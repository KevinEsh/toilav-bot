"""Tests for upsert_customer in dbutils.py.

Tests async upsert_customer(session, whatsapp_id, phone, name) using a mocked AsyncSession.
Uses ON CONFLICT DO UPDATE — no manual race handling needed.
"""

import os
import sys

_chatbot_dir = os.path.join(os.path.dirname(__file__), "..")
_db_dir = os.path.normpath(os.path.join(_chatbot_dir, "..", "database"))
for _p in [_chatbot_dir, _db_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unittest.mock import AsyncMock, MagicMock

import pytest

from dbutils import upsert_customer
from models import CustomerRow


def _make_session(customer_row=None, exec_side_effect=None):
    """AsyncMock session that returns given row from execute().mappings().first()."""
    session = AsyncMock()
    if exec_side_effect is not None:
        session.execute.side_effect = exec_side_effect
    else:
        result = MagicMock()
        result.mappings.return_value.first.return_value = customer_row
        session.execute.return_value = result
    return session


def _customer_dict(c_id=1, c_name="Juan", c_whatsapp_id="5215512345678"):
    return {"c_id": c_id, "c_name": c_name, "c_whatsapp_id": c_whatsapp_id}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestUpsertCustomerHappyPath:

    @pytest.mark.asyncio
    async def test_returns_customer_row(self):
        session = _make_session(customer_row=_customer_dict())
        result = await upsert_customer(session, "5215512345678", "5215512345678", "Juan")
        assert isinstance(result, CustomerRow)
        assert result.c_id == 1
        assert result.c_name == "Juan"
        assert result.c_whatsapp_id == "5215512345678"

    @pytest.mark.asyncio
    async def test_passes_whatsapp_id_and_name(self):
        session = _make_session(customer_row=_customer_dict(c_name="María", c_whatsapp_id="52999"))
        await upsert_customer(session, "52999", "52999", "María")
        session.execute.assert_called_once()
        args_dict = session.execute.call_args.args[1]
        assert args_dict["whatsapp_id"] == "52999"
        assert args_dict["name"] == "María"

    @pytest.mark.asyncio
    async def test_passes_phone_separately(self):
        session = _make_session(customer_row=_customer_dict())
        await upsert_customer(session, "521111", "5521111", "Test")
        args_dict = session.execute.call_args.args[1]
        assert args_dict["whatsapp_id"] == "521111"
        assert args_dict["c_phone"] == "5521111"

    @pytest.mark.asyncio
    async def test_existing_customer_returned(self):
        """ON CONFLICT → existing customer is returned (DB handles idempotency)."""
        existing = _customer_dict(c_id=99, c_name="Existente")
        session = _make_session(customer_row=existing)
        result = await upsert_customer(session, "521", "521", "Existente")
        assert result.c_id == 99


# ---------------------------------------------------------------------------
# DB errors
# ---------------------------------------------------------------------------

class TestUpsertCustomerDbErrors:

    @pytest.mark.asyncio
    async def test_db_error_propagates(self):
        session = _make_session(exec_side_effect=Exception("DB error"))
        with pytest.raises(Exception, match="DB error"):
            await upsert_customer(session, "521", "521", "Test")
