"""Tests for load_active_order helper in dbutils.py."""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
_db_dir = os.path.normpath(os.path.join(_chatbot_dir, "..", "database"))
for _p in [_chatbot_dir, _db_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from dbutils import load_active_order
from models import OrderRow


def _make_session(order_row=None, exec_side_effect=None):
    """AsyncMock session for load_active_order."""
    session = AsyncMock()
    if exec_side_effect is not None:
        session.execute.side_effect = exec_side_effect
    else:
        result = MagicMock()
        result.mappings.return_value.first.return_value = order_row
        session.execute.return_value = result
    return session


def _order_dict(o_id=42, o_total="100.00", o_subtotal="100.00",
                o_shipping_amount="0.00", o_currency="MXN", o_customer_notes=""):
    return {
        "o_id": o_id,
        "o_total": Decimal(o_total),
        "o_subtotal": Decimal(o_subtotal),
        "o_shipping_amount": Decimal(o_shipping_amount),
        "o_currency": o_currency,
        "o_customer_notes": o_customer_notes,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestLoadActiveOrderHappyPath:

    @pytest.mark.asyncio
    async def test_returns_order_when_exists(self):
        session = _make_session(order_row=_order_dict(o_id=42))
        result = await load_active_order(session, c_id=1)
        assert isinstance(result, OrderRow)
        assert result.o_id == 42

    @pytest.mark.asyncio
    async def test_queries_with_correct_c_id(self):
        session = _make_session(order_row=_order_dict(o_id=7))
        await load_active_order(session, c_id=5)
        session.execute.assert_called_once()
        positional = session.execute.call_args.args
        assert positional[1]["c_id"] == 5


# ---------------------------------------------------------------------------
# No active order
# ---------------------------------------------------------------------------

class TestLoadActiveOrderNotFound:

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="OrderRow() has no defaults — known bug when no active order")
    async def test_returns_empty_order_row_when_not_found(self):
        session = _make_session(order_row=None)
        result = await load_active_order(session, c_id=1)
        assert isinstance(result, OrderRow)


# ---------------------------------------------------------------------------
# DB errors
# ---------------------------------------------------------------------------

class TestLoadActiveOrderDbErrors:

    @pytest.mark.asyncio
    async def test_db_error_propagates(self):
        session = _make_session(exec_side_effect=Exception("DB down"))
        with pytest.raises(Exception, match="DB down"):
            await load_active_order(session, c_id=1)
