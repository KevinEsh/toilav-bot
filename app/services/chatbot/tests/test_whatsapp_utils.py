"""Tests for whatsapp_utils module."""

import asyncio
from collections import OrderedDict
from unittest.mock import AsyncMock, patch

import pytest
from whatsapp_utils import (
    _UNSUPPORTED_TYPE_RESPONSE,
    UserMessageBuffer,
    _extract_message_text,
    _get_buffer,
    _user_buffers,
    encapsulate_text_message,
    is_valid_whatsapp_message,
    parse_text_for_whatsapp,
    process_whatsapp_message,
)

# ── Helpers ──────────────────────────────────────────────────────────────


def _clear_all():
    _user_buffers.clear()


# ── UserMessageBuffer ────────────────────────────────────────────────────


class TestUserMessageBuffer:
    def test_first_message_is_not_duplicate(self):
        buf = UserMessageBuffer("test_user")
        assert buf.is_duplicate("msg_001") is False

    def test_same_id_is_duplicate(self):
        buf = UserMessageBuffer("test_user")
        buf.is_duplicate("msg_002")
        assert buf.is_duplicate("msg_002") is True

    def test_different_ids_are_independent(self):
        buf = UserMessageBuffer("test_user")
        buf.is_duplicate("msg_a")
        assert buf.is_duplicate("msg_b") is False

    def test_lru_eviction(self):
        """When exceeding max_seen, oldest entry is evicted."""
        buf = UserMessageBuffer("test_user", max_seen=5)
        for i in range(6):
            buf.is_duplicate(f"id_{i}")
        # id_0 should have been evicted
        assert "id_0" not in buf._seen
        # id_5 should still be present
        assert "id_5" in buf._seen

    def test_add_message_and_flush_timestamp_order(self):
        """Flush should return messages sorted by timestamp."""
        buf = UserMessageBuffer("test_user")
        buf.add_message(1700000003, "Tercero")
        buf.add_message(1700000001, "Primero")
        buf.add_message(1700000002, "Segundo")

        result = buf.flush()
        assert result == "Primero\nSegundo\nTercero"

    def test_flush_fifo_on_same_timestamp(self):
        """Messages with the same timestamp should be flushed in insertion order."""
        buf = UserMessageBuffer("test_user")
        buf.add_message(1700000001, "A")
        buf.add_message(1700000001, "B")
        buf.add_message(1700000001, "C")

        result = buf.flush()
        assert result == "A\nB\nC"

    def test_flush_clears_messages(self):
        buf = UserMessageBuffer("test_user")
        buf.add_message(1, "x")
        assert len(buf._messages) == 1
        buf.flush()
        assert len(buf._messages) == 0

    def test_flush_empty_returns_empty(self):
        buf = UserMessageBuffer("test_user")
        assert buf.flush() == ""

    def test_name_attribute(self):
        buf = UserMessageBuffer("test_user")
        buf.name = "Juan"
        assert buf.name == "Juan"

    def test_dedup_independent_per_buffer(self):
        """Two different buffers (users) should have independent dedup caches."""
        buf_a = UserMessageBuffer("user_a")
        buf_b = UserMessageBuffer("user_b")
        buf_a.is_duplicate("shared_id")
        # Same message_id in a different buffer should NOT be duplicate
        assert buf_b.is_duplicate("shared_id") is False

    @pytest.mark.asyncio
    async def test_wait_for_more_messages_cancels_previous_waiter(self):
        """A second call to wait_for_more_messages should cancel the first waiter."""
        buf = UserMessageBuffer("test_user")

        async def waiter():
            await buf.wait_for_more_messages()

        with patch("whatsapp_utils.DEBOUNCE_SECONDS", 10):
            task1 = asyncio.create_task(waiter())
            await asyncio.sleep(0)  # let task1 register as waiter

            task2 = asyncio.create_task(waiter())
            await asyncio.sleep(0)  # let task2 cancel task1 and register

            assert task1.cancelling()
            assert buf._debounce_timer is task2

            task2.cancel()
            await asyncio.sleep(0)


# ── _extract_message_text ────────────────────────────────────────────────


class TestExtractMessageText:
    def test_text_message(self):
        msg = {"type": "text", "text": {"body": "Hola mundo"}}
        assert _extract_message_text(msg) == "Hola mundo"

    def test_image_without_caption(self):
        msg = {"type": "image", "image": {"id": "img1"}}
        result = _extract_message_text(msg)
        assert result == _UNSUPPORTED_TYPE_RESPONSE["image"]

    def test_image_with_caption(self):
        msg = {"type": "image", "image": {"id": "img1", "caption": "Mira esto"}}
        assert _extract_message_text(msg) == "Mira esto"

    def test_video_without_caption(self):
        msg = {"type": "video", "video": {"id": "vid1"}}
        result = _extract_message_text(msg)
        assert result == _UNSUPPORTED_TYPE_RESPONSE["video"]

    def test_video_with_caption(self):
        msg = {"type": "video", "video": {"id": "vid1", "caption": "Mi video"}}
        assert _extract_message_text(msg) == "Mi video"

    def test_document_without_caption(self):
        msg = {"type": "document", "document": {"id": "doc1"}}
        result = _extract_message_text(msg)
        assert result == _UNSUPPORTED_TYPE_RESPONSE["document"]

    def test_document_with_caption(self):
        msg = {"type": "document", "document": {"id": "doc1", "caption": "Factura"}}
        assert _extract_message_text(msg) == "Factura"

    def test_audio(self):
        msg = {"type": "audio", "audio": {"id": "aud1"}}
        result = _extract_message_text(msg)
        assert result == _UNSUPPORTED_TYPE_RESPONSE["audio"]

    def test_sticker(self):
        msg = {"type": "sticker", "sticker": {"id": "stk1"}}
        result = _extract_message_text(msg)
        assert result == _UNSUPPORTED_TYPE_RESPONSE["sticker"]

    def test_location(self):
        msg = {"type": "location", "location": {"latitude": 19.4, "longitude": -99.1}}
        result = _extract_message_text(msg)
        assert result == _UNSUPPORTED_TYPE_RESPONSE["location"]

    def test_contacts(self):
        msg = {"type": "contacts", "contacts": [{"name": {"formatted_name": "Pedro"}}]}
        result = _extract_message_text(msg)
        assert result == _UNSUPPORTED_TYPE_RESPONSE["contacts"]

    def test_reaction_returns_none(self):
        msg = {"type": "reaction", "reaction": {"message_id": "wamid.x", "emoji": "👍"}}
        assert _extract_message_text(msg) is None

    def test_interactive_button_reply(self):
        msg = {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "btn1", "title": "Sí, quiero"},
            },
        }
        assert _extract_message_text(msg) == "Sí, quiero"

    def test_interactive_list_reply(self):
        msg = {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "lst1", "title": "Opción 2", "description": "Desc"},
            },
        }
        assert _extract_message_text(msg) == "Opción 2"

    def test_unknown_type_returns_none(self):
        msg = {"type": "some_future_type"}
        assert _extract_message_text(msg) is None


# ── process_text_for_whatsapp ────────────────────────────────────────────


class TestProcessTextForWhatsApp:
    def test_removes_brackets(self):
        assert parse_text_for_whatsapp("Hola 【fuente】 mundo") == "Hola  mundo"

    def test_converts_double_to_single_asterisks(self):
        assert parse_text_for_whatsapp("Esto es **importante**") == "Esto es *importante*"

    def test_mixed_formatting(self):
        text = "【ref】Precio: **$100** MXN"
        assert parse_text_for_whatsapp(text) == "Precio: *$100* MXN"

    def test_no_change_for_plain_text(self):
        assert parse_text_for_whatsapp("Hola, buen día") == "Hola, buen día"


# ── get_text_message_input ───────────────────────────────────────────────


class TestGetTextMessageInput:
    def test_returns_valid_json(self):
        import json

        result = encapsulate_text_message("5215512345678", "Hola")
        data = json.loads(result)
        assert data["messaging_product"] == "whatsapp"
        assert data["to"] == "5215512345678"
        assert data["text"]["body"] == "Hola"
        assert data["type"] == "text"


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
        with (
            patch("whatsapp_utils.DEBOUNCE_SECONDS", 0),
            patch(
                "whatsapp_utils.agent_generate_response",
                new_callable=AsyncMock,
                return_value="Respuesta",
            ) as mock_gen,
            patch("whatsapp_utils.send_message", new_callable=AsyncMock) as mock_send,
        ):
            await process_whatsapp_message(sample_whatsapp_text_body)

            mock_gen.assert_called_once_with("Hola, quiero información", "5215512345678", "Juan")
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_message_is_skipped(self, sample_whatsapp_text_body):
        """Same message_id should not be processed twice."""
        with (
            patch("whatsapp_utils.DEBOUNCE_SECONDS", 0),
            patch(
                "whatsapp_utils.agent_generate_response",
                new_callable=AsyncMock,
                return_value="OK",
            ) as mock_gen,
            patch("whatsapp_utils.send_message", new_callable=AsyncMock),
        ):
            # Run both calls concurrently; second has same message_id
            await asyncio.gather(
                process_whatsapp_message(sample_whatsapp_text_body),
                process_whatsapp_message(sample_whatsapp_text_body),
            )

            # Agent should be called only once
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsupported_type_is_ignored(self, sample_whatsapp_image_body):
        """Image without caption should be silently ignored (no LLM, no send)."""
        with patch("whatsapp_utils.send_message", new_callable=AsyncMock) as mock_send:
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
        with patch("whatsapp_utils.send_message", new_callable=AsyncMock) as mock_send:
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

        with (
            patch("whatsapp_utils.DEBOUNCE_SECONDS", 0.01),
            patch(
                "whatsapp_utils.agent_generate_response",
                new_callable=AsyncMock,
                return_value="OK",
            ) as mock_gen,
            patch("whatsapp_utils.send_message", new_callable=AsyncMock),
        ):
            results = await asyncio.gather(
                process_whatsapp_message(_make_body("msg_1", 1700000002, "Segundo")),
                process_whatsapp_message(_make_body("msg_2", 1700000001, "Primero")),
                return_exceptions=True,
            )

            # One task should have been cancelled, one should have completed
            cancelled = [r for r in results if isinstance(r, asyncio.CancelledError)]
            assert len(cancelled) == 1

            # Agent should be called once with combined messages sorted by timestamp
            mock_gen.assert_called_once()
            combined_text = mock_gen.call_args[0][0]
            assert combined_text == "Primero\nSegundo"

    @pytest.mark.asyncio
    async def test_buffer_preserved_after_flush(self, sample_whatsapp_text_body):
        """After processing, the buffer should remain (for dedup) but messages should be empty."""
        with (
            patch("whatsapp_utils.DEBOUNCE_SECONDS", 0),
            patch(
                "whatsapp_utils.agent_generate_response",
                new_callable=AsyncMock,
                return_value="OK",
            ),
            patch("whatsapp_utils.send_message", new_callable=AsyncMock),
        ):
            await process_whatsapp_message(sample_whatsapp_text_body)
            wa_id = "5215512345678"
            assert wa_id in _user_buffers
            assert len(_user_buffers[wa_id]._messages) == 0
            assert "wamid.abc123" in _user_buffers[wa_id]._seen
