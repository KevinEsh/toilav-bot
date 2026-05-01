from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

import httpx
import whatsapp_client
from config import settings
from database import get_session
from dbutils import load_order, load_orderitem
from models import CustomerRow, OrderRow, ProductRow, StoreRow
from pydantic_ai import Agent, ModelSettings, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import UsageLimits
from queries import insert_bulk_orderitems_query, insert_order_query
from rules import ChatOutput, build_mega_prompt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _send_whatsapp_text(to: str, body: str) -> bool:
    """Sends a plain WhatsApp text message. Returns True on success, logs and returns False on error."""
    if not settings.WHATSAPP_ACCESS_TOKEN or not settings.PHONE_NUMBER_ID:
        logger.error(f"_send_whatsapp_text[{to=}]: WhatsApp credentials not configured")
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
            f"_send_whatsapp_text[{to=}]: HTTP {e.response.status_code} — {e.response.text}"
        )
    except httpx.TimeoutException:
        logger.error(f"_send_whatsapp_text[{to=}]: timeout")
    except httpx.HTTPError as e:
        logger.error(f"_send_whatsapp_text[{to=}]: network error — {e}")
    return False


@dataclass
class ChatDeps:
    """Agent dependencies injected on every run."""

    customer: CustomerRow
    store: StoreRow
    products: dict[str, ProductRow]
    session: AsyncSession  # shared session for the duration of the agent run
    active_order: OrderRow | None = None  # pre-loaded; tools write back here after create_order
    _once: set[str] = field(default_factory=set)  # tools allowed only once per run


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
        SELECT o_total, o_subtotal, o_customer_notes, p_name,
            oi_units, oi_units * oi_unit_price as p_subtotal
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
    return None if ctx.deps.active_order is not None else tool_def


async def _hide_when_no_order(
    ctx: RunContext[ChatDeps], tool_def: ToolDefinition
) -> ToolDefinition | None:
    """Hides the tool when there is no active order."""
    return tool_def if ctx.deps.active_order is not None else None


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


def _product_payload(wa_id: str, product: ProductRow) -> dict:
    """Construye el payload de WhatsApp para un producto.

    Si tiene p_image_url usa `type: "image"` (imagen + caption).
    Si no, cae a `type: "text"` para no romper el flujo por falta de foto.
    """
    price = str(product.p_sale_price)
    header = f"*{product.p_name}* — ${price} {product.p_currency}"
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
    c_id = ctx.deps.customer.c_id
    wa_id = ctx.deps.customer.c_whatsapp_id
    logger.info(f"show_products[{c_id=}]: llamado con {p_ids=}")

    if "show_products" in ctx.deps._once:
        return "Los productos ya fueron enviados. No vuelvas a llamar show_products en este turno."

    # --- Validaciones de entrada (no tocan la red) ---
    if not p_ids:
        return "ERROR_VALIDACION: p_ids no puede estar vacío. Selecciona al menos un producto del catálogo."

    catalog = ctx.deps.products

    invalid_ids = [pid for pid in p_ids if pid not in catalog]
    if invalid_ids:
        return f"ERROR_VALIDACION: los p_ids {invalid_ids} no existen en el catálogo. Usa solo ids del catálogo disponible."

    valid = [catalog[pid] for pid in set(p_ids)][:_SHOW_PRODUCTS_CAP]

    # --- Envío secuencial — break en el primer error, no reintenta ---
    sent = 0
    for product in valid:
        p_id = product.p_id
        try:
            await whatsapp_client.post_message(_product_payload(wa_id, product))
        except httpx.HTTPStatusError as e:
            logger.error(
                f"show_products[{c_id=}, {p_id=}]: HTTP {e.response.status_code} — {e.response.text}"
            )
            break
        except httpx.TimeoutException:
            logger.error(f"show_products[{c_id=}, {p_id=}]: timeout")
            break
        except httpx.HTTPError as e:
            logger.error(f"show_products[{c_id=}, {p_id=}]: network error — {e}")
            break
        sent += 1

    if sent == 0:
        # Nada llegó al cliente — no marcamos _once, el LLM puede reintentar o
        # decidir responder por texto.
        return "ERROR_INTERNO: no se pudo enviar el catálogo al cliente. Intenta más tarde."

    ctx.deps._once.add("show_products")
    if sent < len(valid):
        logger.warning(f"show_products[{c_id=}]: envío parcial {sent}/{len(valid)}")
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
    products = ctx.deps.products
    c_id = ctx.deps.customer.c_id
    logger.info(f"create_order[{c_id=}]: {items=}, {delivery_address=}, {delivery_instructions=}")

    # --- Validaciones de entrada (no tocan la DB) ---
    if not items:
        logger.warning(f"create_order[{c_id=}]: items vacío")
        return "ERROR_VALIDACION: items está vacío. Pide al cliente que especifique qué productos quiere."

    if not delivery_address or not delivery_address.strip():
        logger.warning(f"create_order[{c_id=}]: delivery_address vacía")
        return "ERROR_VALIDACION: delivery_address es obligatoria. Pide al cliente su dirección de entrega."

    logger.info(f"create_order[{c_id=}]: iniciando validación de parámetros")

    errors = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"items[{i}]: debe ser un dict con p_id y units.")
            continue
        if "p_id" not in item or "units" not in item:
            errors.append(f"items[{i}]: faltan campos 'p_id' o 'units'.")
            continue

        if item["p_id"] not in ctx.deps.products:
            errors.append(f"items[{i}]: p_id={item['p_id']} no existe en el catálogo.")
        if not isinstance(item["units"], int) or item["units"] < 1:
            errors.append(
                f"items[{i}] (p_id={item.get('p_id')}): units debe ser un entero >= 1, recibido: {item.get('units')}."
            )

    if errors:
        logger.warning(f"create_order[{c_id=}]: errores de validación — {errors}")
        return "ERROR_VALIDACION:\n" + "\n".join(f"- {e}" for e in errors)

    logger.info(f"create_order[{c_id=}]: validaciones OK, procediendo a DB")

    # --- Escritura a DB ---
    try:
        session = ctx.deps.session
        notes = f"Dirección: {delivery_address.strip()} | Instrucciones: {delivery_instructions.strip()}"

        query_args = {
            "o_c_id": ctx.deps.customer.c_id,
            "o_s_id": ctx.deps.store.s_id,
            "o_status": "PENDING_STORE_APPROVAL",
            "o_customer_notes": notes,
            "o_shipping_amount": Decimal("20.0"),
            "o_currency": "MXN",
        }

        logger.info(f"create_order[{c_id=}]: insertando order")
        order_res = await session.execute(insert_order_query, query_args)
        o_id = order_res.scalar()
        logger.info(f"create_order[{c_id=}]: inserción retornó {o_id=}")

        if o_id is None:
            logger.error(f"create_order[{c_id=}]: inserción retornó o_id=None ocurrio un error")

        orderitems_rows = [
            {
                "oi_o_id": o_id,
                "oi_p_id": item["p_id"],
                "oi_units": item["units"],
                "oi_unit_price": products[item["p_id"]].p_sale_price,
            }
            for item in items
        ]

        logger.info(f"create_order[{c_id=}, {o_id=}]: insertando {len(orderitems_rows)} orderitems")
        await session.execute(insert_bulk_orderitems_query, orderitems_rows)
        await session.commit()
        logger.info(f"create_order[{c_id=}, {o_id=}]: commit OK")

        ctx.deps.active_order = await load_order(session, o_id)

    except Exception as e:
        logger.error(f"create_order[{c_id=}]: fallo — {e}")
        logger.debug("create_order traceback:", exc_info=True)
        return "ERROR_INTERNO: No se pudo crear el pedido por un problema técnico. Intenta de nuevo en un momento."

    summary = await order_summary(session, o_id, ctx.deps.customer.c_name)

    if settings.OWNER_WA_ID:
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
async def add_order_item(ctx: RunContext[ChatDeps], p_id: int, units: int) -> str:
    """Agrega unidades de un producto al pedido activo.

    Si el producto ya está en el pedido, suma `units` a la cantidad existente.
    Si no está, lo crea. Retorna ERROR_VALIDACION: si el p_id no existe en el catálogo.

    Args:
        p_id: ID del producto (del catálogo en el system prompt).
        units: Unidades a agregar (>= 1).
    """
    products = ctx.deps.products
    if p_id not in products:
        return f"ERROR_VALIDACION: p_id={p_id} no existe en el catálogo."
    if units < 1:
        return f"ERROR_VALIDACION: units debe ser >= 1, recibido: {units}."

    o_id = ctx.deps.active_order.o_id
    c_id = ctx.deps.customer.c_id
    logger.info(f"add_order_item[{c_id=}, {o_id=}]: {p_id=}, {units=}")

    try:
        session = ctx.deps.session
        item = await load_orderitem(session, o_id, p_id)
        if item:
            await session.execute(
                text("UPDATE orderitems SET oi_units = oi_units + :units WHERE oi_id = :oi_id"),
                {"units": units, "oi_id": item.oi_id},
            )
        else:
            await session.execute(
                text(
                    "INSERT INTO orderitems (oi_o_id, oi_p_id, oi_units, oi_unit_price)"
                    " VALUES (:o_id, :p_id, :units, :price)"
                ),
                {"o_id": o_id, "p_id": p_id, "units": units, "price": products[p_id].p_sale_price},
            )
        await session.commit()
        summary = await order_summary(session, o_id, ctx.deps.customer.c_name)
        return f"Pedido actualizado:\n{summary}"
    except Exception as e:
        logger.error(f"add_order_item[{c_id=}, {o_id=}]: fallo — {e}")
        return "ERROR_INTERNO: No se pudo actualizar el pedido por un problema técnico. Intenta de nuevo en un momento."


@agent.tool(prepare=_hide_when_no_order)
async def reduce_order_item(ctx: RunContext[ChatDeps], p_id: int, units: int) -> str:
    """Reduce la cantidad de un producto en el pedido activo.

    Si la cantidad resultante es <= 0, elimina el ítem. No puede dejar el pedido vacío.
    Retorna ERROR_VALIDACION: si el p_id no está en el pedido.

    Args:
        p_id: ID del producto (del catálogo en el system prompt).
        units: Unidades a reducir (>= 1).
    """
    if p_id not in ctx.deps.products:
        return f"ERROR_VALIDACION: p_id={p_id} no existe en el catálogo."
    if units < 1:
        return f"ERROR_VALIDACION: units debe ser >= 1, recibido: {units}."

    o_id = ctx.deps.active_order.o_id
    c_id = ctx.deps.customer.c_id
    logger.info(f"reduce_order_item[{c_id=}, {o_id=}]: {p_id=}, {units=}")

    try:
        session = ctx.deps.session
        item = await load_orderitem(session, o_id, p_id)
        if item is None:
            return f"ERROR_VALIDACION: p_id={p_id} no está en el pedido."

        new_units = item.oi_units - units
        if new_units <= 0:
            await session.execute(
                text("DELETE FROM orderitems WHERE oi_id = :oi_id"),
                {"oi_id": item.oi_id},
            )
        else:
            await session.execute(
                text("UPDATE orderitems SET oi_units = :units WHERE oi_id = :oi_id"),
                {"units": new_units, "oi_id": item.oi_id},
            )

        remaining = (
            await session.execute(
                text("SELECT COUNT(*) FROM orderitems WHERE oi_o_id = :o_id"), {"o_id": o_id}
            )
        ).scalar()
        if not remaining:
            await session.rollback()
            return "ERROR_VALIDACION: no puedes eliminar todos los ítems del pedido. Usa cancel_order si quieres cancelarlo."

        await session.commit()
        summary = await order_summary(session, o_id, ctx.deps.customer.c_name)
        return f"Pedido actualizado:\n{summary}"
    except Exception as e:
        logger.error(f"reduce_order_item[{c_id=}, {o_id=}]: fallo — {e}")
        return "ERROR_INTERNO: No se pudo actualizar el pedido por un problema técnico. Intenta de nuevo en un momento."


@agent.tool(prepare=_hide_when_no_order)
async def set_order_item_units(ctx: RunContext[ChatDeps], p_id: int, units: int) -> str:
    """Establece la cantidad exacta de un producto en el pedido activo.

    El producto debe estar ya en el pedido. Para agregar un producto nuevo usa add_order_item.
    Retorna ERROR_VALIDACION: si el p_id no está en el pedido.

    Args:
        p_id: ID del producto (del catálogo en el system prompt).
        units: Nueva cantidad exacta (>= 1).
    """
    if p_id not in ctx.deps.products:
        return f"ERROR_VALIDACION: p_id={p_id} no existe en el catálogo."
    if units < 1:
        return f"ERROR_VALIDACION: units debe ser >= 1, recibido: {units}."

    o_id = ctx.deps.active_order.o_id
    c_id = ctx.deps.customer.c_id
    logger.info(f"set_order_item_units[{c_id=}, {o_id=}]: {p_id=}, {units=}")

    try:
        session = ctx.deps.session
        item = await load_orderitem(session, o_id, p_id)
        if item is None:
            return f"ERROR_VALIDACION: p_id={p_id} no está en el pedido."

        await session.execute(
            text("UPDATE orderitems SET oi_units = :units WHERE oi_id = :oi_id"),
            {"units": units, "oi_id": item.oi_id},
        )
        await session.commit()
        summary = await order_summary(session, o_id, ctx.deps.customer.c_name)
        return f"Pedido actualizado:\n{summary}"
    except Exception as e:
        logger.error(f"set_order_item_units[{c_id=}, {o_id=}]: fallo — {e}")
        return "ERROR_INTERNO: No se pudo actualizar el pedido por un problema técnico. Intenta de nuevo en un momento."


@agent.tool(prepare=_hide_when_no_order)
async def remove_order_item(ctx: RunContext[ChatDeps], p_id: int) -> str:
    """Elimina un producto del pedido activo. No puede dejar el pedido vacío.

    Retorna ERROR_VALIDACION: si el p_id no está en el pedido.

    Args:
        p_id: ID del producto a eliminar (del catálogo en el system prompt).
    """
    if p_id not in ctx.deps.products:
        return f"ERROR_VALIDACION: p_id={p_id} no existe en el catálogo."

    o_id = ctx.deps.active_order.o_id
    c_id = ctx.deps.customer.c_id
    logger.info(f"remove_order_item[{c_id=}, {o_id=}]: {p_id=}")

    try:
        session = ctx.deps.session
        item = await load_orderitem(session, o_id, p_id)
        if item is None:
            return f"ERROR_VALIDACION: p_id={p_id} no está en el pedido."

        await session.execute(
            text("DELETE FROM orderitems WHERE oi_id = :oi_id"),
            {"oi_id": item.oi_id},
        )

        remaining = (
            await session.execute(
                text("SELECT COUNT(*) FROM orderitems WHERE oi_o_id = :o_id"), {"o_id": o_id}
            )
        ).scalar()
        if not remaining:
            await session.rollback()
            return "ERROR_VALIDACION: no puedes eliminar todos los ítems del pedido. Usa cancel_order si quieres cancelarlo."

        await session.commit()
        summary = await order_summary(session, o_id, ctx.deps.customer.c_name)
        return f"Pedido actualizado:\n{summary}"
    except Exception as e:
        logger.error(f"remove_order_item[{c_id=}, {o_id=}]: fallo — {e}")
        return "ERROR_INTERNO: No se pudo actualizar el pedido por un problema técnico. Intenta de nuevo en un momento."


# @agent.tool(prepare=_hide_when_no_order)
# async def notify_staff_order_ready(ctx: RunContext[ChatDeps]) -> str: ...


@agent.tool(prepare=_hide_when_no_order)
async def cancel_order(ctx: RunContext[ChatDeps]) -> str:
    """Cancela el pedido activo del cliente.

    Úsala cuando el cliente pida cancelar explícitamente su pedido en curso.
    """
    c_id = ctx.deps.customer.c_id
    o_id = ctx.deps.active_order.o_id
    logger.info(f"cancel_order[{c_id=}, {o_id=}]: iniciando")

    # --- Escritura a DB ---
    try:
        session = ctx.deps.session

        order = await load_order(session, o_id)
        print(order)

        if order is None:
            return f"ERROR_INTERNO: no se encontró el pedido o_id={o_id}."

        if order.o_status in {"CANCELLED", "COMPLETED"}:
            return (
                f"ERROR_VALIDACION: el pedido o_id={o_id} ya está en estado "
                f"{order.o_status} y no puede cancelarse."
            )

        await session.execute(
            text("UPDATE orders SET o_status = 'CANCELLED' WHERE o_id = :o_id"),
            {"o_id": o_id},
        )
        await session.commit()

        ctx.deps.active_order = None
        logger.info(f"cancel_order[{c_id=}, {o_id=}]: cancelado OK")
        return f"Orden o_id={o_id} transicionó de '{order.o_status}' a 'CANCELLED' exitosamente. No hay orden activa"

    except Exception as e:
        logger.error(f"cancel_order[{c_id=}, {o_id=}]: {e}", exc_info=True)
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

    ctx.deps._once.add("escalate_to_staff")
    body = f"🔔 Consulta de *{customer.c_name}* ({customer.c_whatsapp_id}):\n\n{message.strip()}"
    payload = whatsapp_client.encapsulate_text_message(settings.OWNER_WA_ID, body)

    try:
        await whatsapp_client.post_message(payload)
    except httpx.HTTPStatusError as e:
        logger.error(
            f"escalate_to_staff[{customer.c_id=}]: HTTP {e.response.status_code} — {e.response.text}"
        )
        return "ERROR_INTERNO: no se pudo notificar al dueño. Intenta más tarde."
    except httpx.TimeoutException:
        logger.error(f"escalate_to_staff[{customer.c_id=}]: timeout")
        return "ERROR_INTERNO: no se pudo notificar al dueño (timeout). Intenta más tarde."
    except httpx.HTTPError as e:
        logger.error(f"escalate_to_staff[{customer.c_id=}]: network error — {e}")
        return "ERROR_INTERNO: no se pudo notificar al dueño. Intenta más tarde."

    logger.info(f"escalate_to_staff[{customer.c_id=}]: dueño notificado")
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
    active_order: OrderRow = None,
) -> tuple[str, list]:
    """Run the agent and return (response_text, full_message_history).

    history: pydantic-ai ModelMessage list loaded from Conversations.cv_history.
    The system prompt is passed via instructions= and never enters the history.

    Returns:
        Tuple of (response text, all_messages from the run) — the caller persists
        the full history back to Conversations.cv_history.
    """
    once = _history_tool_calls(history) & {"show_products"}

    async with get_session() as session:
        # # Resolve active order before handing control to the agent.
        # active_res = await session.execute(
        #     text("""
        #         SELECT o_id FROM orders
        #         WHERE o_c_id = :c_id
        #           AND o_status NOT IN ('CANCELLED', 'COMPLETED')
        #         ORDER BY o_created_at DESC
        #         LIMIT 1
        #     """),
        #     {"c_id": customer.c_id},
        # )
        # active_order_id = active_res.scalar()

        # active_order_summary = ""
        # if active_order_id is not None:
        #     active_order_summary = await order_summary(session, active_order_id, customer.c_name)

        system_prompt = build_mega_prompt(
            customer_info=customer,
            store_name=store.s_name,
            store_info=store,
            products_info=products,
            active_order=active_order,
        )

        # print(system_prompt)

        deps = ChatDeps(
            customer=customer,
            store=store,
            products=products,
            session=session,
            active_order=active_order,
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
            logger.warning(
                f"agent_generate_response: request limit tras {result.usage().requests} requests — {e}"
            )
            final = await _direct_agent.run(
                message,
                message_history=result.all_messages(),
                instructions=system_prompt
                + "\nResponde directamente al cliente ahora, sin usar herramientas. "
                "NO prometas acciones que aún no se completaron (crear pedido, confirmar, etc.). "
                "Si aún falta información del cliente, haz la pregunta de clarificación que corresponde.",
            )
            return final.output.response, final.all_messages()
