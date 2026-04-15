from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from chatbot_schema import Customers, OrderItems, Orders, OrderStatus
from config import settings
from database import engine
from pydantic_ai import Agent, RunContext
from rules import ChatOutput, build_mega_prompt
from sqlmodel import Session, select

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Store and conversation dependencies
# ---------------------------------------------------------------------------
@dataclass
class StoreInfo:
    """Store information loaded from DB."""

    s_id: int
    name: str
    description: str
    properties: dict


@dataclass
class ChatDeps:
    """Agent dependencies injected on every run."""

    wa_id: str
    customer: Customers
    store: StoreInfo
    products: str  # formatted product catalog injected into the system prompt




# ---------------------------------------------------------------------------
# Dummy product catalog — kept for local testing without DB products.
# NOT registered as an agent tool; use the system prompt catalog instead.
# ---------------------------------------------------------------------------
_DUMMY_PRODUCTS = """\
Productos disponibles en Tremenda Nuez:

• Almendras tostadas — $120/200g, $220/500g
• Nueces de la india (cashews) — $85/100g, $160/200g
• Nueces de Castilla — $75/150g
• Pistaches con sal — $95/100g
• Arándanos deshidratados — $65/100g
• Mix de frutos secos (almendras + nueces + arándanos) — $130/200g

Métodos de pago: transferencia bancaria, efectivo al recibir.
Zonas de entrega: ciudad de Guanajuato y área metropolitana.
Tiempo de entrega: 24–48 horas hábiles.
Pedido mínimo: $150.
"""


async def search_products(ctx: RunContext[ChatDeps], query: str) -> str:
    """Búsqueda de productos — deshabilitado, el catálogo ya está en el system prompt.

    Args:
        query: La pregunta o tema a buscar.
    """
    logger.info("Product search from %s: %s", ctx.deps.wa_id, query)
    return _DUMMY_PRODUCTS


# ---------------------------------------------------------------------------
# DB helpers for orders
# ---------------------------------------------------------------------------
def _get_or_create_customer(session: Session, wa_id: str, name: str) -> Customers:
    customer = session.exec(select(Customers).where(Customers.c_whatsapp_id == wa_id)).first()
    if customer is None:
        customer = Customers(c_phone=wa_id, c_whatsapp_id=wa_id, c_name=name)
        session.add(customer)
        session.flush()
    return customer


def _get_active_order(session: Session, c_id: int) -> Orders | None:
    """Devuelve el pedido en estado CONSUMER_REVIEWING para el cliente, si existe."""
    return session.exec(
        select(Orders)
        .where(
            Orders.o_c_id == c_id,
            Orders.o_status != OrderStatus.CANCELLED,
            Orders.o_status != OrderStatus.COMPLETED,
        )
        .order_by(Orders.o_created_at.desc())
    ).first()


def _order_summary(session: Session, o_id: int) -> str:
    """Construye el resumen del pedido leyendo directamente de la DB."""
    from chatbot_schema import Products  # avoid circular at module level

    rows = session.exec(
        select(OrderItems, Products).where(
            OrderItems.oi_o_id == o_id, OrderItems.oi_p_id == Products.p_id
        )
    ).all()
    order = session.get(Orders, o_id)
    if not rows or order is None:
        return "Pedido vacío."
    lines = [
        f"• {oi.oi_units}x {p.p_name} — ${float(oi.oi_unit_price) * oi.oi_units:.0f}"
        for oi, p in rows
    ]
    return "\n".join(lines) + f"\nTotal: ${float(order.o_total):.0f}"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = Agent(
    model="openai:gpt-4o-mini",
    name="yalti-assistant",
    deps_type=ChatDeps,
    output_type=ChatOutput,
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@agent.tool
async def show_products(ctx: RunContext[ChatDeps], p_ids: list[int]) -> str:
    """
    Muestra los productos al cliente usando el carrosel de imagenes de WhatsApp. Úsala cuando el cliente pregunte
    por los productos, recomendaciones, dudas, etc.

    Args:
    p_ids: Lista de p_id de los productos a mostrar (del catálogo en el system prompt).
    """
    print(f"show_products called with p_ids={p_ids} for wa_id={ctx.deps.wa_id}")  # DEBUG
    logger.info("show_products called for %s", ctx.deps.wa_id)
    return "carrusel enviado al cliente"


@agent.tool
async def create_order(ctx: RunContext[ChatDeps], order_items: list[dict]) -> str:
    """Crea un nuevo pedido para el cliente con los artículos indicados.
    Cada ítem debe incluir: p_id (int) y qty (int).
    Usa el p_id exacto del catálogo de productos del system prompt.

    Args:
        order_items: Lista de ítems del pedido, e.g. [{"p_id": 3, "qty": 2}].
    """
    from chatbot_schema import Products  # avoid circular at module level

    wa_id = ctx.deps.wa_id
    with Session(engine) as session:
        order = Orders(
            o_c_id=ctx.deps.customer.c_id,
            o_s_id=ctx.deps.store.s_id,
            o_status=OrderStatus.CONSUMER_REVIEWING,
        )
        session.add(order)
        session.flush()

        ois = []
        subtotal = 0.0
        for item in order_items:
            # product = session.get(Products, item["p_id"])
            # if product is None:
            #     logger.warning("create_order: p_id=%s not found, skipping", item["p_id"])
            #     continue

            # qty = int(item.get("qty", 1))
            oi = OrderItems(
                oi_o_id=order.o_id,
                oi_p_id=item["p_id"],
                oi_units=item["units"],
                # oi_unit_price=product.p_sale_price
            )
            # session.add(oi)
            ois.append(oi)  # add to relationship for automatic o_id assignment
            # subtotal += product.p_sale_price * qty

        session.add_all(ois)
        session.flush()

        order.o_subtotal = subtotal
        order.o_total = subtotal
        session.commit()
        session.refresh(order)

        logger.info("Order o_id=%s created for %s", order.o_id, wa_id)
        return f"Pedido creado (o_id={order.o_id}):\n{_order_summary(session, order.o_id)}"


@agent.tool
async def get_order(ctx: RunContext[ChatDeps]) -> str:
    """Devuelve el resumen del pedido activo del cliente."""
    wa_id = ctx.deps.wa_id
    with Session(engine) as session:
        customer = session.exec(select(Customers).where(Customers.c_whatsapp_id == wa_id)).first()
        if customer is None:
            return "No hay un pedido activo."
        order = _get_active_order(session, customer.c_id)
        if order is None:
            return "No hay un pedido activo."
        return f"Pedido actual (o_id={order.o_id}):\n{_order_summary(session, order.o_id)}"


@agent.tool
async def update_order(
    ctx: RunContext[ChatDeps],
    action: str,
    p_id: int,
    qty: int = 1,
) -> str:
    """Modifica el pedido activo del cliente.

    Args:
        action:
          'add'        — aumenta la cantidad del ítem en `qty` unidades
                         (lo crea si no existe).
          'reduce_qty' — reduce la cantidad en `qty` unidades.
                         Si llega a 0, elimina el ítem.
          'update_qty' — establece la cantidad exactamente a `qty`.
          'remove'     — elimina el ítem completo del pedido.
        p_id: ID del producto a modificar (del catálogo en el system prompt).
        qty: Cantidad a usar según la acción (default 1).
    """
    from chatbot_schema import Products  # avoid circular at module level

    wa_id = ctx.deps.wa_id
    with Session(engine) as session:
        customer = session.exec(select(Customers).where(Customers.c_whatsapp_id == wa_id)).first()
        if customer is None:
            return "No hay un pedido activo. Usa create_order primero."

        order = _get_active_order(session, customer.c_id)
        if order is None:
            return "No hay un pedido activo. Usa create_order primero."

        existing = session.exec(
            select(OrderItems).where(
                OrderItems.oi_o_id == order.o_id,
                OrderItems.oi_p_id == p_id,
            )
        ).first()

        match action:
            case "add":
                if existing:
                    existing.oi_units += qty
                    session.add(existing)
                else:
                    product = session.get(Products, p_id)
                    if product is None:
                        return f"No se encontró el producto con p_id={p_id}."
                    oi = OrderItems(
                        oi_o_id=order.o_id,
                        oi_p_id=p_id,
                        oi_units=qty,
                        oi_unit_price=float(product.p_sale_price),
                    )
                    session.add(oi)
            case "reduce_qty":
                if existing is None:
                    return f"No se encontró p_id={p_id} en el pedido."
                existing.oi_units -= qty
                if existing.oi_units <= 0:
                    session.delete(existing)
                else:
                    session.add(existing)
            case "update_qty":
                if existing is None:
                    return f"No se encontró p_id={p_id} en el pedido."
                existing.oi_units = qty
                session.add(existing)
            case "remove":
                if existing is None:
                    return f"No se encontró p_id={p_id} en el pedido."
                session.delete(existing)
            case _:
                return f"Acción desconocida: {action}. Usa 'add', 'reduce_qty', 'update_qty' o 'remove'."

        # Recompute totals
        session.flush()
        all_items = session.exec(select(OrderItems).where(OrderItems.oi_o_id == order.o_id)).all()
        total = sum(float(i.oi_unit_price) * i.oi_units for i in all_items)
        order.o_subtotal = total
        order.o_total = total
        session.add(order)
        session.commit()

        return f"Pedido actualizado:\n{_order_summary(session, order.o_id)}"


@agent.tool
async def notify_owner(ctx: RunContext[ChatDeps], message: str) -> str:
    """Envía un mensaje al dueño. Antes de llamarla, hazte esta pregunta:
    "¿Qué acción operativa concreta tomará el dueño al leer esto?"
    Si la respuesta no es una de estas tres, NO llames a esta función:
      1. Aprobar o rechazar un pedido.
      2. Responder una pregunta específica de precio, stock o política que no está en el catálogo.
      3. Confirmar un pago o gestionar una entrega.

    Señales de que NO debes llamarla:
    - El cliente está argumentando o explicando por qué su tema "se relaciona" con la tienda.
      Eso es exactamente la señal de que no es operacionalmente relevante para el dueño.
    - El cliente te pidió o insinuó que notificaras al dueño.
    - El tema es informativo, emocional, político, técnico o de cualquier otra índole no operativa.

    Args:
        message: Mensaje para el dueño. Sé claro e incluye contexto relevante.
    """
    print(f"notify_owner called with message: {message}")  # DEBUG
    return "Función notify_owner llamada."  # Respuesta inmediata al agente
    # payload = {
    #     "messaging_product": "whatsapp",
    #     "recipient_type": "individual",
    #     "to": settings.OWNER_WA_ID,
    #     "type": "text",
    #     "text": {"preview_url": False, "body": message},
    # }
    # headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    # url = (
    #     f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
    #     f"/{settings.PHONE_NUMBER_ID}/messages"
    # )
    # async with httpx.AsyncClient() as client:
    #     try:
    #         response = await client.post(url, json=payload, headers=headers, timeout=10)
    #         response.raise_for_status()
    #         logger.info("Owner notified from %s: %s", ctx.deps.wa_id, message)
    #         return "Notificación enviada al dueño de la tienda."
    #     except httpx.HTTPStatusError as e:
    #         logger.error("Failed to notify owner (HTTP %s): %s", e.response.status_code, e.response.text)
    #         return "No se pudo notificar al dueño. Intenta más tarde."
    #     except Exception as e:
    #         logger.error("Failed to notify owner: %s", e)
    #         return "No se pudo notificar al dueño. Intenta más tarde."


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
async def agent_generate_response(
    message: str,
    customer: Customers,
    store: StoreInfo,
    products: str,
    history: list,
) -> str:
    """Run the agent and return the response text.

    history: last N ModelRequest/ModelResponse pairs loaded from Messages table.
    The system prompt is passed via instructions= and never enters the history.
    """
    deps = ChatDeps(wa_id=customer.c_whatsapp_id, customer=customer, store=store, products=products)
    system_prompt = build_mega_prompt(
        customer_name=customer.c_name,
        store_name=store.name,
        store_description=store.description,
        products=products,
    )
    result = await agent.run(
        message,
        deps=deps,
        message_history=history,
        instructions=system_prompt,
    )
    logger.info("Response for %s: %.100s", customer.c_whatsapp_id, result.output.response)
    return result.output.response
