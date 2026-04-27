"""Tests for update_order tool in yalti.py.

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
from yalti import ChatDeps, StoreInfo, update_order


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

_ORDER_ROW = {"o_id": 99, "o_customer_notes": "notas test"}


def _make_session(order_row=_ORDER_ROW, existing_item=None, items_after=None):
    """AsyncMock session configured for the execute() call sequence in update_order.

    Call order: 1=SELECT order, 2=SELECT existing item, 3=mutation (UPDATE/INSERT/DELETE),
                4=SELECT all items, 5=UPDATE order totals.
    """
    session = AsyncMock()

    def _result(first=None, all_rows=None):
        r = MagicMock()
        r.mappings.return_value.first.return_value = first
        r.mappings.return_value.all.return_value = all_rows or []
        return r

    noop = _result()  # used for write statements (no return value consumed)
    session.execute.side_effect = [
        _result(first=order_row),        # SELECT order
        _result(first=existing_item),    # SELECT existing item
        noop,                            # mutation (UPDATE/INSERT/DELETE)
        _result(all_rows=items_after or []),  # SELECT all items
        noop,                            # UPDATE order totals
    ]
    return session


def _make_ctx(active_order_id=99, session=None):
    customer = MagicMock()
    customer.c_id = 1
    customer.c_name = "Test User"
    deps = ChatDeps(
        customer=customer,
        store=StoreInfo(s_id=1, name="Test Store", description="", properties={}),
        products="",
        session=session or AsyncMock(),
        active_order_id=active_order_id,
    )
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _item_row(p_id=1, units=2, unit_price=120.0, oi_id=1):
    return {"oi_id": oi_id, "oi_p_id": p_id, "oi_units": units, "oi_unit_price": unit_price}


# ---------------------------------------------------------------------------
# Validaciones de entrada (sin DB)
# ---------------------------------------------------------------------------

class TestUpdateOrderValidations:

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        ctx = _make_ctx()
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="borrar", p_id=1, units=1)
        assert result.startswith("ERROR_VALIDACION:")
        assert "borrar" in result

    @pytest.mark.asyncio
    async def test_unknown_p_id(self):
        ctx = _make_ctx()
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="add", p_id=999, units=1)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=999" in result

    @pytest.mark.asyncio
    async def test_add_units_zero(self):
        ctx = _make_ctx()
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="add", p_id=1, units=0)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_add_units_negative(self):
        ctx = _make_ctx()
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="add", p_id=1, units=-2)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_reduce_units_zero(self):
        ctx = _make_ctx()
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="reduce_units", p_id=1, units=0)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_set_units_zero(self):
        ctx = _make_ctx()
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="set_units", p_id=1, units=0)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_remove_ignores_units_value(self):
        """remove no requiere units >= 1 — la validación no aplica."""
        session = _make_session(
            existing_item=_item_row(p_id=1),
            items_after=[_item_row(p_id=2)],
        )
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="remove", p_id=1, units=0)
        assert not result.startswith("ERROR_VALIDACION:")


# ---------------------------------------------------------------------------
# Validaciones en DB (ítem no existe, orden vacía)
# ---------------------------------------------------------------------------

class TestUpdateOrderDbValidations:

    @pytest.mark.asyncio
    async def test_reduce_units_item_not_in_order(self):
        session = _make_session(existing_item=None)
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="reduce_units", p_id=1, units=1)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=1" in result

    @pytest.mark.asyncio
    async def test_set_units_item_not_in_order(self):
        session = _make_session(existing_item=None)
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="set_units", p_id=1, units=2)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_remove_item_not_in_order(self):
        session = _make_session(existing_item=None)
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="remove", p_id=1, units=0)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_order_not_found_in_db(self):
        session = _make_session(order_row=None)
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="add", p_id=1, units=1)
        assert result.startswith("ERROR_INTERNO:")

    @pytest.mark.asyncio
    async def test_last_item_removal_blocked(self):
        """Eliminar el único ítem debe rechazarse con ERROR_VALIDACION y hacer rollback."""
        session = _make_session(existing_item=_item_row(), items_after=[])
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="remove", p_id=1, units=0)
        assert result.startswith("ERROR_VALIDACION:")
        assert "cancel_order" in result
        session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_reduce_units_to_zero_leaves_no_items_blocked(self):
        """reduce_units que deja la orden vacía debe rechazarse."""
        session = _make_session(existing_item=_item_row(units=2), items_after=[])
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="reduce_units", p_id=1, units=2)
        assert result.startswith("ERROR_VALIDACION:")
        session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestUpdateOrderHappyPath:

    @pytest.mark.asyncio
    async def test_add_new_item(self):
        session = _make_session(existing_item=None, items_after=[_item_row()])
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="add", p_id=1, units=2)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_existing_item_increases_units(self):
        session = _make_session(existing_item=_item_row(units=1), items_after=[_item_row(units=4)])
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="add", p_id=1, units=3)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_units(self):
        session = _make_session(existing_item=_item_row(units=5), items_after=[_item_row(units=2)])
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="set_units", p_id=1, units=2)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_item_with_others_remaining(self):
        session = _make_session(
            existing_item=_item_row(p_id=1),
            items_after=[_item_row(p_id=2, unit_price=95.0)],
        )
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="remove", p_id=1, units=0)
        assert result == "Pedido actualizado:\nResumen"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_exception_returns_error_interno(self):
        session = AsyncMock()
        session.execute.side_effect = Exception("DB timeout")
        ctx = _make_ctx(session=session)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS):
            result = await update_order(ctx, action="add", p_id=1, units=1)
        assert result.startswith("ERROR_INTERNO:")
