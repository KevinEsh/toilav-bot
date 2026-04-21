from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx
from chatbot_schema import Customers, OrderItems, Orders, OrderStatus, Products, Stores
from config import settings
from database import engine
from pydantic_ai import Agent, ModelSettings, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import UsageLimits
from rules import ChatOutput, build_mega_prompt
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

# Populated by whatsapp_utils._fetch_products() each time the catalog is loaded.
PRODUCTS: dict[int, Products] = {}


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

    customer: Customers
    store: StoreInfo
    products: str  # formatted product catalog injected into the system prompt
    active_order_id: int | None = None  # pre-loaded; tools write back here after create_order
    _once: set[str] = field(default_factory=set)  # tools allowed only once per run


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


def _get_active_order(c_id: int) -> Orders | None:
    """Devuelve el pedido activo (no cancelado ni completado) del cliente, si existe."""
    with Session(engine) as session:
        return session.exec(
            select(Orders)
            .where(
                Orders.o_c_id == c_id,
                Orders.o_status != OrderStatus.CANCELLED,
                Orders.o_status != OrderStatus.COMPLETED,
            )
            .order_by(Orders.o_created_at.desc())
        ).first()


def _history_tool_calls(history: list) -> set[str]:
    """Devuelve los nombres de todas las herramientas llamadas en el historial previo."""
    called: set[str] = set()
    for msg in history:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    called.add(part.tool_name)
    return called


def _order_summary(order: Orders, order_items: list[OrderItems], customer_name: str) -> str:
    """Construye el resumen del pedido. Luce asi:
    🛍️ Nueva orden — *Juan López*

    • 2x Almendras tostadas — $120
    • 1x Nueces de la india — $85
    Total: *$205*

    📍 Calle 15 #45-23
    """
    if not order_items:
        return f"🛍️ Pedido — {customer_name}\n\n(sin ítems)\n\nTotal: $0"

    lines = []
    for oi in order_items:
        product = PRODUCTS.get(oi.oi_p_id)
        prod_name = product.p_name if product is not None else f"Producto #{oi.oi_p_id}"
        line_total = float(oi.oi_unit_price) * oi.oi_units
        lines.append(f"• {oi.oi_units}x {prod_name} — ${line_total:.0f}")

    total = float(order.o_total) if order.o_total is not None else 0.0
    notes = order.o_customer_notes or "(sin notas)"
    return (
        f"🛍️ Nueva orden — {customer_name}\n\n"
        + "\n".join(lines)
        + f"\n\nTotal: ${total:.0f}\n\n📍: {notes}"
    )
    # 📍 {order.o_delivery_address}
    # ⏰ {order.o_delivery_instructions}
    # 💳 {order.o_payment_method}

    # rows = session.exec(
    #     select(OrderItems, Products).where(
    #         OrderItems.oi_o_id == o_id, OrderItems.oi_p_id == Products.p_id
    #     )
    # ).all()
    # order = session.get(Orders, o_id)
    # if not rows or order is None:
    #     return "Pedido vacío."
    # lines = [
    #     f"• {oi.oi_units}x {p.p_name} — ${float(oi.oi_unit_price) * oi.oi_units:.0f}"
    #     for oi, p in rows
    # ]
    # return "\n".join(lines) + f"\nTotal: ${float(order.o_total):.0f}"


# ---------------------------------------------------------------------------
# Tool prepare functions — gate visibility based on active order state
# Returning None hides the tool from the LLM entirely (not just a prompt hint).
# ---------------------------------------------------------------------------
async def _hide_when_order_exists(
    ctx: RunContext[ChatDeps], tool_def: ToolDefinition
) -> ToolDefinition | None:
    """Hides the tool when an active order already exists."""
    return None if ctx.deps.active_order_id is not None else tool_def


async def _hide_when_no_order(
    ctx: RunContext[ChatDeps], tool_def: ToolDefinition
) -> ToolDefinition | None:
    """Hides the tool when there is no active order."""
    return tool_def if ctx.deps.active_order_id is not None else None


async def _hide_when_shown(
    ctx: RunContext[ChatDeps], tool_def: ToolDefinition
) -> ToolDefinition | None:
    """Hides show_products if it was already called this turn or in a previous turn."""
    return None if "show_products" in ctx.deps._once else tool_def


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = Agent(
    model="openai:gpt-4o-mini",
    name="yalti-assistant",
    deps_type=ChatDeps,
    output_type=ChatOutput,
    model_settings=ModelSettings(temperature=0.1),
)

# Sin tools — garantiza una respuesta directa en una sola llamada (usado como fallback)
_direct_agent = Agent(
    model="openai:gpt-4o-mini",
    output_type=ChatOutput,
    # instructions=
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@agent.tool(prepare=_hide_when_shown)
async def show_products(ctx: RunContext[ChatDeps], p_ids: list[int]) -> str:
    """Envía un carrusel visual de productos al cliente vía WhatsApp.

    Cuándo usarla: el cliente quiere explorar opciones ("¿qué tienen?", "¿qué me recomiendas?").
    Cuándo NO: preguntas de detalle sobre un producto específico (responde desde el catálogo)
    o si el cliente ya está armando un pedido. Si falta un dato, usa escalate_to_staff.

    Args:
        p_ids: Lista de p_id de los productos a mostrar (del catálogo).
    """
    ctx.deps._once.add("show_products")
    logger.info("show_products(%s) called for %s", p_ids, ctx.deps.customer.c_whatsapp_id)
    return "carrusel enviado al cliente"


@agent.tool(prepare=_hide_when_order_exists)
async def create_order(
    ctx: RunContext[ChatDeps],
    order_items: list[dict],
    delivery_address: str,
    delivery_instructions: str = "",
) -> str:
    """Crea un nuevo pedido en la base de datos.

    PRERREQUISITOS — no llamar hasta cumplir todos:
      1. Cada ítem tiene p_id del catálogo y units >= 1 confirmados por el cliente.
      2. delivery_address fue proporcionada explícitamente por el cliente (OBLIGATORIO).
      3. delivery_instructions fue preguntada (puede ser cadena vacía si el cliente no tiene).
      4. El cliente confirmó el resumen con una respuesta afirmativa SEPARADA al mensaje de resumen.
         El mensaje original del pedido no cuenta como confirmación.

    Si esta función retorna un error de validación (string que empieza con "ERROR_VALIDACION:"),
    NO debes crear el pedido. Primero obtén la información faltante del cliente y vuelve a llamar
    esta función con los parámetros corregidos.

    Args:
        order_items: Lista de ítems, cada uno con p_id (int) y units (int >= 1).
                     Ejemplo: [{"p_id": 3, "units": 2}]
        delivery_address: Dirección de entrega dada por el cliente. OBLIGATORIO — nunca inferir ni inventar.
        delivery_instructions: Instrucciones especiales para la entrega. Puede ser cadena vacía si el cliente no tiene.
    """
    logger.info(f"create_order({order_items=}, {delivery_address=}, {delivery_instructions=})")

    # --- Validaciones de entrada (no tocan la DB) ---
    if not order_items:
        return "ERROR_VALIDACION: order_items está vacío. Pide al cliente que especifique qué productos quiere."

    if not delivery_address or not delivery_address.strip():
        return "ERROR_VALIDACION: delivery_address es obligatoria. Pide al cliente su dirección de entrega."

    errors = []
    for i, item in enumerate(order_items):
        if not isinstance(item, dict):
            errors.append(f"Ítem {i}: debe ser un dict con p_id y units.")
            continue
        if "p_id" not in item or "units" not in item:
            errors.append(f"Ítem {i}: faltan campos 'p_id' o 'units'.")
            continue
        if item["p_id"] not in PRODUCTS:
            errors.append(f"Ítem {i}: p_id={item['p_id']} no existe en el catálogo.")
        if not isinstance(item["units"], int) or item["units"] < 1:
            errors.append(f"Ítem {i} (p_id={item.get('p_id')}): units debe ser un entero >= 1, recibido: {item.get('units')}.")

    if errors:
        return "ERROR_VALIDACION:\n" + "\n".join(f"- {e}" for e in errors)

    # --- Escritura a DB ---
    try:
        with Session(engine) as session:
            order = Orders(
                o_c_id=ctx.deps.customer.c_id,
                o_s_id=ctx.deps.store.s_id,
                o_status=OrderStatus.PENDING_STORE_APPROVAL,
                o_customer_notes=f"Dirección: {delivery_address.strip()} | Instrucciones: {delivery_instructions}",
            )
            session.add(order)
            session.flush()

            items = []
            subtotal = 0.0
            for item in order_items:
                unit_price = float(PRODUCTS[item["p_id"]].p_sale_price)
                subtotal += unit_price * item["units"]
                oi = OrderItems(
                    oi_o_id=order.o_id,
                    oi_p_id=item["p_id"],
                    oi_units=item["units"],
                    oi_unit_price=unit_price,
                )
                items.append(oi)

            order.o_subtotal = subtotal
            order.o_shipping_amount = 20.0  # flat shipping for now
            order.o_total = subtotal + order.o_shipping_amount

            session.add_all(items)
            session.commit()

            session.refresh(order)
            for oi in items:
                session.refresh(oi)

            ctx.deps.active_order_id = order.o_id
            logger.info(
                "create_order created o_id=%s for c_id=%s",
                order.o_id,
                ctx.deps.customer.c_id,
            )
            return _order_summary(order, items, ctx.deps.customer.c_name)

    except Exception as e:
        logger.error("create_order failed for c_id=%s: %s", ctx.deps.customer.c_id, e)
        return "ERROR_INTERNO: No se pudo crear el pedido por un problema técnico. Intenta de nuevo en un momento."


# @agent.tool(prepare=_hide_when_no_order)
# async def get_order(ctx: RunContext[ChatDeps]) -> str:
#     """Devuelve el resumen actual del pedido activo del cliente."""
#     with Session(engine) as session:
#         order = session.get(Orders, ctx.deps.active_order_id)
#         if order is None:
#             return "No se encontró el pedido activo."
#         return _order_summary(order, ctx.deps.customer.c_name)


@agent.tool(prepare=_hide_when_no_order)
async def update_order(
    ctx: RunContext[ChatDeps],
    action: str,
    p_id: int,
    units: int = 0,
) -> str:
    """Modifica el pedido activo del cliente.

    Si retorna un string que empieza con "ERROR_VALIDACION:", obtén la información
    correcta del cliente y vuelve a llamar con los parámetros corregidos.

    Args:
        action:
          'add'          — aumenta la cantidad del ítem en `units` unidades (lo crea si no existe).
          'reduce_units' — reduce la cantidad en `units` unidades; si llega a 0 elimina el ítem.
          'set_units'    — establece la cantidad exactamente a `units` (>= 1).
          'remove'       — elimina el ítem completo del pedido.
        p_id: ID del producto a modificar (del catálogo en el system prompt).
        units: Cantidad a usar según la acción. Requerido (>= 1) para 'add', 'reduce_units', 'set_units'.
    """
    c_id = ctx.deps.customer.c_id
    o_id = ctx.deps.active_order_id

    logger.info(f"update_order({action=}, {p_id=}, {units=}) for {o_id=} {c_id=}")

    # --- Validaciones de entrada (no tocan la DB) ---
    valid_actions = {"add", "reduce_units", "set_units", "remove"}
    if action not in valid_actions:
        return f"ERROR_VALIDACION: acción {action!r} desconocida. Usa: {', '.join(sorted(valid_actions))}."

    if p_id not in PRODUCTS:
        return f"ERROR_VALIDACION: p_id={p_id} no existe en el catálogo."

    if action in {"add", "reduce_units", "set_units"} and units < 1:
        return f"ERROR_VALIDACION: units debe ser >= 1 para la acción '{action}', recibido: {units}."

    # --- Escritura a DB ---
    try:
        with Session(engine) as session:
            order = session.get(Orders, o_id)
            if order is None:
                return f"ERROR_INTERNO: no se encontró el pedido o_id={o_id}."

            existing = session.exec(
                select(OrderItems).where(OrderItems.oi_o_id == o_id, OrderItems.oi_p_id == p_id)
            ).first()

            product = PRODUCTS[p_id]

            match action:
                case "add":
                    if existing:
                        existing.oi_units += units
                        session.add(existing)
                    else:
                        session.add(OrderItems(
                            oi_o_id=o_id,
                            oi_p_id=p_id,
                            oi_units=units,
                            oi_unit_price=float(product.p_sale_price),
                        ))
                case "reduce_units":
                    if existing is None:
                        return f"ERROR_VALIDACION: p_id={p_id} no está en el pedido."
                    existing.oi_units -= units
                    if existing.oi_units <= 0:
                        session.delete(existing)
                    else:
                        session.add(existing)
                case "set_units":
                    if existing is None:
                        return f"ERROR_VALIDACION: p_id={p_id} no está en el pedido."
                    existing.oi_units = units
                    session.add(existing)
                case "remove":
                    if existing is None:
                        return f"ERROR_VALIDACION: p_id={p_id} no está en el pedido."
                    session.delete(existing)

            session.flush()
            all_items = session.exec(select(OrderItems).where(OrderItems.oi_o_id == o_id)).all()

            if not all_items:
                session.rollback()
                return "ERROR_VALIDACION: no puedes eliminar todos los ítems del pedido. Usa cancel_order si quieres cancelarlo."

            total = sum(float(i.oi_unit_price) * i.oi_units for i in all_items)
            order.o_subtotal = total
            order.o_total = total
            session.add(order)
            session.commit()

            return f"Pedido actualizado:\n{_order_summary(order, all_items, ctx.deps.customer.c_name)}"

    except Exception as e:
        logger.error("update_order failed for o_id=%s c_id=%s: %s", o_id, c_id, e)
        return "ERROR_INTERNO: No se pudo actualizar el pedido por un problema técnico. Intenta de nuevo en un momento."


# @agent.tool(prepare=_hide_when_no_order)
# async def notify_staff_order_ready(ctx: RunContext[ChatDeps]) -> str:
#     """Notifica al dueño que el cliente confirmó su pedido y está listo para aprobación.

#     Solo cuando el cliente confirme de forma inequívoca ("sí, confírmalo", "listo",
#     "procede"). Para consultas generales usa escalate_to_staff.
#     """
#     o_id = ctx.deps.active_order_id
#     with Session(engine) as session:
#         order = session.get(Orders, o_id)
#         summary = _order_summary(session, o_id)
#         order.o_status = OrderStatus.PENDING_STORE_APPROVAL
#         session.add(order)
#         session.commit()

#     logger.info("notify_staff_order_ready o_id=%s for c_id=%s", o_id, ctx.deps.customer.c_id)
#     # TODO: send WhatsApp message to OWNER_WA_ID with summary
#     return f"Pedido o_id={o_id} enviado al equipo para aprobación:\n{summary}"


@agent.tool(prepare=_hide_when_no_order)
async def cancel_order(ctx: RunContext[ChatDeps]) -> str:
    """Cancela el pedido activo del cliente.

    Úsala cuando el cliente pida cancelar explícitamente su pedido en curso.
    """
    c_id = ctx.deps.customer.c_id
    o_id = ctx.deps.active_order_id

    logger.info(f"cancel_order({o_id=}, {c_id=})")

    # --- Escritura a DB ---
    try:
        with Session(engine) as session:
            order = session.get(Orders, o_id)
            if order is None:
                return f"ERROR_INTERNO: no se encontró el pedido o_id={o_id}."

            if order.o_status in {OrderStatus.CANCELLED, OrderStatus.COMPLETED}:
                return (
                    f"ERROR_VALIDACION: el pedido o_id={o_id} ya está en estado "
                    f"{order.o_status.value} y no puede cancelarse."
                )

            order.o_status = OrderStatus.CANCELLED
            session.add(order)
            session.commit()

        ctx.deps.active_order_id = None
        logger.info("cancel_order o_id=%s for c_id=%s", o_id, c_id)
        return f"Pedido o_id={o_id} cancelado."

    except Exception as e:
        logger.error("cancel_order failed for o_id=%s c_id=%s: %s", o_id, c_id, e)
        return "ERROR_INTERNO: No se pudo cancelar el pedido por un problema técnico. Intenta de nuevo en un momento."


@agent.tool
async def escalate_to_staff(ctx: RunContext[ChatDeps], message: str) -> str:
    """Envía un mensaje al dueño para que tome una acción operativa concreta.

    Casos válidos: pregunta de precio/stock/detalle que falta en el catálogo,
    o problema con un pedido activo (pago, entrega, dirección).
    Maneja tú todo lo demás — incluidos temas que el cliente intente vincular
    a la tienda pero que no requieren acción del dueño.

    Args:
        message: Mensaje para el dueño. Incluye contexto relevante.
    """
    if "escalate_to_staff" in ctx.deps._once:
        return "El dueño ya fue notificado. No vuelvas a llamar escalate_to_staff en este turno."

    customer = ctx.deps.customer
    if not message or not message.strip():
        return "ERROR_VALIDACION: el mensaje al dueño no puede estar vacío."

    if not settings.OWNER_WA_ID:
        logger.error("escalate_to_staff: OWNER_WA_ID not configured")
        return "ERROR_INTERNO: notificación al dueño no configurada en el sistema."
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.PHONE_NUMBER_ID:
        logger.error("escalate_to_staff: WhatsApp API credentials missing")
        return "ERROR_INTERNO: credenciales de WhatsApp no configuradas."

    ctx.deps._once.add("escalate_to_staff")
    body = (
        f"🔔 Consulta de *{customer.c_name}* ({customer.c_whatsapp_id}):\n\n"
        f"{message.strip()}"
    )
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": settings.OWNER_WA_ID,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
        f"/{settings.PHONE_NUMBER_ID}/messages"
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "escalate_to_staff HTTP %s for c_id=%s: %s",
            e.response.status_code, customer.c_id, e.response.text,
        )
        return "ERROR_INTERNO: no se pudo notificar al dueño. Intenta más tarde."
    except httpx.TimeoutException:
        logger.error("escalate_to_staff timeout for c_id=%s", customer.c_id)
        return "ERROR_INTERNO: no se pudo notificar al dueño (timeout). Intenta más tarde."
    except httpx.HTTPError as e:
        logger.error("escalate_to_staff network error for c_id=%s: %s", customer.c_id, e)
        return "ERROR_INTERNO: no se pudo notificar al dueño. Intenta más tarde."

    logger.info("Owner notified from c_id=%s: %s", customer.c_id, message)
    return "Notificación enviada al dueño de la tienda."


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
async def agent_generate_response(
    message: str,
    customer: Customers,
    store: Stores,
    products: str,
    history: list,
) -> tuple[str, list]:
    """Run the agent and return (response_text, full_message_history).

    history: pydantic-ai ModelMessage list loaded from Conversations.cv_history.
    The system prompt is passed via instructions= and never enters the history.

    Returns:
        Tuple of (response text, all_messages from the run) — the caller persists
        the full history back to Conversations.cv_history.
    """
    existing_order = _get_active_order(customer.c_id)
    # Pre-populate _once from history so show_products stays hidden across turns.
    once = _history_tool_calls(history) & {"show_products"}
    deps = ChatDeps(
        customer=customer,
        store=store,
        products=products,
        active_order_id=existing_order.o_id if existing_order else None,
        _once=once,
    )
    system_prompt = build_mega_prompt(
        customer_name=customer.c_name,
        store_name=store.s_name,
        store_description=store.s_description,
        products=products,
    )
    # DEBUG: iter() para ver cada nodo del loop — reemplazar con agent.run() en producción
    try:
        # async with agent.iter(
        #     message,
        #     deps=deps,
        #     message_history=history,
        #     instructions=system_prompt,
        #     usage_limits=UsageLimits(request_limit=8),
        # ) as run:
        #     async for node in run:
        # print("-" * 20)  # DEBUG: separador entre nodos
        # logger.info("[%s] %s", type(node).__name__, n)
        # print("-" * 20)
        # print(node)  # DEBUG: print each node
        result = await agent.run(
            message,
            deps=deps,
            message_history=history,
            instructions=system_prompt,
            usage_limits=UsageLimits(request_limit=8),
        )
        return result.output.response, result.all_messages()
    except UsageLimitExceeded as e:
        # UsageLimitExceeded se lanza desde __aexit__, no desde el loop.
        # run sigue en scope porque fue asignado en __aenter__.
        logger.warning("Request limit hit after %s requests: %s", result.usage().requests, e)
        final = await _direct_agent.run(
            message,
            message_history=result.all_messages(),
            instructions=system_prompt
            + "\nResponde directamente al cliente ahora, sin usar herramientas. "
            "NO prometas acciones que aún no se completaron (crear pedido, confirmar, etc.). "
            "Si aún falta información del cliente, haz la pregunta de clarificación que corresponde.",
        )
        return final.output.response, final.all_messages()
