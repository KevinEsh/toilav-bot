"""Tests for show_products tool in yalti.py.

Mockea whatsapp_client.post_message y el catálogo PRODUCTS. No toca DB.
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
from models import StoreRow
from yalti import ChatDeps, show_products

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(
    p_id=1,
    name="Almendras",
    price=120.0,
    currency="MXN",
    description="Almendras tostadas con sal",
    image_url="https://cdn.test/almendras.jpg",
    available=True,
):
    product = MagicMock()
    product.p_id = p_id
    product.p_name = name
    product.p_sale_price = price
    product.p_currency = currency
    product.p_description = description
    product.p_image_url = image_url
    product.p_is_available = available
    return product


def _make_ctx(once=None, products=None):
    customer = MagicMock()
    customer.c_id = 1
    customer.c_name = "Juan López"
    customer.c_whatsapp_id = "5215512345678"
    deps = ChatDeps(
        customer=customer,
        store=StoreRow(s_id=1, s_name="Test Store", s_description=""),
        products=products if products is not None else {},
        session=AsyncMock(),
    )
    if once:
        deps._once.update(once)
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


@pytest.fixture
def mock_settings():
    """Settings con credenciales válidas para la mayoría de tests."""
    with patch("yalti.settings") as s:
        s.WHATSAPP_ACCESS_TOKEN = "token-abc"
        s.WHATSAPP_API_VERSION = "v18.0"
        s.PHONE_NUMBER_ID = "phone-123"
        yield s


@pytest.fixture
def mock_catalog():
    """Catálogo con un producto con imagen, uno sin imagen, uno no disponible."""
    catalog = {
        1: _make_product(
            p_id=1,
            name="Almendras",
            price=120.0,
            image_url="https://cdn.test/almendras.jpg",
            available=True,
        ),
        2: _make_product(
            p_id=2,
            name="Nueces",
            price=85.0,
            image_url=None,
            description="Nueces de la india",
            available=True,
        ),
        3: _make_product(
            p_id=3,
            name="Pistaches",
            price=95.0,
            image_url="https://cdn.test/pistaches.jpg",
            available=False,
        ),
    }
    yield catalog


# ---------------------------------------------------------------------------
# Validaciones sin red
# ---------------------------------------------------------------------------


class TestShowProductsGuards:
    async def test_already_shown_this_turn(self, mock_settings, mock_catalog):
        ctx = _make_ctx(once={"show_products"}, products=mock_catalog)
        with patch("yalti.whatsapp_client.post_message", new=AsyncMock()) as mock_post:
            result = await show_products(ctx, [1])
        assert "ya fueron enviados" in result
        mock_post.assert_not_called()

    async def test_empty_p_ids(self, mock_settings, mock_catalog):
        ctx = _make_ctx(products=mock_catalog)
        with patch("yalti.whatsapp_client.post_message", new=AsyncMock()) as mock_post:
            result = await show_products(ctx, [])
        assert result.startswith("ERROR_VALIDACION")
        mock_post.assert_not_called()
        assert "show_products" not in ctx.deps._once

    async def test_all_missing(self, mock_settings, mock_catalog):
        ctx = _make_ctx(products=mock_catalog)
        with patch("yalti.whatsapp_client.post_message", new=AsyncMock()) as mock_post:
            result = await show_products(ctx, [999, 998])
        assert result.startswith("ERROR_VALIDACION")
        assert "999" in result and "998" in result
        mock_post.assert_not_called()

    async def test_all_missing_no_catalog(self, mock_settings):
        """p_ids que no existen en el catálogo devuelven ERROR_VALIDACION."""
        ctx = _make_ctx()
        with patch("yalti.whatsapp_client.post_message", new=AsyncMock()) as mock_post:
            result = await show_products(ctx, [3])
        assert result.startswith("ERROR_VALIDACION")
        assert "3" in result
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Filtrado y dedup
# ---------------------------------------------------------------------------


class TestShowProductsFiltering:
    async def test_invalid_ids_rejected(self, mock_settings, mock_catalog):
        """p_ids no existentes se rechazan con ERROR_VALIDACION."""
        catalog_only_1_2 = {k: v for k, v in mock_catalog.items() if k in (1, 2)}
        ctx = _make_ctx(products=catalog_only_1_2)
        mock_post = AsyncMock()
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            result = await show_products(ctx, [1, 999])
        assert result.startswith("ERROR_VALIDACION")
        mock_post.assert_not_called()

    async def test_dedup_preserves_order(self, mock_settings, mock_catalog):
        catalog_1_2 = {k: v for k, v in mock_catalog.items() if k in (1, 2)}
        ctx = _make_ctx(products=catalog_1_2)
        mock_post = AsyncMock()
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            await show_products(ctx, [1, 2, 1, 2])
        assert mock_post.call_count == 2

    async def test_cap_at_5(self, mock_settings):
        """Más de 5 productos válidos → se cappea a 5."""
        catalog = {
            i: _make_product(
                p_id=i, name=f"Prod{i}", price=10.0 + i, image_url=f"https://cdn.test/{i}.jpg"
            )
            for i in range(1, 10)
        }
        ctx = _make_ctx(products=catalog)
        mock_post = AsyncMock()
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            result = await show_products(ctx, list(range(1, 10)))
        assert mock_post.call_count == 5
        assert "5 productos" in result


# ---------------------------------------------------------------------------
# Payload shape
# ---------------------------------------------------------------------------


class TestShowProductsPayload:
    async def test_image_payload_for_product_with_url(self, mock_settings, mock_catalog):
        ctx = _make_ctx(products=mock_catalog)
        mock_post = AsyncMock()
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            await show_products(ctx, [1])
        payload = mock_post.call_args.args[0]
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "5215512345678"
        assert payload["type"] == "image"
        assert payload["image"]["link"] == "https://cdn.test/almendras.jpg"
        caption = payload["image"]["caption"]
        assert "Almendras" in caption
        assert "$120" in caption
        assert "MXN" in caption
        assert "tostadas" in caption  # del description

    async def test_text_fallback_without_image(self, mock_settings, mock_catalog):
        """p_id=2 no tiene image_url → fallback a type text."""
        ctx = _make_ctx(products=mock_catalog)
        mock_post = AsyncMock()
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            await show_products(ctx, [2])
        payload = mock_post.call_args.args[0]
        assert payload["type"] == "text"
        assert payload["text"]["preview_url"] is False
        body = payload["text"]["body"]
        assert "Nueces" in body
        assert "$85" in body

    async def test_caption_without_description(self, mock_settings):
        """Producto sin description no deja el caption con newlines colgantes."""
        catalog = {
            1: _make_product(
                p_id=1,
                name="Foo",
                price=10.0,
                description=None,
                image_url="https://cdn.test/foo.jpg",
            ),
        }
        ctx = _make_ctx(products=catalog)
        mock_post = AsyncMock()
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            await show_products(ctx, [1])
        caption = mock_post.call_args.args[0]["image"]["caption"]
        assert caption == "*Foo* — $10.0 MXN"


# ---------------------------------------------------------------------------
# Errores HTTP / red — envío parcial y _once
# ---------------------------------------------------------------------------


class TestShowProductsHttpErrors:
    async def test_timeout_on_first_aborts_nothing_sent(self, mock_settings, mock_catalog):
        ctx = _make_ctx(products=mock_catalog)
        mock_post = AsyncMock(side_effect=httpx.TimeoutException("slow"))
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            result = await show_products(ctx, [1, 2])
        assert result.startswith("ERROR_INTERNO")
        assert "show_products" not in ctx.deps._once  # permite retry

    async def test_http_error_on_first_aborts_nothing_sent(self, mock_settings, mock_catalog):
        ctx = _make_ctx(products=mock_catalog)
        response = MagicMock(status_code=500, text="server error")
        error = httpx.HTTPStatusError("500", request=MagicMock(), response=response)
        mock_post = AsyncMock(side_effect=error)
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            result = await show_products(ctx, [1, 2])
        assert result.startswith("ERROR_INTERNO")
        assert "show_products" not in ctx.deps._once

    async def test_partial_send_marks_once_and_reports(self, mock_settings, mock_catalog):
        """Primer producto OK, segundo falla → _once se marca (ya llegó algo al cliente)."""
        catalog_1_2 = {k: v for k, v in mock_catalog.items() if k in (1, 2)}
        ctx = _make_ctx(products=catalog_1_2)
        mock_post = AsyncMock(
            side_effect=[
                MagicMock(status_code=200),
                httpx.TimeoutException("slow"),
            ]
        )
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            result = await show_products(ctx, [1, 2])
        assert "1 de 2" in result
        assert "parcial" in result.lower()
        assert "show_products" in ctx.deps._once
        assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# Happy path + idempotencia
# ---------------------------------------------------------------------------


class TestShowProductsHappyPath:
    async def test_marks_once_on_success(self, mock_settings, mock_catalog):
        ctx = _make_ctx(products=mock_catalog)
        with patch("yalti.whatsapp_client.post_message", new=AsyncMock()):
            await show_products(ctx, [1])
        assert "show_products" in ctx.deps._once

    async def test_second_call_blocked_by_once(self, mock_settings, mock_catalog):
        ctx = _make_ctx(products=mock_catalog)
        mock_post = AsyncMock()
        with patch("yalti.whatsapp_client.post_message", new=mock_post):
            await show_products(ctx, [1])
            result2 = await show_products(ctx, [2])
        assert "ya fueron enviados" in result2
        assert mock_post.call_count == 1
