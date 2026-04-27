"""
Local dataclasses for DB row results in the chatbot service.

Using plain dataclasses keeps the service decoupled from the shared ORM
schema (chatbot_schema.py). Fields map 1-to-1 to the DB column names.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CustomerRow:
    c_id: int
    c_name: str | None
    c_whatsapp_id: str
    c_phone: str | None = None


@dataclass
class StoreRow:
    s_id: int = 0
    s_name: str = ""
    s_description: str = ""
    s_rag_text: str | None = None
    # s_properties: dict = None  # type: ignore[assignment]

    # def __post_init__(self) -> None:
    #     if self.s_properties is None:
    #         self.s_properties = {}


@dataclass
class ProductRow:
    p_id: int
    p_name: str
    p_sale_price: Decimal
    p_currency: str
    p_rag_text: str | None
    p_image_url: str


@dataclass
class MessageRow:
    m_id: int


@dataclass
class OrderRow:
    o_id: int
    o_total: Decimal
    o_subtotal: Decimal
    o_shipping_amount: Decimal
    o_currency: str
    o_customer_notes: str


@dataclass
class OrderItemRow:
    oi_id: int
    oi_p_id: int
    oi_units: int
    oi_unit_price: Decimal | None = None
