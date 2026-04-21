"""Tests for update_order tool in yalti.py.

Validation failures return before opening a DB session.
Happy path and DB-error cases mock Session.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
_db_dir = os.path.normpath(os.path.join(_chatbot_dir, "..", "database"))
for _p in [_chatbot_dir, _db_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import MagicMock, call, patch

import pytest
from yalti import ChatDeps, StoreInfo, update_order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(active_order_id=99):
    customer = MagicMock()
    customer.c_id = 1
    customer.c_name = "Test User"
    deps = ChatDeps(
        customer=customer,
        store=StoreInfo(s_id=1, name="Test Store", description="", properties={}),
        products="",
        active_order_id=active_order_id,
    )
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


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


def _make_session(existing_item=None, order_items_after=None):
    """Construye un mock de Session listo para usar como context manager."""
    mock_order = MagicMock()
    mock_order.o_id = 99

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.get.return_value = mock_order
    mock_session.exec.return_value.first.return_value = existing_item

    # Segunda llamada a exec (all_items tras flush) devuelve la lista post-operación
    if order_items_after is not None:
        mock_session.exec.return_value.all.return_value = order_items_after

    return mock_session, mock_order


def _make_item(p_id, units, unit_price):
    item = MagicMock()
    item.oi_p_id = p_id
    item.oi_units = units
    item.oi_unit_price = unit_price
    return item


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
        ctx = _make_ctx()
        existing = _make_item(1, 2, 120.0)
        remaining = [_make_item(2, 1, 95.0)]  # queda un ítem
        mock_session, _ = _make_session(existing_item=existing, order_items_after=remaining)

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="remove", p_id=1, units=0)

        assert not result.startswith("ERROR_VALIDACION:")


# ---------------------------------------------------------------------------
# Validaciones en DB (ítem no existe, orden vacía)
# ---------------------------------------------------------------------------

class TestUpdateOrderDbValidations:

    @pytest.mark.asyncio
    async def test_reduce_units_item_not_in_order(self):
        ctx = _make_ctx()
        mock_session, _ = _make_session(existing_item=None)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session):
            result = await update_order(ctx, action="reduce_units", p_id=1, units=1)
        assert result.startswith("ERROR_VALIDACION:")
        assert "p_id=1" in result

    @pytest.mark.asyncio
    async def test_set_units_item_not_in_order(self):
        ctx = _make_ctx()
        mock_session, _ = _make_session(existing_item=None)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session):
            result = await update_order(ctx, action="set_units", p_id=1, units=2)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_remove_item_not_in_order(self):
        ctx = _make_ctx()
        mock_session, _ = _make_session(existing_item=None)
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session):
            result = await update_order(ctx, action="remove", p_id=1, units=0)
        assert result.startswith("ERROR_VALIDACION:")

    @pytest.mark.asyncio
    async def test_order_not_found_in_db(self):
        ctx = _make_ctx()
        mock_session, _ = _make_session()
        mock_session.get.return_value = None  # orden no existe
        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session):
            result = await update_order(ctx, action="add", p_id=1, units=1)
        assert result.startswith("ERROR_INTERNO:")

    @pytest.mark.asyncio
    async def test_last_item_removal_blocked(self):
        """Eliminar el único ítem debe rechazarse con ERROR_VALIDACION y hacer rollback."""
        ctx = _make_ctx()
        existing = _make_item(1, 2, 120.0)
        mock_session, _ = _make_session(existing_item=existing, order_items_after=[])

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session):
            result = await update_order(ctx, action="remove", p_id=1, units=0)

        assert result.startswith("ERROR_VALIDACION:")
        assert "cancel_order" in result
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_reduce_units_to_zero_leaves_no_items_blocked(self):
        """reduce_units que deja la orden vacía debe rechazarse."""
        ctx = _make_ctx()
        existing = _make_item(1, 2, 120.0)
        mock_session, _ = _make_session(existing_item=existing, order_items_after=[])

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session):
            result = await update_order(ctx, action="reduce_units", p_id=1, units=2)

        assert result.startswith("ERROR_VALIDACION:")
        mock_session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestUpdateOrderHappyPath:

    @pytest.mark.asyncio
    async def test_add_new_item(self):
        ctx = _make_ctx()
        new_item = _make_item(1, 2, 120.0)
        mock_session, _ = _make_session(existing_item=None, order_items_after=[new_item])

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="add", p_id=1, units=2)

        assert result == "Pedido actualizado:\nResumen"
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_existing_item_increases_units(self):
        ctx = _make_ctx()
        existing = _make_item(1, 1, 120.0)
        mock_session, _ = _make_session(existing_item=existing, order_items_after=[existing])

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="add", p_id=1, units=3)

        assert existing.oi_units == 4
        assert result == "Pedido actualizado:\nResumen"

    @pytest.mark.asyncio
    async def test_set_units(self):
        ctx = _make_ctx()
        existing = _make_item(1, 5, 120.0)
        mock_session, _ = _make_session(existing_item=existing, order_items_after=[existing])

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="set_units", p_id=1, units=2)

        assert existing.oi_units == 2
        assert result == "Pedido actualizado:\nResumen"

    @pytest.mark.asyncio
    async def test_remove_item_with_others_remaining(self):
        ctx = _make_ctx()
        existing = _make_item(1, 2, 120.0)
        remaining = [_make_item(2, 1, 95.0)]
        mock_session, _ = _make_session(existing_item=existing, order_items_after=remaining)

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session), \
             patch("yalti._order_summary", return_value="Resumen"):
            result = await update_order(ctx, action="remove", p_id=1, units=0)

        mock_session.delete.assert_called_once_with(existing)
        assert result == "Pedido actualizado:\nResumen"

    @pytest.mark.asyncio
    async def test_db_exception_returns_error_interno(self):
        ctx = _make_ctx()
        mock_session, _ = _make_session()
        mock_session.get.side_effect = Exception("DB timeout")

        with patch("yalti.PRODUCTS", FAKE_PRODUCTS), \
             patch("yalti.Session", return_value=mock_session):
            result = await update_order(ctx, action="add", p_id=1, units=1)

        assert result.startswith("ERROR_INTERNO:")
