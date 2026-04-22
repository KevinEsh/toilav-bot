"""Tests for escalate_to_staff tool in yalti.py.

Mockea httpx.AsyncClient.post. No toca DB.
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

from yalti import ChatDeps, StoreInfo, escalate_to_staff


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(once=None):
    customer = MagicMock()
    customer.c_id = 1
    customer.c_name = "Juan López"
    customer.c_whatsapp_id = "5215512345678"
    deps = ChatDeps(
        customer=customer,
        store=StoreInfo(s_id=1, name="Test Store", description="", properties={}),
        products="",
    )
    if once:
        deps._once.update(once)
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _make_async_client(post_return=None, post_side_effect=None):
    """Construye un mock de httpx.AsyncClient usable como async context manager."""
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
    """Settings con credenciales válidas para la mayoría de tests."""
    with patch("yalti.settings") as s:
        s.OWNER_WA_ID = "5215599999999"
        s.WHATSAPP_ACCESS_TOKEN = "token-abc"
        s.WHATSAPP_API_VERSION = "v18.0"
        s.PHONE_NUMBER_ID = "phone-123"
        yield s


# ---------------------------------------------------------------------------
# Guards: idempotencia + validaciones sin tocar la red
# ---------------------------------------------------------------------------

class TestEscalateGuards:

    async def test_already_escalated_this_turn(self, mock_settings):
        """Si _once ya contiene 'escalate_to_staff', no debe hacer HTTP."""
        ctx = _make_ctx(once={"escalate_to_staff"})
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            result = await escalate_to_staff(ctx, "pregunta")
        assert "ya fue notificado" in result
        client.post.assert_not_called()

    async def test_empty_message(self, mock_settings):
        ctx = _make_ctx()
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            result = await escalate_to_staff(ctx, "")
        assert result.startswith("ERROR_VALIDACION")
        client.post.assert_not_called()
        assert "escalate_to_staff" not in ctx.deps._once

    async def test_whitespace_only_message(self, mock_settings):
        ctx = _make_ctx()
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            result = await escalate_to_staff(ctx, "   \n\t ")
        assert result.startswith("ERROR_VALIDACION")
        client.post.assert_not_called()

    async def test_missing_owner_wa_id(self):
        ctx = _make_ctx()
        client = _make_async_client()
        with patch("yalti.settings") as s:
            s.OWNER_WA_ID = ""
            s.WHATSAPP_ACCESS_TOKEN = "token-abc"
            s.WHATSAPP_API_VERSION = "v18.0"
            s.PHONE_NUMBER_ID = "phone-123"
            with patch("httpx.AsyncClient", return_value=client):
                result = await escalate_to_staff(ctx, "pregunta")
        assert result.startswith("ERROR_INTERNO")
        client.post.assert_not_called()
        assert "escalate_to_staff" not in ctx.deps._once

    async def test_missing_credentials(self):
        ctx = _make_ctx()
        client = _make_async_client()
        with patch("yalti.settings") as s:
            s.OWNER_WA_ID = "5215599999999"
            s.WHATSAPP_ACCESS_TOKEN = ""
            s.WHATSAPP_API_VERSION = "v18.0"
            s.PHONE_NUMBER_ID = "phone-123"
            with patch("httpx.AsyncClient", return_value=client):
                result = await escalate_to_staff(ctx, "pregunta")
        assert result.startswith("ERROR_INTERNO")
        client.post.assert_not_called()


# ---------------------------------------------------------------------------
# Errores HTTP / red
# ---------------------------------------------------------------------------

class TestEscalateHttpErrors:

    async def test_http_4xx(self, mock_settings):
        ctx = _make_ctx()
        response = MagicMock(status_code=400, text="bad request")
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("400", request=MagicMock(), response=response)
        )
        client = _make_async_client(post_return=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = await escalate_to_staff(ctx, "pregunta")
        assert result.startswith("ERROR_INTERNO")

    async def test_http_5xx(self, mock_settings):
        ctx = _make_ctx()
        response = MagicMock(status_code=503, text="unavailable")
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=response)
        )
        client = _make_async_client(post_return=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = await escalate_to_staff(ctx, "pregunta")
        assert result.startswith("ERROR_INTERNO")

    async def test_timeout(self, mock_settings):
        ctx = _make_ctx()
        client = _make_async_client(post_side_effect=httpx.TimeoutException("timeout"))
        with patch("httpx.AsyncClient", return_value=client):
            result = await escalate_to_staff(ctx, "pregunta")
        assert result.startswith("ERROR_INTERNO")
        assert "timeout" in result.lower()

    async def test_network_error(self, mock_settings):
        ctx = _make_ctx()
        client = _make_async_client(post_side_effect=httpx.ConnectError("no route"))
        with patch("httpx.AsyncClient", return_value=client):
            result = await escalate_to_staff(ctx, "pregunta")
        assert result.startswith("ERROR_INTERNO")


# ---------------------------------------------------------------------------
# Happy path — payload y URL
# ---------------------------------------------------------------------------

class TestEscalateHappyPath:

    async def test_returns_success_message(self, mock_settings):
        ctx = _make_ctx()
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            result = await escalate_to_staff(ctx, "¿Tienen nueces sin sal?")
        assert result == "Notificación enviada al dueño de la tienda."
        assert "escalate_to_staff" in ctx.deps._once

    async def test_payload_shape(self, mock_settings):
        """URL/headers son responsabilidad de whatsapp_client (ver su test propio).
        Aquí sólo verificamos que escalate_to_staff arma el payload correcto."""
        ctx = _make_ctx()
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            await escalate_to_staff(ctx, "¿Tienen nueces sin sal?")

        payload = client.post.call_args.kwargs["json"]
        assert payload["to"] == "5215599999999"
        assert payload["messaging_product"] == "whatsapp"
        assert payload["type"] == "text"
        assert payload["text"]["preview_url"] is False
        body = payload["text"]["body"]
        assert "Juan López" in body
        assert "5215512345678" in body
        assert "¿Tienen nueces sin sal?" in body

    async def test_message_is_trimmed(self, mock_settings):
        """Espacios alrededor del mensaje no llegan al body."""
        ctx = _make_ctx()
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            await escalate_to_staff(ctx, "   hola dueño   ")
        body = client.post.call_args.kwargs["json"]["text"]["body"]
        assert "hola dueño" in body
        assert "   hola dueño" not in body

    async def test_once_marker_blocks_second_call(self, mock_settings):
        """Tras un happy path, un segundo llamado no debe tocar la red."""
        ctx = _make_ctx()
        client = _make_async_client()
        with patch("httpx.AsyncClient", return_value=client):
            await escalate_to_staff(ctx, "primera")
            result2 = await escalate_to_staff(ctx, "segunda")
        assert "ya fue notificado" in result2
        assert client.post.call_count == 1
