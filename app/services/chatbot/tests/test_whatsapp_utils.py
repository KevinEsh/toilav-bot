"""Tests for whatsapp_utils module."""

import asyncio
from collections import OrderedDict
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models import CustomerRow
from whatsapp_client import encapsulate_text_message
from whatsapp_utils import (
    UserMessageBuffer,
    WhatsappMessage,
    WhatsappUser,
    _user_buffers,
    is_valid_whatsapp_message,
    parse_text_for_whatsapp,
    process_whatsapp_message,
    struct_message_from_payload,
)

# ── Helpers ──────────────────────────────────────────────────────────────


def _clear_all():
    _user_buffers.clear()


def _make_msg(msg_id, timestamp=0, text="", wa_id="test_user"):
    contact = WhatsappUser(wa_id=wa_id, name="Test")
    return WhatsappMessage(id=msg_id, contact=contact, timestamp=timestamp, text=text, type="text")


def _make_customer(wa_id="5215512345678", name="Juan"):
    return CustomerRow(c_id=1, c_phone=wa_id, c_whatsapp_id=wa_id, c_name=name)


@asynccontextmanager
async def _null_session():
    yield AsyncMock()


# ── UserMessageBuffer ────────────────────────────────────────────────────


class TestUserMessageBuffer:
    def test_first_message_is_not_duplicate(self):
        buf = UserMessageBuffer()
        assert buf.is_duplicate(_make_msg("msg_001")) is False

    def test_same_id_is_duplicate(self):
        buf = UserMessageBuffer()
        buf.is_duplicate(_make_msg("msg_002"))
        assert buf.is_duplicate(_make_msg("msg_002")) is True

    def test_different_ids_are_independent(self):
        buf = UserMessageBuffer()
        buf.is_duplicate(_make_msg("msg_a"))
        assert buf.is_duplicate(_make_msg("msg_b")) is False

    def test_lru_eviction(self):
        """When exceeding max_seen, oldest entry is evicted."""
        buf = UserMessageBuffer(max_seen=5)
        for i in range(6):
            buf.is_duplicate(_make_msg(f"id_{i}"))
        assert "id_0" not in buf._seen
        assert "id_5" in buf._seen

    def test_add_message_and_flush_timestamp_order(self):
        """Flush should return messages sorted by timestamp."""
        buf = UserMessageBuffer()
        buf.add_message(_make_msg("id1", timestamp=1700000003, text="Tercero"))
        buf.add_message(_make_msg("id2", timestamp=1700000001, text="Primero"))
        buf.add_message(_make_msg("id3", timestamp=1700000002, text="Segundo"))

        result = buf.flush()
        assert result == "Primero\nSegundo\nTercero"

    def test_flush_fifo_on_same_timestamp(self):
        """Messages with the same timestamp should be flushed in insertion order."""
        buf = UserMessageBuffer()
        buf.add_message(_make_msg("id1", timestamp=1700000001, text="A"))
        buf.add_message(_make_msg("id2", timestamp=1700000001, text="B"))
        buf.add_message(_make_msg("id3", timestamp=1700000001, text="C"))

        result = buf.flush()
        assert result == "A\nB\nC"

    def test_flush_clears_messages(self):
        buf = UserMessageBuffer()
        buf.add_message(_make_msg("id1", timestamp=1, text="x"))
        assert len(buf._messages) == 1
        buf.flush()
        assert len(buf._messages) == 0

    def test_flush_empty_returns_empty(self):
        buf = UserMessageBuffer()
        assert buf.flush() == ""

    def test_dedup_independent_per_buffer(self):
        """Two different buffers (users) should have independent dedup caches."""
        buf_a = UserMessageBuffer()
        buf_b = UserMessageBuffer()
        buf_a.is_duplicate(_make_msg("shared_id"))
        assert buf_b.is_duplicate(_make_msg("shared_id")) is False

    @pytest.mark.asyncio
    async def test_wait_for_more_messages_cancels_previous_waiter(self):
        """A second call to wait_for_more_messages should cancel the first waiter."""
        buf = UserMessageBuffer()

        async def waiter():
            await buf.wait_for_more_messages()

        with patch("whatsapp_utils.DEBOUNCE_SECONDS", 10):
            task1 = asyncio.create_task(waiter())
            await asyncio.sleep(0)

            task2 = asyncio.create_task(waiter())
            await asyncio.sleep(0)

            assert task1.cancelling()
            assert buf._debounce_timer is task2

            task2.cancel()
            await asyncio.sleep(0)


# ── struct_message_from_payload ──────────────────────────────────────────


def _make_text_payload(wa_id="521", name="Juan", text="Hola", msg_id="wamid.123", ts=1700000000):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": wa_id, "profile": {"name": name}}],
                            "messages": [
                                {
                                    "id": msg_id,
                                    "type": "text",
                                    "timestamp": str(ts),
                                    "text": {"body": text},
                                }
                            ],
                            "metadata": {"display_phone_number": "5215550000"},
                        }
                    }
                ]
            }
        ]
    }


class TestStructMessageFromPayload:
    def test_text_message_returns_whatsapp_message(self):
        body = _make_text_payload(text="Hola mundo")
        result = struct_message_from_payload(body)
        assert isinstance(result, WhatsappMessage)
        assert result.text == "Hola mundo"

    def test_contact_info_extracted(self):
        body = _make_text_payload(wa_id="52999", name="María")
        result = struct_message_from_payload(body)
        assert result.contact.wa_id == "52999"
        assert result.contact.name == "María"

    def test_message_id_extracted(self):
        body = _make_text_payload(msg_id="wamid.abc")
        result = struct_message_from_payload(body)
        assert result.id == "wamid.abc"

    def test_non_text_type_returns_none(self):
        body = _make_text_payload()
        body["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
        result = struct_message_from_payload(body)
        assert result is None

    def test_malformed_payload_returns_none(self):
        result = struct_message_from_payload({"entry": []})
        assert result is None

    def test_empty_payload_returns_none(self):
        result = struct_message_from_payload({})
        assert result is None


# ── parse_text_for_whatsapp ──────────────────────────────────────────────


class TestParseTextForWhatsApp:
    def test_removes_brackets(self):
        assert parse_text_for_whatsapp("Hola 【fuente】 mundo") == "Hola  mundo"

    def test_converts_double_to_single_asterisks(self):
        assert parse_text_for_whatsapp("Esto es **importante**") == "Esto es *importante*"

    def test_mixed_formatting(self):
        text = "【ref】Precio: **$100** MXN"
        assert parse_text_for_whatsapp(text) == "Precio: *$100* MXN"

    def test_no_change_for_plain_text(self):
        assert parse_text_for_whatsapp("Hola, buen día") == "Hola, buen día"


# ── encapsulate_text_message ─────────────────────────────────────────────


class TestGetTextMessageInput:
    def test_returns_valid_dict(self):
        result = encapsulate_text_message("5215512345678", "Hola")
        assert result["messaging_product"] == "whatsapp"
        assert result["to"] == "5215512345678"
        assert result["text"]["body"] == "Hola"
        assert result["type"] == "text"


# ── is_valid_whatsapp_message ────────────────────────────────────────────


class TestIsValidWhatsAppMessage:
    def test_valid_message(self, sample_whatsapp_text_body):
        assert is_valid_whatsapp_message(sample_whatsapp_text_body) is True

    def test_missing_object(self):
        assert is_valid_whatsapp_message({}) is False

    def test_missing_messages(self):
        body = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {}}]}]}
        assert is_valid_whatsapp_message(body) is False

    def test_status_update_is_invalid(self, sample_status_update_body):
        assert is_valid_whatsapp_message(sample_status_update_body) is False


# ── process_whatsapp_message ─────────────────────────────────────────────


class TestProcessWhatsAppMessage:
    def setup_method(self):
        _clear_all()

    @pytest.mark.asyncio
    async def test_text_message_calls_agent(self, sample_whatsapp_text_body):
        """A text message should be debounced, flushed, and sent to the agent."""
        customer = _make_customer()
        with (
            patch("whatsapp_utils.DEBOUNCE_SECONDS", 0),
            patch("whatsapp_utils.get_session", _null_session),
            patch(
                "whatsapp_utils.upsert_customer",
                new_callable=AsyncMock,
                return_value=customer,
            ),
            patch("whatsapp_utils.load_conversation", new_callable=AsyncMock, return_value=[]),
            patch("whatsapp_utils.insert_message", new_callable=AsyncMock, return_value=1),
            patch("whatsapp_utils.update_message_status", new_callable=AsyncMock),
            patch("whatsapp_utils.update_conversation", new_callable=AsyncMock),
            patch("whatsapp_utils.store_cache") as mock_sc,
            patch("whatsapp_utils.products_cache") as mock_pc,
            patch(
                "whatsapp_utils.agent_generate_response",
                new_callable=AsyncMock,
                return_value=("Respuesta", []),
            ) as mock_gen,
            patch("whatsapp_utils.send_text_message", new_callable=AsyncMock) as mock_send,
        ):
            mock_sc.aget = AsyncMock(return_value=MagicMock())
            mock_pc.aget = AsyncMock(return_value="")
            await process_whatsapp_message(sample_whatsapp_text_body)

            mock_gen.assert_called_once()
            assert mock_gen.call_args.kwargs["message"] == "Hola, quiero información"
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_message_is_skipped(self, sample_whatsapp_text_body):
        """Same message_id should not be processed twice."""
        customer = _make_customer()
        with (
            patch("whatsapp_utils.DEBOUNCE_SECONDS", 0),
            patch("whatsapp_utils.get_session", _null_session),
            patch(
                "whatsapp_utils.upsert_customer",
                new_callable=AsyncMock,
                return_value=customer,
            ),
            patch("whatsapp_utils.load_conversation", new_callable=AsyncMock, return_value=[]),
            patch("whatsapp_utils.insert_message", new_callable=AsyncMock, return_value=1),
            patch("whatsapp_utils.update_message_status", new_callable=AsyncMock),
            patch("whatsapp_utils.update_conversation", new_callable=AsyncMock),
            patch("whatsapp_utils.store_cache") as mock_sc,
            patch("whatsapp_utils.products_cache") as mock_pc,
            patch(
                "whatsapp_utils.agent_generate_response",
                new_callable=AsyncMock,
                return_value=("OK", []),
            ) as mock_gen,
            patch("whatsapp_utils.send_text_message", new_callable=AsyncMock),
        ):
            mock_sc.aget = AsyncMock(return_value=MagicMock())
            mock_pc.aget = AsyncMock(return_value="")
            await asyncio.gather(
                process_whatsapp_message(sample_whatsapp_text_body),
                process_whatsapp_message(sample_whatsapp_text_body),
            )
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsupported_type_is_ignored(self, sample_whatsapp_image_body):
        """Image without caption has empty text — silently ignored (no LLM, no send)."""
        with patch("whatsapp_utils.send_text_message", new_callable=AsyncMock) as mock_send:
            await process_whatsapp_message(sample_whatsapp_image_body)
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_reaction_is_ignored(self):
        """Reaction messages should be silently ignored."""
        body = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [
                                    {"profile": {"name": "Luis"}, "wa_id": "5215500002222"}
                                ],
                                "messages": [
                                    {
                                        "from": "5215500002222",
                                        "id": "wamid.react001",
                                        "timestamp": "1700000003",
                                        "type": "reaction",
                                        "reaction": {"message_id": "wamid.original", "emoji": "👍"},
                                    }
                                ],
                            }
                        }
                    ],
                }
            ],
        }
        with patch("whatsapp_utils.send_text_message", new_callable=AsyncMock) as mock_send:
            await process_whatsapp_message(body)
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_messages_combined_in_order(self):
        """Multiple fast messages from the same user should be combined by timestamp."""

        def _make_body(msg_id, timestamp, text):
            return {
                "object": "whatsapp_business_account",
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "metadata": {
                                        "display_phone_number": "5215550000000",
                                        "phone_number_id": "123456789",
                                    },
                                    "contacts": [
                                        {"profile": {"name": "Juan"}, "wa_id": "5215512345678"}
                                    ],
                                    "messages": [
                                        {
                                            "from": "5215512345678",
                                            "id": msg_id,
                                            "timestamp": str(timestamp),
                                            "text": {"body": text},
                                            "type": "text",
                                        }
                                    ],
                                }
                            }
                        ],
                    }
                ],
            }

        customer = _make_customer()
        with (
            patch("whatsapp_utils.DEBOUNCE_SECONDS", 0.01),
            patch("whatsapp_utils.get_session", _null_session),
            patch(
                "whatsapp_utils.upsert_customer",
                new_callable=AsyncMock,
                return_value=customer,
            ),
            patch("whatsapp_utils.load_conversation", new_callable=AsyncMock, return_value=[]),
            patch("whatsapp_utils.insert_message", new_callable=AsyncMock, return_value=1),
            patch("whatsapp_utils.update_message_status", new_callable=AsyncMock),
            patch("whatsapp_utils.update_conversation", new_callable=AsyncMock),
            patch("whatsapp_utils.store_cache") as mock_sc,
            patch("whatsapp_utils.products_cache") as mock_pc,
            patch(
                "whatsapp_utils.agent_generate_response",
                new_callable=AsyncMock,
                return_value=("OK", []),
            ) as mock_gen,
            patch("whatsapp_utils.send_text_message", new_callable=AsyncMock),
        ):
            mock_sc.aget = AsyncMock(return_value=MagicMock())
            mock_pc.aget = AsyncMock(return_value="")
            results = await asyncio.gather(
                process_whatsapp_message(_make_body("msg_1", 1700000002, "Segundo")),
                process_whatsapp_message(_make_body("msg_2", 1700000001, "Primero")),
                return_exceptions=True,
            )

            cancelled = [r for r in results if isinstance(r, asyncio.CancelledError)]
            assert len(cancelled) == 1

            mock_gen.assert_called_once()
            combined_text = mock_gen.call_args.kwargs["message"]
            assert combined_text == "Primero\nSegundo"

    @pytest.mark.asyncio
    async def test_buffer_preserved_after_flush(self, sample_whatsapp_text_body):
        """After processing, the buffer should remain (for dedup) but messages should be empty."""
        customer = _make_customer()
        with (
            patch("whatsapp_utils.DEBOUNCE_SECONDS", 0),
            patch("whatsapp_utils.get_session", _null_session),
            patch(
                "whatsapp_utils.upsert_customer",
                new_callable=AsyncMock,
                return_value=customer,
            ),
            patch("whatsapp_utils.load_conversation", new_callable=AsyncMock, return_value=[]),
            patch("whatsapp_utils.insert_message", new_callable=AsyncMock, return_value=1),
            patch("whatsapp_utils.update_message_status", new_callable=AsyncMock),
            patch("whatsapp_utils.update_conversation", new_callable=AsyncMock),
            patch("whatsapp_utils.store_cache") as mock_sc,
            patch("whatsapp_utils.products_cache") as mock_pc,
            patch(
                "whatsapp_utils.agent_generate_response",
                new_callable=AsyncMock,
                return_value=("OK", []),
            ),
            patch("whatsapp_utils.send_text_message", new_callable=AsyncMock),
        ):
            mock_sc.aget = AsyncMock(return_value=MagicMock())
            mock_pc.aget = AsyncMock(return_value="")
            await process_whatsapp_message(sample_whatsapp_text_body)
            wa_id = "5215512345678"
            assert wa_id in _user_buffers
            assert len(_user_buffers[wa_id]._messages) == 0
            assert "wamid.abc123" in _user_buffers[wa_id]._seen
