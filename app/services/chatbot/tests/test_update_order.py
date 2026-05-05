"""Tests for the four order-item tools in yalti.py.

Validation failures return before opening a DB session.
Happy path and DB-error cases patch yalti.get_session with a mock session.

Note: reduce_order_item and remove_order_item now COUNT before mutating
(check-before-delete), so the execute call order is:
  SELECT item → COUNT(*) → DELETE/UPDATE → order_summary
instead of the old:
  SELECT item → DELETE/UPDATE → COUNT(*) → order_summary
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
from models import OrderItemRow, OrderRow, StoreRow
from yalti import (
    ChatDeps,
    add_order_item,
    reduce_order_item,
    remove_order_item,
    set_order_item_units,
)


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


def _make_product(p_id, name, price):
    p = MagicMock()
    p.p_id = p_id
    p.p_name = name
    p.p_sale_price = price
    return p


FAKE_PRODUCTS = {
    1: _make_product(1, "Almendras tostadas", 120.0),
    2: _make_product(2, "Pistaches", 95.0),
}


def _result(first=None, scalar=0):
    r = MagicMock()
    r.mappings.return_value.first.return_value = first
    r.scalar.return_value = scalar
    return r


def _make_ctx(active_order_id=99, products=None):
    customer = MagicMock()
    customer.c_id = 1
    customer.c_name = "Test User"
    active_order = (
        OrderRow(
            o_id=active_order_id, o_total=Decimal("0"), o_subtotal=Decimal("0"),
            o_shipping_amount=Decimal("0"), o_currency="MXN", o_customer_notes="", o_status="PENDING_STORE_APPROVAL",
        )
        if active_order_id is not None
        else None
    )
    deps = ChatDeps(
        customer=customer,
        store=StoreRow(s_id=1, s_name="Test Store"),
        products=products if products is not None else FAKE_PRODUCTS,
        active_order=active_order,
    )
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _item_row(p_id=1, units=2, unit_price=120.0, oi_id=1):
    return {"oi_id": oi_id, "oi_p_id": p_id, "oi_units": units, "oi_unit_price": unit_price}


# ---------------------------------------------------------------------------
# Validaciones de entrada (sin DB)
# ---------------------------------------------------------------------------

class TestInputValidations:

    @pytest.mark.asyncio
    async def test_add_unknown_p_id(self):
        ctx = _make_ctx()
        result = await add_order_item(ctx, p_id=999, units=1)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=999" in result

    @pytest.mark.asyncio
    async def test_add_units_zero(self):
        ctx = _make_ctx()
        result = await add_order_item(ctx, p_id=1, units=0)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_add_units_negative(self):
        ctx = _make_ctx()
        result = await add_order_item(ctx, p_id=1, units=-2)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_reduce_unknown_p_id(self):
        ctx = _make_ctx()
        result = await reduce_order_item(ctx, p_id=999, units=1)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_reduce_units_zero(self):
        ctx = _make_ctx()
        result = await reduce_order_item(ctx, p_id=1, units=0)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_set_unknown_p_id(self):
        ctx = _make_ctx()
        result = await set_order_item_units(ctx, p_id=999, units=1)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_set_units_zero(self):
        ctx = _make_ctx()
        result = await set_order_item_units(ctx, p_id=1, units=0)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_remove_unknown_p_id(self):
        ctx = _make_ctx()
        result = await remove_order_item(ctx, p_id=999)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_remove_item_works_without_units_param(self):
        """remove_order_item has no units parameter — validate it works fine."""
        session = AsyncMock()
        # SELECT item → COUNT(*) returning 2 → DELETE
        session.execute.side_effect = [
            _result(first=_item_row(p_id=1), scalar=2),  # load_orderitem
            _result(scalar=2),                            # COUNT(*)
            MagicMock(),                                  # DELETE
        ]
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)), \
             patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await remove_order_item(ctx, p_id=1)
        assert not result.startswith("ERROR_VALIDACION:")


# ---------------------------------------------------------------------------
# Validaciones en DB (ítem no existe, orden vacía)
# ---------------------------------------------------------------------------

class TestDbValidations:

    @pytest.mark.asyncio
    async def test_reduce_item_not_in_order(self):
        session = AsyncMock()
        session.execute.return_value = _result(first=None)
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)):
            result = await reduce_order_item(ctx, p_id=1, units=1)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=1" in result

    @pytest.mark.asyncio
    async def test_set_item_not_in_order(self):
        session = AsyncMock()
        session.execute.return_value = _result(first=None)
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)):
            result = await set_order_item_units(ctx, p_id=1, units=2)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_remove_item_not_in_order(self):
        session = AsyncMock()
        session.execute.return_value = _result(first=None)
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)):
            result = await remove_order_item(ctx, p_id=1)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_last_item_removal_blocked(self):
        """Eliminar el único ítem debe rechazarse con ERROR_VALIDACION."""
        session = AsyncMock()
        # SELECT item → COUNT(*) returning 1 → no DELETE
        session.execute.side_effect = [
            _result(first=_item_row(), scalar=1),  # load_orderitem
            _result(scalar=1),                      # COUNT(*) — only 1 item
        ]
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)):
            result = await remove_order_item(ctx, p_id=1)
        assert result.startswith("ERROR_VALIDACION:")
        assert "cancel_order" in result

    @pytest.mark.asyncio
    async def test_reduce_to_zero_leaves_no_items_blocked(self):
        """reduce_order_item que vacía la orden debe rechazarse."""
        session = AsyncMock()
        # SELECT item(units=2) → COUNT(*) returning 1 → no DELETE
        session.execute.side_effect = [
            _result(first=_item_row(units=2), scalar=1),  # load_orderitem
            _result(scalar=1),                             # COUNT(*) — only 1 item
        ]
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)):
            result = await reduce_order_item(ctx, p_id=1, units=2)
        assert result.startswith("ERROR_VALIDACION:")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:

    @pytest.mark.asyncio
    async def test_add_new_item(self):
        session = AsyncMock()
        session.execute.side_effect = [_result(first=None), MagicMock()]
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)), \
             patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await add_order_item(ctx, p_id=1, units=2)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_existing_item_increases_units(self):
        session = AsyncMock()
        session.execute.side_effect = [_result(first=_item_row(units=1)), MagicMock()]
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)), \
             patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await add_order_item(ctx, p_id=1, units=3)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_units(self):
        session = AsyncMock()
        session.execute.side_effect = [_result(first=_item_row(units=5)), MagicMock()]
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)), \
             patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await set_order_item_units(ctx, p_id=1, units=2)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_item_with_others_remaining(self):
        session = AsyncMock()
        # SELECT item → COUNT(*) returning 2 → DELETE
        session.execute.side_effect = [
            _result(first=_item_row(p_id=1), scalar=2),  # load_orderitem
            _result(scalar=2),                            # COUNT(*)
            MagicMock(),                                  # DELETE
        ]
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)), \
             patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await remove_order_item(ctx, p_id=1)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_exception_returns_error_interno(self):
        session = AsyncMock()
        session.execute.side_effect = Exception("DB timeout")
        ctx = _make_ctx()
        with patch("yalti.get_session", _make_get_session(session)):
            result = await add_order_item(ctx, p_id=1, units=1)
        assert result.startswith("ERROR_INTERNO:")
