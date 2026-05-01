from __future__ import annotations

import json
from collections import OrderedDict
from logging import getLogger
from time import monotonic
from typing import Callable, Coroutine, Generic, TypeVar

from database import get_session
from models import CustomerRow, OrderItemRow, OrderRow, ProductRow, StoreRow
from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = getLogger(__name__)

# ---------------------------------------------------------------------------
# Generic TTL cache — reloads from DB at most once per `ttl` seconds.
# Keeps store info and product catalog in memory so we don't hit the DB on
# every incoming message. Both change infrequently (owner-driven updates).
# ---------------------------------------------------------------------------
_T = TypeVar("_T")


class TTLCache(Generic[_T]):
    def __init__(self, loader: Callable[[], Coroutine[None, None, _T]], ttl: float = 300.0):
        self._loader = loader
        self._ttl = ttl
        self._value: _T | None = None
        self._loaded_at: float = 0.0

    async def aget(self, session) -> _T:
        if self._value is None or (monotonic() - self._loaded_at) > self._ttl:
            self._value = await self._loader(session)
            self._loaded_at = monotonic()
        return self._value

    def invalidate(self) -> None:
        """Force reload on next access (e.g., after a product update webhook)."""
        self._value = None
        self._loaded_at = 0.0


# ---------------------------------------------------------------------------
# DB helpers — short-lived sessions scoped to each operation; no connection
# held open during the (potentially slow) LLM call.
# ---------------------------------------------------------------------------
async def load_store(session) -> StoreRow:
    # async with get_session() as session:
    get_store = text("""
        SELECT s_id, s_name, s_description, s_rag_text
        FROM stores LIMIT 1
    """)
    result = await session.execute(get_store)
    row = result.mappings().first()
    if row is None:
        logger.warning("No store record found in DB, using empty StoreRow")
        return StoreRow()
    return StoreRow(**row)


async def load_orderitem(session: AsyncSession, o_id: int, p_id: int):
    result = await session.execute(
        text(
            "SELECT oi_id, oi_p_id, oi_units, oi_unit_price FROM orderitems WHERE oi_o_id = :o_id AND oi_p_id = :p_id"
        ),
        {"o_id": o_id, "p_id": p_id},
    )
    orderitem = result.mappings().first()
    if orderitem is None:
        return None
    return OrderItemRow(**orderitem)


async def order_summary(session: AsyncSession, o_id: int, c_name: str) -> str:
    """Consulta la DB y construye el resumen del pedido."""

    get_order_summary_query = text("""
        SELECT o_total, o_subtotal, o_customer_notes, p_name, oi_units, oi_units * oi_unit_price as p_subtotal
        FROM orderitems
        JOIN orders on o_id = oi_o_id
        JOIN products on p_id = oi_p_id
        WHERE oi_o_id = :o_id
    """)

    result = await session.execute(get_order_summary_query, {"o_id": o_id})
    oi_summary = result.mappings().all()

    if not oi_summary:
        return f"🛍️ Orden #{o_id} — {c_name}\n\n(sin ítems)\n\nTotal: $0"

    lines = []
    for oi in oi_summary:
        lines.append(f"• {oi['oi_units']}x {oi['p_name']} — ${oi['p_subtotal']:.0f}")

    return (
        f"🛍️ Orden #{o_id} — {c_name}\n\n"
        + "\n".join(lines)
        + f"\n\nTotal: ${oi_summary[0]['o_total']:.0f}\n\n📍"
        + f"{oi_summary[0]['o_customer_notes']}"
    )


async def load_active_order(session, c_id):
    get_active_order_query = text("""
        SELECT o_id, o_total, o_subtotal, o_shipping_amount, o_currency, o_customer_notes, o_status
        FROM orders
        WHERE o_c_id = :c_id
            AND o_status NOT IN ('CANCELLED', 'COMPLETED')
        ORDER BY o_created_at DESC
        LIMIT 1
    """)

    result = await session.execute(get_active_order_query, {"c_id": c_id})
    order = result.mappings().first()

    if order is None:
        return None

    logger.info("Active order found in DB")
    return OrderRow(**order)


async def load_order(session, o_id: int):
    get_order_query = text("""
        SELECT o_id, o_total, o_subtotal, o_shipping_amount, o_currency, o_customer_notes, o_status
        FROM orders WHERE o_id = :o_id
    """)

    result = await session.execute(get_order_query, {"o_id": o_id})
    order = result.mappings().first()

    if order is None:
        return None

    logger.info("load_order[{o_id=}]: order found in DB")
    return OrderRow(**order)


async def load_products(session) -> dict[str, ProductRow]:
    """Lee todos los productos disponibles (pre-computado en la API)."""
    # async with get_session() as session:
    get_products_query = text("""
        SELECT p_id, p_name, p_sale_price, p_rag_text, p_currency, p_image_url
        FROM products WHERE p_is_available = true
    """)

    result = await session.execute(get_products_query)
    rows = result.mappings().all()
    if not rows:
        logger.warning("No products records found in DB, using empty dict")
        return {}
    return {r["p_id"]: ProductRow(**r) for r in rows}

    # Almacena en Yalti para acceso rápido durante la generación de respuestas
    # yalti.PRODUCTS = {r["p_id"]: ProductRow(**r) for r in rows}
    # return "\n".join(r["p_rag_text"] for r in rows if r["p_rag_text"])


# TODO: definir si se va a utulizar
async def load_customers() -> dict[str, CustomerRow]:
    """Carga un dict de c_id → CustomerRow para todos los clientes registrados."""
    async with get_session() as session:
        get_customers_query = text("SELECT c_id, c_name, c_whatsapp_id FROM customers")
        result = await session.execute(get_customers_query)
        rows = result.mappings().all()

    return {r["c_whatsapp_id"]: CustomerRow(**r) for r in rows}


store_cache: TTLCache[StoreRow] = TTLCache(loader=load_store, ttl=300.0)
products_cache: TTLCache[dict[str, ProductRow]] = TTLCache(loader=load_products, ttl=300.0)
# customer_cache: TTLCache[dict[str, CustomerRow]] = TTLCache(loader=load_customers, ttl=300.0)


async def upsert_customer(session, whatsapp_id: str, phone: str, name: str) -> CustomerRow:
    """Upserts a customer by whatsapp_id and returns the row. Single query via ON CONFLICT."""

    # async with get_session() as session:
    upsert_customer_query = text("""
        INSERT INTO customers (c_phone, c_whatsapp_id, c_name, c_status)
        VALUES (:c_phone, :whatsapp_id, :name, :c_status)
        ON CONFLICT (c_whatsapp_id) DO UPDATE SET c_name = EXCLUDED.c_name
        RETURNING c_id, c_name, c_whatsapp_id
    """)

    args = {"whatsapp_id": whatsapp_id, "c_phone": phone, "name": name, "c_status": "ACTIVE"}
    result = await session.execute(upsert_customer_query, args)
    row = result.mappings().first()

    return CustomerRow(**row)


# ---------------------------------------------------------------------------
# Conversation history cache — LRU in-memory cache that avoids re-reading
# + deserializing JSONB on every message for active customers.
# ---------------------------------------------------------------------------
class ConversationsCache:
    """LRU cache for deserialized pydantic-ai conversation histories, keyed by c_id."""

    def __init__(self, max_entries: int = 30):
        self._store: OrderedDict[int, list] = OrderedDict()
        self._max = max_entries

    def get(self, c_id: int) -> list | None:
        """Returns cached history or None. Promotes to MRU on hit."""
        if c_id in self._store:
            self._store.move_to_end(c_id)
            return self._store[c_id]
        return None

    def set(self, c_id: int, history: list) -> None:
        """Stores history, evicting the oldest entry if at capacity."""
        self._store[c_id] = history
        self._store.move_to_end(c_id)
        if len(self._store) > self._max:
            self._store.popitem(last=False)

    def invalidate(self, c_id: int) -> None:
        """Removes a specific entry (e.g. on conversation reset)."""
        self._store.pop(c_id, None)


conversations_cache = ConversationsCache()


# ---------------------------------------------------------------------------
# Conversation persistence — one record per customer in the conversations
# table, with full pydantic-ai history in a JSONB column.
# ---------------------------------------------------------------------------
async def load_conversation(session, c_id: int) -> list:
    """Loads the pydantic-ai message history for a customer.

    1. Check in-memory cache (hot path).
    2. Load from Conversations.cv_history (JSONB) and deserialize.
    3. If no conversation exists yet, return empty list.

    Returns a list of ModelRequest/ModelResponse ready for agent.iter().
    """
    cached = conversations_cache.get(c_id)
    if cached is not None:
        return cached

    # async with get_session() as session:
    get_consersations_query = text("SELECT cv_history FROM conversations WHERE cv_c_id = :c_id")
    args = {"c_id": c_id}
    result = await session.execute(get_consersations_query, args)
    row = result.mappings().first()

    if row is None or not row["cv_history"]:
        return []

    history = ModelMessagesTypeAdapter.validate_python(row["cv_history"])
    conversations_cache.set(c_id, history)
    return history


async def update_conversation(session, c_id: int, history: list) -> None:
    """Persists the full pydantic-ai message history to the conversations table."""
    serialized = json.dumps(to_jsonable_python(history))

    # async with get_session() as session:
    update_conversation_query = text("""
        UPDATE conversations
        SET cv_history = :cv_history
        WHERE cv_c_id = :cv_c_id
    """)
    args = {"cv_c_id": c_id, "cv_history": serialized}
    await session.execute(update_conversation_query, args)

    # TODO: move this outside the function to improve code clarity
    conversations_cache.set(c_id, history)


async def insert_message(
    session,
    c_id: int,
    direction: str,
    content: str,
    status: str = "RECEIVED",
    msg_type: str = "TEXT",
) -> int:
    """Persiste un único mensaje en la DB y retorna el m_id creado."""
    # async with get_session() as session:
    insert_message_query = text("""
        INSERT INTO messages (m_c_id, m_direction, m_type, m_content, m_status)
        VALUES (:m_c_id, :m_direction, :m_type, :m_content, :m_status)
        RETURNING m_id
    """)
    args = {
        "m_c_id": c_id,
        "m_direction": direction,
        "m_type": msg_type,
        "m_content": content,
        "m_status": status,
    }
    result = await session.execute(insert_message_query, args)
    m_id = result.scalar()

    return m_id


async def update_message_status(session, m_id: int, status: str) -> None:
    """Actualiza el status de un mensaje existente."""
    # async with get_session() as session:
    update_message_status_query = text("""
        UPDATE messages SET m_status = :m_status WHERE m_id = :m_id
    """)
    args = {"m_status": status, "m_id": m_id}
    await session.execute(update_message_status_query, args)
