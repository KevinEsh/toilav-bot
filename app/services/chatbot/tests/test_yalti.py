"""Smoke tests for yalti module public interface."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from models import StoreRow
from yalti import ChatDeps, agent_generate_response


class TestChatDeps:
    def test_creation(self):
        session = AsyncMock()
        customer = MagicMock()
        customer.c_id = 1
        customer.c_name = "Juan"
        customer.c_whatsapp_id = "521551234"
        store = StoreRow(s_id=1, s_name="Tienda", s_description="")
        deps = ChatDeps(customer=customer, store=store, products="", session=session)
        assert deps.active_order is None
        assert deps._once == set()
