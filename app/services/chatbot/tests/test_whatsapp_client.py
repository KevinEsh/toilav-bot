"""Tests for whatsapp_client.post_message.

Mockea httpx.AsyncClient. Verifica que URL/headers/timeout/payload se
construyen correctamente y que las excepciones httpx.* se propagan sin
envolver (el caller decide el mensaje de error).
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
_db_dir = os.path.normpath(os.path.join(_chatbot_dir, "..", "database"))
for _p in [_chatbot_dir, _db_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import whatsapp_client


def _make_async_client(post_return=None, post_side_effect=None):
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    if post_side_effect is not None:
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        if post_return is None:
            post_return = MagicMock(status_code=200)
            post_return.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=post_return)
    return mock_client


@pytest.fixture
def mock_settings():
    with patch("whatsapp_client.settings") as s:
        s.WHATSAPP_ACCESS_TOKEN = "token-abc"
        s.WHATSAPP_API_VERSION = "v18.0"
        s.PHONE_NUMBER_ID = "phone-123"
        yield s


PAYLOAD = {
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": "5215599999999",
    "type": "text",
    "text": {"preview_url": False, "body": "hola"},
}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestPostMessage:

    async def test_url_constructed_from_settings(self, mock_settings):
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            await whatsapp_client.post_message(PAYLOAD)
        url = client.post.call_args.args[0]
        assert url == "https://graph.facebook.com/v18.0/phone-123/messages"

    async def test_auth_header_uses_access_token(self, mock_settings):
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            await whatsapp_client.post_message(PAYLOAD)
        headers = client.post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer token-abc"

    async def test_payload_passed_as_json(self, mock_settings):
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            await whatsapp_client.post_message(PAYLOAD)
        assert client.post.call_args.kwargs["json"] is PAYLOAD

    async def test_default_timeout_is_10s(self, mock_settings):
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            await whatsapp_client.post_message(PAYLOAD)
        assert client.post.call_args.kwargs["timeout"] == 10.0

    async def test_custom_timeout(self, mock_settings):
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            await whatsapp_client.post_message(PAYLOAD, timeout=30.0)
        assert client.post.call_args.kwargs["timeout"] == 30.0

    async def test_returns_response_on_success(self, mock_settings):
        response = MagicMock(status_code=200)
        response.raise_for_status = MagicMock()
        client = _make_async_client(post_return=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = await whatsapp_client.post_message(PAYLOAD)
        assert result is response


# ---------------------------------------------------------------------------
# Propagación de excepciones — el caller decide qué hacer
# ---------------------------------------------------------------------------

class TestPostMessageErrorsPropagate:

    async def test_http_error_propagates(self, mock_settings):
        response = MagicMock(status_code=400, text="bad request")
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("400", request=MagicMock(), response=response)
        )
        client = _make_async_client(post_return=response)
        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(httpx.HTTPStatusError):
                await whatsapp_client.post_message(PAYLOAD)

    async def test_timeout_propagates(self, mock_settings):
        client = _make_async_client(post_side_effect=httpx.TimeoutException("slow"))
        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(httpx.TimeoutException):
                await whatsapp_client.post_message(PAYLOAD)

    async def test_network_error_propagates(self, mock_settings):
        client = _make_async_client(post_side_effect=httpx.ConnectError("no route"))
        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(httpx.HTTPError):
                await whatsapp_client.post_message(PAYLOAD)
