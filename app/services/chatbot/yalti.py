from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

import httpx
from chatbot_schema import Customers, OrderItems, Orders, OrderStatus, Products, Stores
from config import settings
from database import get_session
from models import CustomerRow, ProductRow, StoreRow
from pydantic_ai import Agent, ModelSettings, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import UsageLimits
from rules import ChatOutput, build_mega_prompt
from sqlalchemy import column, insert, table, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Populated by whatsapp_utils._fetch_products() each time the catalog is loaded.
PRODUCTS: dict[int, ProductRow] = {}


async def _send_whatsapp_text(to: str, body: str) -> bool:
    """Sends a plain WhatsApp text message. Returns True on success, logs and returns False on error."""
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.PHONE_NUMBER_ID:
        logger.error("_send_whatsapp_text: WhatsApp credentials not configured")
        return False
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    url = (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
        f"/{settings.PHONE_NUMBER_ID}/messages"
    )
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        logger.error(
            "_send_whatsapp_text HTTP %s to %s: %s",
            e.response.status_code,
            to,
            e.response.text,
        )
    except httpx.TimeoutException:
        logger.error("_send_whatsapp_text timeout to %s", to)
    except httpx.HTTPError as e:
        logger.error("_send_whatsapp_text network error to %s: %s", to, e)
    return False


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

    customer: CustomerRow
    store: StoreRow
    products: dict[str, ProductRow]
    session: AsyncSession  # shared session for the duration of the agent run
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
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
# Máximo de productos a enviar en un mismo turno — evita flood al cliente
# y respeta el rate limit del Graph API (WhatsApp tolera ráfagas cortas pero
# 5 mensajes encadenados es el umbral práctico antes de que marquen spam).
_SHOW_PRODUCTS_CAP = 5


def _product_payload(wa_id: str, product: Products) -> dict:
    """Construye el payload de WhatsApp para un producto.

    Si tiene p_image_url usa `type: "image"` (imagen + caption).
    Si no, cae a `type: "text"` para no romper el flujo por falta de foto.
    """
    price = float(product.p_sale_price)
    header = f"*{product.p_name}* — ${price:.0f} {product.p_currency}"
    description = (product.p_description or "").strip()
    caption = header if not description else f"{header}\n\n{description}"

    if product.p_image_url:
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": wa_id,
            "type": "image",
            "image": {"link": product.p_image_url, "caption": caption},
        }
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": wa_id,
        "type": "text",
        "text": {"preview_url": False, "body": caption},
    }


@agent.tool(prepare=_hide_when_shown)
async def show_products(ctx: RunContext[ChatDeps], p_ids: list[int]) -> str:
    """Envía al cliente una tarjeta visual por cada producto (imagen + precio + nombre).

    Cuándo usarla: el cliente quiere explorar opciones ("¿qué tienen?", "¿qué me recomiendas?").
    Cuándo NO: preguntas de detalle sobre un producto específico (responde desde el catálogo)
    o si el cliente ya está armando un pedido. Si falta un dato, usa escalate_to_staff.

    Args:
        p_ids: Lista de p_id de los productos a mostrar (del catálogo). Máximo 5.
    """
    logger.info("show_products(%s) called for %s", p_ids, ctx.deps.customer.c_whatsapp_id)

    if "show_products" in ctx.deps._once:
        return "Los productos ya fueron enviados. No vuelvas a llamar show_products en este turno."

    # --- Validaciones de entrada (no tocan la red) ---
    if not p_ids:
        return "ERROR_VALIDACION: p_ids no puede estar vacío. Selecciona al menos un producto del catálogo."

    # Dedup preservando orden
    seen: set[int] = set()
    dedup = [p for p in p_ids if not (p in seen or seen.add(p))]

    valid: list[Products] = []
    missing: list[int] = []
    unavailable: list[int] = []
    for pid in dedup:
        product = PRODUCTS.get(pid)
        if product is None:
            missing.append(pid)
        elif not product.p_is_available:
            unavailable.append(pid)
        else:
            valid.append(product)

    if not valid:
        detalles = []
        if missing:
            detalles.append(f"no existen en el catálogo: {missing}")
        if unavailable:
            detalles.append(f"no están disponibles: {unavailable}")
        detalle = "; ".join(detalles) if detalles else "ninguno válido"
        return f"ERROR_VALIDACION: ningún producto válido para mostrar ({detalle})."

    valid = valid[:_SHOW_PRODUCTS_CAP]

    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.PHONE_NUMBER_ID:
        logger.error("show_products: WhatsApp API credentials missing")
        return "ERROR_INTERNO: credenciales de WhatsApp no configuradas."

    # --- Envío secuencial — break en el primer error, no reintenta ---
    wa_id = ctx.deps.customer.c_whatsapp_id
    c_id = ctx.deps.customer.c_id
    sent = 0
    for product in valid:
        try:
            await whatsapp_client.post_message(_product_payload(wa_id, product))
        except httpx.HTTPStatusError as e:
            logger.error(
                "show_products HTTP %s for p_id=%s c_id=%s: %s",
                e.response.status_code,
                product.p_id,
                c_id,
                e.response.text,
            )
            break
        except httpx.TimeoutException:
            logger.error("show_products timeout for p_id=%s c_id=%s", product.p_id, c_id)
            break
        except httpx.HTTPError as e:
            logger.error(
                "show_products network error for p_id=%s c_id=%s: %s", product.p_id, c_id, e
            )
            break
        sent += 1

    if sent == 0:
        # Nada llegó al cliente — no marcamos _once, el LLM puede reintentar o
        # decidir responder por texto.
        return "ERROR_INTERNO: no se pudo enviar el catálogo al cliente. Intenta más tarde."

    ctx.deps._once.add("show_products")
    if sent < len(valid):
        logger.warning(
            "show_products sent %s/%s for c_id=%s (parcial por error HTTP)",
            sent,
            len(valid),
            c_id,
        )
        return f"Se enviaron {sent} de {len(valid)} productos al cliente (envío parcial)."
    return f"Se enviaron {sent} productos al cliente."


@agent.tool(prepare=_hide_when_order_exists)
async def create_order(
    ctx: RunContext[ChatDeps],
    items: list[dict],
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
        items: Lista de ítems, cada uno con p_id (int) y units (int >= 1).
                     Ejemplo: [{"p_id": 3, "units": 2}]
        delivery_address: Dirección de entrega dada por el cliente. OBLIGATORIO — nunca inferir ni inventar.
        delivery_instructions: Instrucciones especiales para la entrega. Puede ser cadena vacía si el cliente no tiene.
    """
    logger.info(f"create_order({items=}, {delivery_address=}, {delivery_instructions=})")

    # --- Validaciones de entrada (no tocan la DB) ---
    if not items:
        logger.warning("")
        return "ERROR_VALIDACION: items está vacío. Pide al cliente que especifique qué productos quiere."

    if not delivery_address or not delivery_address.strip():
        return "ERROR_VALIDACION: delivery_address es obligatoria. Pide al cliente su dirección de entrega."

    logger.info("create_order: products size=%d", len(ctx.deps.products))

    errors = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"Ítem {i}: debe ser un dict con p_id y units.")
            continue
        if "p_id" not in item or "units" not in item:
            errors.append(f"Ítem {i}: faltan campos 'p_id' o 'units'.")
            continue
        logger.info(
            "create_order: validando ítem %d — p_id=%r units=%r in_PRODUCTS=%s",
            i,
            item["p_id"],
            item.get("units"),
            item["p_id"] in PRODUCTS,
        )
        if item["p_id"] not in ctx.deps.products:
            errors.append(f"Ítem {i}: p_id={item['p_id']} no existe en el catálogo.")
        if not isinstance(item["units"], int) or item["units"] < 1:
            errors.append(
                f"Ítem {i} (p_id={item.get('p_id')}): units debe ser un entero >= 1, recibido: {item.get('units')}."
            )

    if errors:
        logger.warning("create_order: errores de validación — %s", errors)
        return "ERROR_VALIDACION:\n" + "\n".join(f"- {e}" for e in errors)

    logger.info("create_order: validaciones OK, procediendo a DB")

    products = ctx.deps.products
    # --- Escritura a DB ---
    try:
        session = ctx.deps.session
        notes = f"Dirección: {delivery_address.strip()} | Instrucciones: {delivery_instructions.strip()}"

        insert_order_query = text("""
            INSERT INTO orders (o_c_id, o_s_id, o_status, o_customer_notes, o_subtotal, o_shipping_amount, o_total, o_currency)
            VALUES (:o_c_id, :o_s_id, :o_status, :o_customer_notes, 0, :o_shipping_amount, 0, :o_currency)
            RETURNING o_id
        """)

        query_args = {
            "o_c_id": ctx.deps.customer.c_id,
            "o_s_id": ctx.deps.store.s_id,
            "o_status": "PENDING_STORE_APPROVAL",
            "o_customer_notes": notes,
            "o_shipping_amount": Decimal("20.0"),
            "o_currency": "MXN",
        }

        logger.info("Inserting Order in DB")

        order_res = await session.execute(insert_order_query, query_args)
        o_id = order_res.scalar()

        logger.info(
            "create_order: RETURNING o_id=%r (None indica fallo silencioso del INSERT)", o_id
        )
        if o_id is None:
            logger.error(
                "create_order: o_id es None tras el INSERT — revisar enum o_status o FK c_id/s_id"
            )

        logger.info(f"Order created with {o_id=}, now inserting OrderItems")

        _orderitems = table(
            "orderitems",
            column("oi_o_id"),
            column("oi_p_id"),
            column("oi_units"),
            column("oi_unit_price"),
        )
        orderitems_rows = [
            {
                "oi_o_id": o_id,
                "oi_p_id": item["p_id"],
                "oi_units": item["units"],
                "oi_unit_price": float(products[item["p_id"]].p_sale_price),
            }
            for item in items
        ]
        logger.info(
            "create_order: insertando %d orderitems: %r", len(orderitems_rows), orderitems_rows
        )
        await session.execute(insert(_orderitems), orderitems_rows)
        logger.info("create_order: INSERT orderitems OK, haciendo commit")
        await session.commit()
        logger.info("create_order: commit OK")

        ctx.deps.active_order_id = o_id
        logger.info("create_order created o_id=%s for c_id=%s", o_id, ctx.deps.customer.c_id)
        summary = await order_summary(session, o_id, ctx.deps.customer.c_name)

    except Exception as e:
        logger.error("create_order failed for c_id=%s: %s", ctx.deps.customer.c_id, e)
        logger.debug("create_order traceback:", exc_info=True)
        return "ERROR_INTERNO: No se pudo crear el pedido por un problema técnico. Intenta de nuevo en un momento."

    if settings.OWNER_WA_ID:
        o_id = ctx.deps.active_order_id
        owner_msg = (
            f"{summary}\n\n"
            f"/approve  |  /approve {o_id}\n"
            f"/reject <motivo>  |  /reject {o_id} <motivo>"
        )
        await _send_whatsapp_text(settings.OWNER_WA_ID, owner_msg)

    return summary


# @agent.tool(prepare=_hide_when_no_order)
# async def get_order(ctx: RunContext[ChatDeps]) -> str:
#     """Devuelve el resumen actual del pedido activo del cliente."""
#     ...


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
    products = ctx.deps.products

    logger.info(f"update_order({action=}, {p_id=}, {units=}) for {o_id=} {c_id=}")

    # --- Validaciones de entrada (no tocan la DB) ---
    valid_actions = {"add", "reduce_units", "set_units", "remove"}
    if action not in valid_actions:
        return f"ERROR_VALIDACION: acción {action!r} desconocida. Usa: {', '.join(sorted(valid_actions))}."

    if p_id not in products:
        return f"ERROR_VALIDACION: p_id={p_id} no existe en el catálogo."

    if action in {"add", "reduce_units", "set_units"} and units < 1:
        return (
            f"ERROR_VALIDACION: units debe ser >= 1 para la acción '{action}', recibido: {units}."
        )

    # --- Escritura a DB ---
    try:
        session = ctx.deps.session

        get_orderitem_query = text("""
            SELECT oi_id, oi_units 
            FROM orderitems 
            WHERE oi_o_id = :o_id AND oi_p_id = :p_id
        """)

        result = await session.execute(get_orderitem_query, {"o_id": o_id, "p_id": p_id})
        order_item = result.mappings().first()

        match action:
            case "add":
                if order_item:
                    add_to_orderitem_query = text(
                        "UPDATE orderitems SET oi_units = oi_units + :oi_units WHERE oi_id = :oi_id"
                    )
                    await session.execute(
                        add_to_orderitem_query,
                        {"oi_units": units, "oi_id": order_item["oi_id"]},
                    )
                else:
                    insert_orderitem_query = text("""
                            INSERT INTO orderitems (oi_o_id, oi_p_id, oi_units, oi_unit_price)
                            VALUES (:o_id, :p_id, :units, :unit_price)
                        """)
                    query_args = {
                        "o_id": o_id,
                        "p_id": p_id,
                        "units": units,
                        "unit_price": products[p_id].p_sale_price,
                    }

                    await session.execute(insert_orderitem_query, query_args)

            case "reduce_units":
                if existing is None:
                    return f"ERROR_VALIDACION: p_id={p_id} no está en el pedido."
                new_units = existing["oi_units"] - units
                if new_units <= 0:
                    await session.execute(
                        text("DELETE FROM orderitems WHERE oi_id = :oi_id"),
                        {"oi_id": existing["oi_id"]},
                    )
                else:
                    await session.execute(
                        text("UPDATE orderitems SET oi_units = :units WHERE oi_id = :oi_id"),
                        {"units": new_units, "oi_id": existing["oi_id"]},
                    )
            case "set_units":
                if existing is None:
                    return f"ERROR_VALIDACION: p_id={p_id} no está en el pedido."
                await session.execute(
                    text("UPDATE orderitems SET oi_units = :units WHERE oi_id = :oi_id"),
                    {"units": units, "oi_id": existing["oi_id"]},
                )
            case "remove":
                if existing is None:
                    return f"ERROR_VALIDACION: p_id={p_id} no está en el pedido."
                await session.execute(
                    text("DELETE FROM orderitems WHERE oi_id = :oi_id"),
                    {"oi_id": existing["oi_id"]},
                )

        remaining = (
            await session.execute(
                text("SELECT COUNT(*) FROM orderitems WHERE oi_o_id = :o_id"),
                {"o_id": o_id},
            )
        ).scalar()
        if not remaining:
            await session.rollback()
            return "ERROR_VALIDACION: no puedes eliminar todos los ítems del pedido. Usa cancel_order si quieres cancelarlo."

        await session.commit()

        summary = await order_summary(session, o_id, ctx.deps.customer.c_name)
        return f"Pedido actualizado:\n{summary}"

    except Exception as e:
        logger.error("update_order failed for o_id=%s c_id=%s: %s", o_id, c_id, e)
        return "ERROR_INTERNO: No se pudo actualizar el pedido por un problema técnico. Intenta de nuevo en un momento."


# @agent.tool(prepare=_hide_when_no_order)
# async def notify_staff_order_ready(ctx: RunContext[ChatDeps]) -> str: ...


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
        session = ctx.deps.session

        row = (
            (
                await session.execute(
                    text("SELECT o_id, o_status FROM orders WHERE o_id = :o_id"),
                    {"o_id": o_id},
                )
            )
            .mappings()
            .first()
        )

        if row is None:
            return f"ERROR_INTERNO: no se encontró el pedido o_id={o_id}."

        if row["o_status"] in {"cancelled", "completed"}:
            return (
                f"ERROR_VALIDACION: el pedido o_id={o_id} ya está en estado "
                f"{row['o_status']} y no puede cancelarse."
            )

        await session.execute(
            text("UPDATE orders SET o_status = 'cancelled' WHERE o_id = :o_id"),
            {"o_id": o_id},
        )
        await session.commit()

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

    ctx.deps._once.add("escalate_to_staff")
    body = f"🔔 Consulta de *{customer.c_name}* ({customer.c_whatsapp_id}):\n\n{message.strip()}"
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
            e.response.status_code,
            customer.c_id,
            e.response.text,
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
    customer: CustomerRow,
    store: StoreRow,
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
    once = _history_tool_calls(history) & {"show_products"}
    system_prompt = build_mega_prompt(
        customer_name=customer.c_name,
        store_name=store.s_name,
        store_description=store.s_description,
        products=products,
    )

    async with get_session() as session:
        # Resolve active order before handing control to the agent.
        active_res = await session.execute(
            text("""
                SELECT o_id FROM orders
                WHERE o_c_id = :c_id
                  AND o_status NOT IN ('CANCELLED', 'COMPLETED')
                ORDER BY o_created_at DESC
                LIMIT 1
            """),
            {"c_id": customer.c_id},
        )
        active_order_id = active_res.scalar()

        deps = ChatDeps(
            customer=customer,
            store=store,
            products=products,
            session=session,
            active_order_id=active_order_id,
            _once=once,
        )

        # DEBUG: iter() para ver cada nodo del loop — reemplazar con agent.run() en producción
        try:
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
