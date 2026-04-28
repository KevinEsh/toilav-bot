"""Tests for order_summary helper in yalti.py.

Tests async order_summary(session, o_id, c_name) using a mocked AsyncSession.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
if _chatbot_dir not in sys.path:
    sys.path.insert(0, _chatbot_dir)

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from yalti import order_summary


def _make_session(rows=None):
    """AsyncMock session that returns given rows from execute().mappings().all()."""
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows or []
    session.execute.return_value = result
    return session


def _make_row(o_total=120.0, o_customer_notes="Calle 15", p_name="Almendras",
              oi_units=1, p_subtotal=120.0):
    return {
        "o_total": o_total,
        "o_subtotal": o_total,
        "o_customer_notes": o_customer_notes,
        "p_name": p_name,
        "oi_units": oi_units,
        "p_subtotal": p_subtotal,
    }


# ---------------------------------------------------------------------------
# Empty order
# ---------------------------------------------------------------------------

class TestOrderSummaryEmptyOrder:

    @pytest.mark.asyncio
    async def test_empty_order_returns_sin_items(self):
        session = _make_session(rows=[])
        result = await order_summary(session, o_id=99, c_name="Juan")
        assert "(sin ítems)" in result
        assert "Juan" in result
        assert "Total: $0" in result

    @pytest.mark.asyncio
    async def test_empty_order_includes_order_id(self):
        session = _make_session(rows=[])
        result = await order_summary(session, o_id=42, c_name="María")
        assert "#42" in result


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestOrderSummaryHappyPath:

    @pytest.mark.asyncio
    async def test_single_item(self):
        rows = [_make_row(o_total=120.0, p_name="Almendras", oi_units=1, p_subtotal=120.0)]
        session = _make_session(rows=rows)
        result = await order_summary(session, o_id=1, c_name="Juan López")
        assert "Juan López" in result
        assert "1x Almendras — $120" in result
        assert "Total: $120" in result
        assert "Calle 15" in result

    @pytest.mark.asyncio
    async def test_multiple_items(self):
        rows = [
            _make_row(o_total=335.0, o_customer_notes="Av. 5", p_name="Almendras",
                      oi_units=2, p_subtotal=240.0),
            _make_row(o_total=335.0, o_customer_notes="Av. 5", p_name="Pistaches",
                      oi_units=1, p_subtotal=95.0),
        ]
        session = _make_session(rows=rows)
        result = await order_summary(session, o_id=5, c_name="María")
        assert "2x Almendras — $240" in result
        assert "1x Pistaches — $95" in result
        assert "Total: $335" in result

    @pytest.mark.asyncio
    async def test_decimal_total(self):
        rows = [_make_row(o_total=Decimal("240.00"), p_name="X", oi_units=2, p_subtotal=240.0)]
        session = _make_session(rows=rows)
        result = await order_summary(session, o_id=1, c_name="Test")
        assert "Total: $240" in result
