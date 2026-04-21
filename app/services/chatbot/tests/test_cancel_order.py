"""Tests for cancel_order tool in yalti.py.

Validaciones de estado y happy path mockean Session.
El tool-gating (_hide_when_no_order) se prueba a nivel de prepare, no aquí.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
_db_dir = os.path.normpath(os.path.join(_chatbot_dir, "..", "database"))
for _p in [_chatbot_dir, _db_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import MagicMock, patch

import pytest
from chatbot_schema import OrderStatus
from yalti import ChatDeps, StoreInfo, cancel_order


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


def _make_session(order=None):
    """Construye un mock de Session listo para usar como context manager."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.get.return_value = order
    return mock_session


def _make_order(o_id=99, status=OrderStatus.PENDING_STORE_APPROVAL):
    order = MagicMock()
    order.o_id = o_id
    order.o_status = status
    return order


# ---------------------------------------------------------------------------
# Validaciones en DB
# ---------------------------------------------------------------------------

class TestCancelOrderDbValidations:

    @pytest.mark.asyncio
    async def test_order_not_found_in_db(self):
        """session.get retorna None → ERROR_INTERNO, no AttributeError."""
        ctx = _make_ctx(active_order_id=99)
        mock_session = _make_session(order=None)
        with patch("yalti.Session", return_value=mock_session):
            result = await cancel_order(ctx)
        assert result.startswith("ERROR_INTERNO:")
        assert "o_id=99" in result
        mock_session.commit.assert_not_called()
        assert ctx.deps.active_order_id == 99  # no se tocó

    @pytest.mark.asyncio
    async def test_order_already_cancelled(self):
        """Orden ya cancelada → ERROR_VALIDACION, sin commit."""
        ctx = _make_ctx(active_order_id=99)
        order = _make_order(status=OrderStatus.CANCELLED)
        mock_session = _make_session(order=order)
        with patch("yalti.Session", return_value=mock_session):
            result = await cancel_order(ctx)
        assert result.startswith("ERROR_VALIDACION:")
        assert "cancelled" in result
        mock_session.commit.assert_not_called()
        assert ctx.deps.active_order_id == 99

    @pytest.mark.asyncio
    async def test_order_already_completed(self):
        """Orden completada → ERROR_VALIDACION, sin commit."""
        ctx = _make_ctx(active_order_id=99)
        order = _make_order(status=OrderStatus.COMPLETED)
        mock_session = _make_session(order=order)
        with patch("yalti.Session", return_value=mock_session):
            result = await cancel_order(ctx)
        assert result.startswith("ERROR_VALIDACION:")
        assert "completed" in result
        mock_session.commit.assert_not_called()
        assert ctx.deps.active_order_id == 99


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestCancelOrderHappyPath:

    @pytest.mark.asyncio
    async def test_cancel_pending_approval_order(self):
        ctx = _make_ctx(active_order_id=99)
        order = _make_order(status=OrderStatus.PENDING_STORE_APPROVAL)
        mock_session = _make_session(order=order)
        with patch("yalti.Session", return_value=mock_session):
            result = await cancel_order(ctx)

        assert order.o_status == OrderStatus.CANCELLED
        mock_session.add.assert_called_once_with(order)
        mock_session.commit.assert_called_once()
        assert ctx.deps.active_order_id is None
        assert "cancelado" in result
        assert "o_id=99" in result

    @pytest.mark.asyncio
    async def test_cancel_consumer_reviewing_order(self):
        ctx = _make_ctx(active_order_id=99)
        order = _make_order(status=OrderStatus.CONSUMER_REVIEWING)
        mock_session = _make_session(order=order)
        with patch("yalti.Session", return_value=mock_session):
            result = await cancel_order(ctx)

        assert order.o_status == OrderStatus.CANCELLED
        mock_session.commit.assert_called_once()
        assert ctx.deps.active_order_id is None
        assert "cancelado" in result


# ---------------------------------------------------------------------------
# Error interno
# ---------------------------------------------------------------------------

class TestCancelOrderDbException:

    @pytest.mark.asyncio
    async def test_db_exception_on_get_returns_error_interno(self):
        ctx = _make_ctx(active_order_id=99)
        mock_session = _make_session()
        mock_session.get.side_effect = Exception("DB timeout")
        with patch("yalti.Session", return_value=mock_session):
            result = await cancel_order(ctx)

        assert result.startswith("ERROR_INTERNO:")
        assert ctx.deps.active_order_id == 99  # no se limpió

    @pytest.mark.asyncio
    async def test_db_exception_on_commit_returns_error_interno(self):
        ctx = _make_ctx(active_order_id=99)
        order = _make_order(status=OrderStatus.PENDING_STORE_APPROVAL)
        mock_session = _make_session(order=order)
        mock_session.commit.side_effect = Exception("connection lost")
        with patch("yalti.Session", return_value=mock_session):
            result = await cancel_order(ctx)

        assert result.startswith("ERROR_INTERNO:")
        assert ctx.deps.active_order_id == 99  # no se limpió
