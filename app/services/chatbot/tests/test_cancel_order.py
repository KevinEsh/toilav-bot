"""Tests for cancel_order tool in yalti.py.

Validaciones de estado y happy path mockean la sesión inyectada en ChatDeps.
El tool-gating (_hide_when_no_order) se prueba a nivel de prepare, no aquí.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
if _chatbot_dir not in sys.path:
    sys.path.insert(0, _chatbot_dir)

from unittest.mock import AsyncMock, MagicMock

import pytest
from models import StoreRow
from yalti import ChatDeps, cancel_order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(order_row=None):
    """AsyncMock session whose execute() returns the given row dict or None."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = order_row
    mock_session.execute.return_value = mock_result
    return mock_session


def _make_ctx(active_order_id=99, session=None):
    customer = MagicMock()
    customer.c_id = 1
    customer.c_name = "Test User"
    deps = ChatDeps(
        customer=customer,
        store=StoreRow(s_id=1, s_name="Test Store", s_description=""),
        products="",
        session=session or AsyncMock(),
        active_order_id=active_order_id,
    )
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _order_row(o_id=99, status="pending_store_approval"):
    return {"o_id": o_id, "o_status": status}


# ---------------------------------------------------------------------------
# Validaciones en DB
# ---------------------------------------------------------------------------

class TestCancelOrderDbValidations:

    @pytest.mark.asyncio
    async def test_order_not_found_in_db(self):
        """execute retorna None → ERROR_INTERNO, no AttributeError."""
        session = _make_session(order_row=None)
        ctx = _make_ctx(active_order_id=99, session=session)

        result = await cancel_order(ctx)

        assert result.startswith("ERROR_INTERNO:")
        assert "o_id=99" in result
        session.commit.assert_not_called()
        assert ctx.deps.active_order_id == 99

    @pytest.mark.asyncio
    async def test_order_already_cancelled(self):
        """Orden ya cancelada → ERROR_VALIDACION, sin commit."""
        session = _make_session(order_row=_order_row(status="cancelled"))
        ctx = _make_ctx(session=session)

        result = await cancel_order(ctx)

        assert result.startswith("ERROR_VALIDACION:")
        assert "cancelled" in result
        session.commit.assert_not_called()
        assert ctx.deps.active_order_id == 99

    @pytest.mark.asyncio
    async def test_order_already_completed(self):
        """Orden completada → ERROR_VALIDACION, sin commit."""
        session = _make_session(order_row=_order_row(status="completed"))
        ctx = _make_ctx(session=session)

        result = await cancel_order(ctx)

        assert result.startswith("ERROR_VALIDACION:")
        assert "completed" in result
        session.commit.assert_not_called()
        assert ctx.deps.active_order_id == 99


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestCancelOrderHappyPath:

    @pytest.mark.asyncio
    async def test_cancel_pending_approval_order(self):
        session = _make_session(order_row=_order_row(status="pending_store_approval"))
        ctx = _make_ctx(session=session)

        result = await cancel_order(ctx)

        session.commit.assert_called_once()
        assert ctx.deps.active_order_id is None
        assert "cancelado" in result
        assert "o_id=99" in result

    @pytest.mark.asyncio
    async def test_cancel_consumer_reviewing_order(self):
        session = _make_session(order_row=_order_row(status="consumer_reviewing"))
        ctx = _make_ctx(session=session)

        result = await cancel_order(ctx)

        session.commit.assert_called_once()
        assert ctx.deps.active_order_id is None
        assert "cancelado" in result


# ---------------------------------------------------------------------------
# Error interno
# ---------------------------------------------------------------------------

class TestCancelOrderDbException:

    @pytest.mark.asyncio
    async def test_db_exception_on_execute_returns_error_interno(self):
        session = AsyncMock()
        session.execute.side_effect = Exception("DB timeout")
        ctx = _make_ctx(session=session)

        result = await cancel_order(ctx)

        assert result.startswith("ERROR_INTERNO:")
        assert ctx.deps.active_order_id == 99

    @pytest.mark.asyncio
    async def test_db_exception_on_commit_returns_error_interno(self):
        session = _make_session(order_row=_order_row(status="pending_store_approval"))
        session.commit.side_effect = Exception("connection lost")
        ctx = _make_ctx(session=session)

        result = await cancel_order(ctx)

        assert result.startswith("ERROR_INTERNO:")
        assert ctx.deps.active_order_id == 99
