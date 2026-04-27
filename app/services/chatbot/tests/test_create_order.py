"""Tests for create_order tool in yalti.py.

Validations happen before any DB write, so error cases don't need a real DB.
Happy path mocks the AsyncSession injected into ChatDeps.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
if _chatbot_dir not in sys.path:
    sys.path.insert(0, _chatbot_dir)

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yalti import ChatDeps, StoreInfo, create_order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(active_order_id=None, session=None):
    """Minimal RunContext-like object with ChatDeps."""
    customer = MagicMock()
    customer.c_id = 1
    customer.c_name = "Test User"

    store = StoreInfo(s_id=1, name="Test Store", description="desc", properties={})

    deps = ChatDeps(
        customer=customer,
        store=store,
        products="",
        session=session or AsyncMock(),
        active_order_id=active_order_id,
    )
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _make_product(p_id: int, name: str, price: float):
    p = MagicMock()
    p.p_id = p_id
    p.p_name = name
    p.p_sale_price = price
    return p


FAKE_PRODUCTS = {
    1: _make_product(1, "Almendras tostadas", 120.0),
    2: _make_product(2, "Pistaches", 95.0),
}

VALID_ITEMS = [{"p_id": 1, "units": 2}, {"p_id": 2, "units": 1}]
VALID_ADDRESS = "Av. Juárez 45, Col. Centro"


# ---------------------------------------------------------------------------
# Validation failures — no DB involved
# ---------------------------------------------------------------------------

class TestCreateOrderValidations:

    @pytest.mark.asyncio
    async def test_empty_order_items(self):
        ctx = _make_ctx()
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=[], delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_empty_delivery_address(self):
        ctx = _make_ctx()
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=VALID_ITEMS, delivery_address="")
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_whitespace_delivery_address(self):
        ctx = _make_ctx()
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=VALID_ITEMS, delivery_address="   ")
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_unknown_p_id(self):
        ctx = _make_ctx()
        items = [{"p_id": 999, "units": 1}]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=999" in result
        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_units_zero(self):
        ctx = _make_ctx()
        items = [{"p_id": 1, "units": 0}]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_units_negative(self):
        ctx = _make_ctx()
        items = [{"p_id": 1, "units": -3}]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_item_not_a_dict(self):
        ctx = _make_ctx()
        items = ["almendras 2 unidades"]  # cadena en lugar de dict
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_item_missing_units_field(self):
        ctx = _make_ctx()
        items = [{"p_id": 1}]  # falta units
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_item_missing_p_id_field(self):
        ctx = _make_ctx()
        items = [{"units": 2}]  # falta p_id
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_multiple_errors_all_reported(self):
        """Todos los errores de todos los ítems se reportan en un solo retorno."""
        ctx = _make_ctx()
        items = [
            {"p_id": 999, "units": 2},   # p_id inválido
            {"p_id": 1, "units": 0},      # units inválido
        ]
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=999" in result
        assert ctx.deps.active_order_id is None


# ---------------------------------------------------------------------------
# Happy path — session mockeada en ChatDeps
# ---------------------------------------------------------------------------

class TestCreateOrderHappyPath:

    def _make_session_for_create(self):
        """Session mock: first execute returns o_id=42, subsequent ones return item rows."""
        session = AsyncMock()

        order_result = MagicMock()
        order_result.scalar.return_value = 42

        item_result = MagicMock()
        item_result.mappings.return_value.first.return_value = {
            "oi_p_id": 1, "oi_units": 2, "oi_unit_price": 120.0,
        }

        session.execute.side_effect = [order_result, item_result, item_result]
        return session

    @pytest.mark.asyncio
    async def test_creates_order_and_sets_active_order_id(self):
        session = self._make_session_for_create()
        ctx = _make_ctx(session=session)

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti._order_summary", return_value="🛍️ Resumen del pedido"), \
             patch("yalti._send_whatsapp_text"):
            result = await create_order(ctx, order_items=VALID_ITEMS, delivery_address=VALID_ADDRESS)

        assert result == "🛍️ Resumen del pedido"
        assert ctx.deps.active_order_id == 42
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_active_order_id_stays_none_after_validation_error(self):
        """Garantiza idempotencia: si falla validación, active_order_id no se toca."""
        ctx = _make_ctx()
        assert ctx.deps.active_order_id is None

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            await create_order(ctx, order_items=[], delivery_address=VALID_ADDRESS)

        assert ctx.deps.active_order_id is None

    @pytest.mark.asyncio
    async def test_db_exception_returns_error_interno(self):
        """Si la DB falla, retorna ERROR_INTERNO sin propagar la excepción."""
        session = AsyncMock()
        session.execute.side_effect = Exception("DB connection lost")
        ctx = _make_ctx(session=session)

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await create_order(ctx, order_items=VALID_ITEMS, delivery_address=VALID_ADDRESS)

        assert result.startswith("ERROR_INTERNO:")
        assert ctx.deps.active_order_id is None
