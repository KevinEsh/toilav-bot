from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from config import settings
from pydantic_ai import Agent, RunContext
from rules import ChatOutput, build_mega_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Store and conversation dependencies
# ---------------------------------------------------------------------------
@dataclass
class StoreInfo:
    """Store information loaded from DB."""

    name: str
    description: str
    properties: dict


@dataclass
class ChatDeps:
    """Agent dependencies injected on every run."""

    wa_id: str
    customer_name: str
    store: StoreInfo


# ---------------------------------------------------------------------------
# In-memory order store — dummy implementation, replace with DB
# ---------------------------------------------------------------------------
_pending_orders: dict[str, dict] = {}

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


def _order_summary(order: dict) -> str:
    lines = "\n".join(
        f"• {i['qty']}x {i['name']} — ${i['unit_price'] * i['qty']:.0f}"
        for i in order["items"]
    )
    return f"{lines}\nTotal: ${order['total']:.0f}"


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
async def search_products(ctx: RunContext[ChatDeps], query: str) -> str:
    """Busca productos, precios, disponibilidad, zonas de entrega y políticas
    de la tienda. Llámala SIEMPRE antes de responder preguntas que necesiten
    datos concretos.

    Args:
        query: La pregunta o tema a buscar.
    """
    logger.info("Product search from %s: %s", ctx.deps.wa_id, query)
    # TODO: Replace with pgvector RAG query
    return _DUMMY_PRODUCTS


@agent.tool
async def create_order(ctx: RunContext[ChatDeps], items: list[dict]) -> str:
    """Crea un nuevo pedido para el cliente con los artículos indicados.
    Cada ítem debe incluir: name (str), qty (int), unit_price (float).

    Args:
        items: Lista de ítems del pedido.
    """
    wa_id = ctx.deps.wa_id
    total = sum(i.get("unit_price", 0) * i.get("qty", 1) for i in items)
    order = {
        "id": f"ORD-{wa_id[-4:].upper()}",
        "customer": ctx.deps.customer_name,
        "items": items,
        "total": total,
        "status": "REVIEWING",
    }
    _pending_orders[wa_id] = order
    logger.info("Order created for %s: %s", wa_id, order)
    # TODO: Persist to DB — Order + OrderItem records
    return f"Pedido creado:\n{_order_summary(order)}"


@agent.tool
async def get_order(ctx: RunContext[ChatDeps]) -> str:
    """Devuelve el resumen del pedido activo del cliente."""
    order = _pending_orders.get(ctx.deps.wa_id)
    if order is None:
        return "No hay un pedido activo."
    return f"Pedido actual:\n{_order_summary(order)}"


@agent.tool
async def update_order(
    ctx: RunContext[ChatDeps],
    action: str,
    item_name: str,
    qty: int = 1,
    unit_price: float = 0.0,
) -> str:
    """Modifica el pedido activo del cliente.

    Args:
        action:
          'add'        — aumenta la cantidad del ítem en `qty` unidades
                         (lo crea si no existe, usando unit_price).
          'reduce_qty' — reduce la cantidad del ítem en `qty` unidades.
                         Úsala cuando el cliente diga "quita uno", "quita dos", etc.
                         Si la cantidad llega a 0, elimina el ítem.
          'update_qty' — establece la cantidad del ítem exactamente a `qty`.
                         Úsala cuando el cliente diga "quiero exactamente N".
          'remove'     — elimina el ítem completo del pedido.
                         Úsala solo cuando el cliente quiera quitarlo por completo.
        item_name: Nombre del producto a modificar.
        qty: Cantidad a usar según la acción (default 1).
        unit_price: Precio unitario (solo necesario en 'add' si el ítem no existe aún).
    """
    wa_id = ctx.deps.wa_id
    order = _pending_orders.get(wa_id)
    if order is None:
        return "No hay un pedido activo. Usa create_order primero."

    items = order["items"]
    match action:
        case "add":
            existing = next((i for i in items if i["name"].lower() == item_name.lower()), None)
            if existing:
                existing["qty"] += qty
            else:
                items.append({"name": item_name, "qty": qty, "unit_price": unit_price})
        case "reduce_qty":
            existing = next((i for i in items if i["name"].lower() == item_name.lower()), None)
            if not existing:
                return f"No se encontró '{item_name}' en el pedido."
            existing["qty"] -= qty
            if existing["qty"] <= 0:
                order["items"] = [i for i in order["items"] if i["name"].lower() != item_name.lower()]
        case "update_qty":
            existing = next((i for i in items if i["name"].lower() == item_name.lower()), None)
            if not existing:
                return f"No se encontró '{item_name}' en el pedido."
            existing["qty"] = qty
        case "remove":
            order["items"] = [i for i in items if i["name"].lower() != item_name.lower()]
        case _:
            return f"Acción desconocida: {action}. Usa 'add', 'reduce_qty', 'update_qty' o 'remove'."

    order["total"] = sum(i.get("unit_price", 0) * i.get("qty", 1) for i in order["items"])
    # TODO: Sync changes to DB OrderItem records
    return f"Pedido actualizado:\n{_order_summary(order)}"


@agent.tool
async def notify_owner(ctx: RunContext[ChatDeps], message: str) -> str:
    """Envía un mensaje directo al dueño de la tienda. Úsala cuando:
    - No puedas responder una pregunta con search_products (escala la consulta).
    - El cliente confirme su pedido (incluye el resumen completo del pedido).

    Args:
        message: Mensaje para el dueño. Sé claro e incluye contexto relevante.
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": settings.OWNER_WA_ID,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
        f"/{settings.PHONE_NUMBER_ID}/messages"
    )
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            logger.info("Owner notified from %s: %s", ctx.deps.wa_id, message)
            return "Notificación enviada al dueño de la tienda."
        except httpx.HTTPStatusError as e:
            logger.error("Failed to notify owner (HTTP %s): %s", e.response.status_code, e.response.text)
            return "No se pudo notificar al dueño. Intenta más tarde."
        except Exception as e:
            logger.error("Failed to notify owner: %s", e)
            return "No se pudo notificar al dueño. Intenta más tarde."


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
async def agent_generate_response(
    message: str,
    wa_id: str,
    name: str,
    store: StoreInfo,
    history: list,
) -> tuple[str, list]:
    """Run the agent and return (response_text, updated_history).

    Phase-based routing (router.py + per-phase prompts in rules.py) is
    preserved in the codebase for future multi-phase integration.
    """
    deps = ChatDeps(wa_id=wa_id, customer_name=name, store=store)
    system_prompt = build_mega_prompt(
        customer_name=name,
        store_name=store.name,
        store_description=store.description,
    )
    result = await agent.run(
        message,
        deps=deps,
        message_history=history,
        instructions=system_prompt,
    )
    new_history = history + list(result.new_messages())
    logger.info("Response for %s: %.100s", wa_id, result.output.response)
    return result.output.response, new_history
