"""Tests for create_order tool in yalti.py.

Validations happen before any DB write, so error cases don't need a real DB.
Happy path patches yalti.get_session with a mock session.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
if _chatbot_dir not in sys.path:
    sys.path.insert(0, _chatbot_dir)

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models import OrderRow, StoreRow
from yalti import ChatDeps, create_order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_get_session(session):
    """Returns a get_session replacement that yields the given mock session."""
    @asynccontextmanager
    async def _cm():
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return _cm


def _make_ctx(active_order=None, products=None):
    """Minimal RunContext-like object with ChatDeps."""
    customer = MagicMock()
    customer.c_id = 1
    customer.c_name = "Test User"

    store = StoreRow(s_id=1, s_name="Test Store", s_description="desc")

    deps = ChatDeps(
        customer=customer,
        store=store,
        products=products if products is not None else FAKE_PRODUCTS,
        active_order=active_order,
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
        result = await create_order(ctx, items=[], delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_empty_delivery_address(self):
        ctx = _make_ctx()
        result = await create_order(ctx, items=VALID_ITEMS, delivery_address="")
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_whitespace_delivery_address(self):
        ctx = _make_ctx()
        result = await create_order(ctx, items=VALID_ITEMS, delivery_address="   ")
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_unknown_p_id(self):
        ctx = _make_ctx()
        items = [{"p_id": 999, "units": 1}]
        result = await create_order(ctx, items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=999" in result
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_units_zero(self):
        ctx = _make_ctx()
        items = [{"p_id": 1, "units": 0}]
        result = await create_order(ctx, items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_units_negative(self):
        ctx = _make_ctx()
        items = [{"p_id": 1, "units": -3}]
        result = await create_order(ctx, items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_item_not_a_dict(self):
        ctx = _make_ctx()
        items = ["almendras 2 unidades"]
        result = await create_order(ctx, items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_item_missing_units_field(self):
        ctx = _make_ctx()
        items = [{"p_id": 1}]
        result = await create_order(ctx, items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_item_missing_p_id_field(self):
        ctx = _make_ctx()
        items = [{"units": 2}]
        result = await create_order(ctx, items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_multiple_errors_all_reported(self):
        """Todos los errores de todos los ítems se reportan en un solo retorno."""
        ctx = _make_ctx()
        items = [
            {"p_id": 999, "units": 2},
            {"p_id": 1, "units": 0},
        ]
        result = await create_order(ctx, items=items, delivery_address=VALID_ADDRESS)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=999" in result
        assert ctx.deps.active_order is None


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestCreateOrderHappyPath:

    def _make_session_for_create(self):
        """Session mock: first execute returns o_id=42, second is bulk insert."""
        session = AsyncMock()
        order_result = MagicMock()
        order_result.scalar.return_value = 42
        session.execute.side_effect = [order_result, MagicMock()]
        return session

    @pytest.mark.asyncio
    async def test_creates_order_and_sets_active_order(self):
        session = self._make_session_for_create()
        ctx = _make_ctx()
        fake_order = OrderRow(
            o_id=42, o_total=Decimal("0"), o_subtotal=Decimal("0"),
            o_shipping_amount=Decimal("20"), o_currency="MXN", o_customer_notes="", o_status="PENDING_STORE_APPROVAL",
        )

        with patch("yalti.get_session", _make_get_session(session)), \
             patch("yalti.order_summary", new=AsyncMock(return_value="🛍️ Resumen del pedido")), \
             patch("yalti.load_order", new=AsyncMock(return_value=fake_order)), \
             patch("yalti._send_whatsapp_text"):
            result = await create_order(ctx, items=VALID_ITEMS, delivery_address=VALID_ADDRESS)

        assert result == "🛍️ Resumen del pedido"
        assert ctx.deps.active_order is not None
        assert ctx.deps.active_order.o_id == 42
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_active_order_stays_none_after_validation_error(self):
        """Garantiza idempotencia: si falla validación, active_order no se toca."""
        ctx = _make_ctx()
        assert ctx.deps.active_order is None
        await create_order(ctx, items=[], delivery_address=VALID_ADDRESS)
        assert ctx.deps.active_order is None

    @pytest.mark.asyncio
    async def test_db_exception_returns_error_interno(self):
        """Si la DB falla, retorna ERROR_INTERNO sin propagar la excepción."""
        session = AsyncMock()
        session.execute.side_effect = Exception("DB connection lost")
        ctx = _make_ctx()

        with patch("yalti.get_session", _make_get_session(session)):
            result = await create_order(ctx, items=VALID_ITEMS, delivery_address=VALID_ADDRESS)

        assert result.startswith("ERROR_INTERNO:")
        assert ctx.deps.active_order is None
