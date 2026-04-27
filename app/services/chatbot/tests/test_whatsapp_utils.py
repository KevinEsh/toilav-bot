"""Tests for whatsapp_utils module.

Nota: clases eliminadas respecto a la versión anterior porque sus APIs
cambiaron sustancialmente (UserMessageBuffer constructor, is_duplicate/
add_message firmas, encapsulate_text_message retorna dict, process_whatsapp_
message flujo nuevo con DB + agent_generate_response signature). Ver
`fixes/chatbot/tests/tech_debt.md` sección "Tests removidos en whatsapp_utils".

Las clases conservadas prueban funciones puras cuyas firmas no cambiaron.
"""

import pytest

from whatsapp_utils import (
    _UNSUPPORTED_TYPE_RESPONSE,
    _extract_message_text,
    is_valid_whatsapp_message,
    parse_text_for_whatsapp,
)


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
