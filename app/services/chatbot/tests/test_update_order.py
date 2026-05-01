"""Tests for the four order-item tools in yalti.py.

Validation failures return before opening a DB session.
Happy path and DB-error cases mock the AsyncSession injected into ChatDeps.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
if _chatbot_dir not in sys.path:
    sys.path.insert(0, _chatbot_dir)

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from decimal import Decimal

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


def _make_session(existing_item=None, items_after=None):
    """AsyncMock session for the four order-item tools.

    Call order: 1=SELECT item, 2=mutation (INSERT/UPDATE/DELETE),
                [3=COUNT(*) remaining — reduce/remove only],
                [4=_order_summary SELECT — patched out in happy-path tests].
    """
    session = AsyncMock()
    remaining = len(items_after) if items_after is not None else 1

    def _result(first=None, all_rows=None):
        r = MagicMock()
        r.mappings.return_value.first.return_value = first
        r.mappings.return_value.all.return_value = all_rows or []
        r.scalar.return_value = remaining
        return r

    noop = MagicMock()
    session.execute.side_effect = [
        _result(first=existing_item),          # SELECT item
        noop,                                   # mutation
        _result(),                              # COUNT(*) remaining (reduce/remove only)
        _result(all_rows=items_after or []),    # _order_summary SELECT (if not patched)
    ]
    return session


def _make_ctx(active_order_id=99, session=None, products=None):
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
        session=session or AsyncMock(),
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
        session = _make_session(existing_item=_item_row(p_id=1), items_after=[_item_row(p_id=2)])
        ctx = _make_ctx(session=session)
        with patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await remove_order_item(ctx, p_id=1)
        assert not result.startswith("ERROR_VALIDACION:")


# ---------------------------------------------------------------------------
# Validaciones en DB (ítem no existe, orden vacía)
# ---------------------------------------------------------------------------

class TestDbValidations:

    @pytest.mark.asyncio
    async def test_reduce_item_not_in_order(self):
        session = _make_session(existing_item=None)
        ctx = _make_ctx(session=session)
        result = await reduce_order_item(ctx, p_id=1, units=1)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=1" in result

    @pytest.mark.asyncio
    async def test_set_item_not_in_order(self):
        session = _make_session(existing_item=None)
        ctx = _make_ctx(session=session)
        result = await set_order_item_units(ctx, p_id=1, units=2)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_remove_item_not_in_order(self):
        session = _make_session(existing_item=None)
        ctx = _make_ctx(session=session)
        result = await remove_order_item(ctx, p_id=1)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_last_item_removal_blocked(self):
        """Eliminar el único ítem debe rechazarse con ERROR_VALIDACION y hacer rollback."""
        session = _make_session(existing_item=_item_row(), items_after=[])
        ctx = _make_ctx(session=session)
        result = await remove_order_item(ctx, p_id=1)
        assert result.startswith("ERROR_VALIDACION:")
        assert "cancel_order" in result
        session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_reduce_to_zero_leaves_no_items_blocked(self):
        """reduce_order_item que vacía la orden debe rechazarse."""
        session = _make_session(existing_item=_item_row(units=2), items_after=[])
        ctx = _make_ctx(session=session)
        result = await reduce_order_item(ctx, p_id=1, units=2)
        assert result.startswith("ERROR_VALIDACION:")
        session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:

    @pytest.mark.asyncio
    async def test_add_new_item(self):
        session = _make_session(existing_item=None, items_after=[_item_row()])
        ctx = _make_ctx(session=session)
        with patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await add_order_item(ctx, p_id=1, units=2)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_existing_item_increases_units(self):
        session = _make_session(existing_item=_item_row(units=1), items_after=[_item_row(units=4)])
        ctx = _make_ctx(session=session)
        with patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await add_order_item(ctx, p_id=1, units=3)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_units(self):
        session = _make_session(existing_item=_item_row(units=5), items_after=[_item_row(units=2)])
        ctx = _make_ctx(session=session)
        with patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await set_order_item_units(ctx, p_id=1, units=2)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_item_with_others_remaining(self):
        session = _make_session(
            existing_item=_item_row(p_id=1),
            items_after=[_item_row(p_id=2, unit_price=95.0)],
        )
        ctx = _make_ctx(session=session)
        with patch("yalti.order_summary", new=AsyncMock(return_value="Resumen")):
            result = await remove_order_item(ctx, p_id=1)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_exception_returns_error_interno(self):
        session = AsyncMock()
        session.execute.side_effect = Exception("DB timeout")
        ctx = _make_ctx(session=session)
        result = await add_order_item(ctx, p_id=1, units=1)
        assert result.startswith("ERROR_INTERNO:")
