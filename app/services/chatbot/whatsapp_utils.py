import asyncio
import logging
import re
from collections import OrderedDict

import httpx
import whatsapp_client
from config import settings
from database import get_session
from dbutils import (
    insert_message,
    load_active_order,
    load_conversation,
    products_cache,
    store_cache,
    update_conversation,
    update_message_status,
    upsert_customer,
)
from queries import (
    get_order_query,
    update_order_cancelled_with_reason_query,
    update_order_status_query,
)
from sqlalchemy import text
from yalti import agent_generate_response

logger = logging.getLogger(__name__)

MAX_USER_BUFFERS = 50
DEBOUNCE_SECONDS = 4  # Tiempo de espera antes de procesar mensajes acumulados


class WhatsappUser:
    """Estructura simplificada para representar un contacto de WhatsApp."""

    __slots__ = ("wa_id", "name", "phone")

    def __init__(self, wa_id: str, name: str, phone: str | None = None):
        self.wa_id = wa_id
        self.name = name
        self.phone = phone


class WhatsappMessage:
    """Estructura simplificada para representar un mensaje de WhatsApp relevante para el chatbot."""

    __slots__ = ("id", "contact", "timestamp", "text", "type")

    def __init__(self, id: str, contact: WhatsappUser, timestamp: int, text: str, type: str):
        self.id = id
        self.contact = contact
        self.timestamp = timestamp
        self.text = text
        self.type = type


# ---------------------------------------------------------------------------
# Buffer per user: O(1) dedup + timestamp-ordered flush via Timsort
# ---------------------------------------------------------------------------
class UserMessageBuffer:
    """Buffer de mensajes por usuario con deduplicación LRU y orden por timestamp.

    Internamente combina:
    - OrderedDict como cache LRU para dedup en O(1)
    - list con tupla (timestamp, seq, text) + Timsort en flush para orden
      temporal con desempate FIFO via contador monótono.
    """

    __slots__ = ("_seen", "_messages", "_seq", "_max_seen", "_debounce_timer")

    def __init__(self, max_seen: int = 50):
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._messages: list[tuple[int, int, str]] = []  # (timestamp, seq, text)
        self._seq: int = 0
        self._max_seen: int = max_seen
        self._debounce_timer: asyncio.Task | None = None

    def is_duplicate(self, message: WhatsappMessage) -> bool:
        """Retorna True si el message_id ya fue visto. Si no, lo registra."""
        if message.id in self._seen:
            return True
        self._seen[message.id] = None
        if len(self._seen) > self._max_seen:
            self._seen.popitem(last=False)
        return False

    def add_message(self, message: WhatsappMessage) -> None:
        """Inserta un mensaje en el buffer."""
        self._seen[message.id] = None
        self._messages.append((message.timestamp, self._seq, message.text))
        self._seq += 1

    async def wait_for_more_messages(self) -> None:
        """Espera el periodo de debounce. Se cancela si otra tarea llama a este método."""
        if self._debounce_timer is not None and not self._debounce_timer.done():
            self._debounce_timer.cancel()
        self._debounce_timer = asyncio.current_task()
        await asyncio.sleep(DEBOUNCE_SECONDS)

    def flush(self) -> str:
        """Extrae todos los mensajes en orden de timestamp. O(n) si casi-ordenados."""
        self._messages.sort()
        combined_message = "\n".join([text for _, _, text in self._messages])
        self._messages.clear()
        self._seq = 0
        return combined_message


# Un buffer por usuario, creado lazily con evicción LRU
_user_buffers: OrderedDict[str, UserMessageBuffer] = OrderedDict()


def get_userbuffer(wa_id: str) -> UserMessageBuffer:
    """Obtiene o crea el buffer para un usuario. Evicta el más antiguo si se excede el límite."""

    if wa_id in _user_buffers:
        _user_buffers.move_to_end(wa_id)
        return _user_buffers[wa_id]

    user_buffer = UserMessageBuffer()
    _user_buffers[wa_id] = user_buffer

    if len(_user_buffers) > MAX_USER_BUFFERS:
        _user_buffers.popitem(last=False)

    return user_buffer


# ---------------------------------------------------------------------------
# Extracción de texto según tipo de mensaje
# ---------------------------------------------------------------------------
_UNSUPPORTED_TYPE_RESPONSE = {
    "audio": "🎤 Recibí tu nota de voz pero por el momento solo puedo leer mensajes de texto. ¿Podrías escribirme tu consulta?",
    "image": "📷 Recibí tu imagen pero por ahora solo puedo procesar texto. ¿Me describes lo que necesitas?",
    "video": "🎥 Recibí tu video pero por el momento solo manejo texto. ¿Me cuentas qué necesitas?",
    "document": "📄 Recibí tu documento pero aún no puedo procesarlo. ¿Me escribes tu consulta?",
    "sticker": "😄 ¡Buen sticker! ¿En qué te puedo ayudar?",
    "location": "📍 Recibí tu ubicación, pero por ahora solo puedo responder mensajes de texto.",
    "contacts": "👤 Recibí el contacto, pero no puedo procesarlo. ¿Me escribes lo que necesitas?",
    "reaction": None,  # Las reacciones se ignoran silenciosamente
}


def struct_message_from_payload(body) -> WhatsappMessage | None:
    """Extrae un WhatsappMessage de la estructura del webhook, o retorna None si no es válido."""
    try:
        entry = body["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        contact_info = value["contacts"][0]
        message_info = value["messages"][0]

        contact = WhatsappUser(
            wa_id=contact_info["wa_id"],
            name=contact_info["profile"]["name"],
            phone=value["metadata"]["display_phone_number"],
        )

        if message_info.get("type") == "text":
            return WhatsappMessage(
                id=message_info.get("id", ""),
                contact=contact,
                timestamp=int(message_info.get("timestamp", 0)),
                text=message_info.get("text", {}).get("body", ""),
                type=message_info.get("type", ""),
            )
        else:
            raise ValueError(f"Unsupported message type: {message_info.get('type')}")

    except (KeyError, IndexError, TypeError, ValueError) as e:
        logger.warning(f"Failed to extract message from webhook body: {e}")
        return None


# def _struct_message_from_payload_text(message: dict) -> str | None:
#     """Extrae el texto del mensaje. Retorna None si debe ignorarse, o un string
#     de aviso si el tipo no está soportado."""
#     msg_type = message.get("type", "")

#     if msg_type == "text":
#         return message["text"]["body"]

#     # Imagen/video/documento con caption → usar el caption como texto
#     if msg_type in ("image", "video", "document"):
#         caption = message.get(msg_type, {}).get("caption")
#         if caption:
#             return caption

#     # Interactive (botones, listas) → extraer el texto seleccionado
#     if msg_type == "interactive":
#         interactive = message.get("interactive", {})
#         reply = interactive.get("button_reply") or interactive.get("list_reply")
#         if reply:
#             return reply.get("title", "")

#     # Tipo no soportado → retornar aviso o None para ignorar
#     if msg_type in _UNSUPPORTED_TYPE_RESPONSE:
#         return _UNSUPPORTED_TYPE_RESPONSE[msg_type]

#     logger.warning("Unknown message type: %s", msg_type)
#     return None


# ---------------------------------------------------------------------------
# WhatsApp API helpers
# ---------------------------------------------------------------------------
def log_http_response(response: httpx.Response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


async def send_text_message(data: dict, whatsapp_id: str) -> httpx.Response | None:
    """Envía un mensaje al API de WhatsApp Cloud."""
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }

    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{whatsapp_id}/messages"

    print(f"Sending message to {whatsapp_id} via WhatsApp API:", data)
    return

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, headers=headers, timeout=10)
            response.raise_for_status()
        except httpx.TimeoutException:
            logging.error("Timeout occurred while sending message")
            return
        except httpx.HTTPStatusError as e:
            logging.error(f"Request failed due to: {e} — body: {e.response.text}")
            return
        except httpx.HTTPError as e:
            logging.error(f"Request failed due to: {e}")
            return
        else:
            log_http_response(response)
            return response


def parse_text_for_whatsapp(text: str) -> str:
    """Adapta el texto generado por el LLM al formato de WhatsApp."""
    # Remove brackets
    text = re.sub(r"\【.*?\】", "", text).strip()
    # Convert double asterisks to single asterisks (WhatsApp bold)
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    return text


# ---------------------------------------------------------------------------
# Owner command handler
# ---------------------------------------------------------------------------
async def handle_approve(args: str) -> None:
    """Handles /approve <order_id>. Requires a valid order_id."""
    usage = "Uso: /aprobar <order_id>\nejemplo: /aprobar 42"

    # Validacion, esta el order_id y es un numero?
    if not args or not args.strip().isdigit():
        await send_text_message(settings.OWNER_WA_ID, f"Debes indicar el ID de la orden.\n{usage}")
        return

    o_id = int(args.strip())

    # Verificar que la orden exista y esté pendiente de aprobación. Extraer la info del cliente para notificarlo.
    async with get_session() as session:
        query_args = {"o_id": o_id, "o_status": "PENDING_STORE_APPROVAL"}
        row = await session.execute(get_order_query, query_args).mappings().first()

        # Si no se encuentra la orden o no está en estado correcto, notificar al dueño y salir
        if row is None:
            await send_text_message(
                settings.OWNER_WA_ID,
                f"No se encontró la orden #{o_id} pendiente de aprobación.\n{usage}",
            )
            return

        # Actualizar el estado de la orden a 'APPROVED_PENDING_PAYMENT'
        query_args = {"o_id": o_id, "o_status": "APPROVED_PENDING_PAYMENT"}
        result = await session.execute(update_order_status_query, query_args)

    if result.rowcount == 0:
        logger.warning(
            f"No se pudo actualizar la orden {o_id} — posible condición de carrera o error"
        )
        # TODO: definir si tambien se debe de notificar al owner sobre el error
        return

    logger.info(f"Store approved {o_id=}")

    await send_text_message(
        row["c_whatsapp_id"],
        f"Tu orden #{o_id} fue aprobada."
        "Transfiere a la siguiente cuenta y comparte tu comprobante para proceder al envio:"
        ""
        "Banco: EjemploBank"
        "Cuenta: 123456789"
        "Titular: Tienda Ejemplo",
    )  # TODO: idealmente esto no estaría hardcodeado sino que vendría de la DB en StoreRow

    await send_text_message(
        settings.OWNER_WA_ID,
        f"✅ Orden #{o_id} aprobada."
        f"Mandé la informacion de pago a {row['c_phone']}. Contactalo para coordinar el pago.",
    )


async def handle_reject(args: str) -> None:
    """Handles /reject <o_id> [motivo]. Requires a valid o_id."""
    usage = "Uso: /rechazar <o_id> <motivo>\nejemplo: /rechazar 42 sin producto disponible"
    parts = args.strip().split(maxsplit=1) if args.strip() else []

    if not parts or not parts[0].isdigit():
        await send_text_message(settings.OWNER_WA_ID, f"Debes indicar el ID de la orden.\n{usage}")
        return

    o_id = int(parts[0])
    o_cancel_reason = parts[1].strip() if len(parts) > 1 else None

    async with get_session() as session:
        query_args = {"o_id": o_id, "o_status": "PENDING_STORE_APPROVAL"}
        row = await session.execute(get_order_query, query_args).mappings().first()

        if row is None:
            await send_text_message(
                settings.OWNER_WA_ID,
                f"No se encontró la orden #{o_id} pendiente de aprobación.\n{usage}",
            )
            return

        # Actualizar el estado de la orden a 'CANCELLED'
        query_args = {"o_id": o_id, "o_status": "CANCELLED"}
        if o_cancel_reason:
            query_args["o_cancel_reason"] = o_cancel_reason
            result = await session.execute(update_order_cancelled_with_reason_query, query_args)
        else:
            result = await session.execute(update_order_status_query, query_args)

        if result.rowcount == 0:
            logger.warning(
                f"No se pudo actualizar la orden {o_id} — posible condición de carrera o error"
            )
            # TODO: definir si tambien se debe de notificar al owner sobre el error
            return

    logger.info("Owner rejected o_id=%s reason=%r", o_id, o_cancel_reason)

    reason_line = f"\nMotivo: {o_cancel_reason}" if o_cancel_reason else ""
    await send_text_message(
        row["c_whatsapp_id"],
        f"❌️ Tu orden #{o_id} fue rechazada.{reason_line}\n\n¿Puedo ayudarte con algo más?",
    )
    await send_text_message(
        settings.OWNER_WA_ID,
        f"❌️ Orden #{o_id} rechazada. Notifiqué al cliente.",
    )


async def handle_owner_command(message: WhatsappMessage) -> None:
    """Dispatches slash commands from the store owner.

    Free-text messages are ignored while there is no active HUMAN_TAKEOVER.
    """
    text_body = message.text.strip()
    if not text_body.startswith("/"):
        logger.info("Owner sent free-text (no active takeover): %r", text_body)
        return

    command, _, args = text_body[1:].partition(" ")
    command = command.lower().strip()
    args = args.strip()
    logger.info("Owner command: /%s args=%r", command, args)

    if command == "aprovar":
        await handle_approve(args)
    elif command == "rechazar":
        await handle_reject(args)
    else:
        logger.info("Unknown owner command: /%s", command)


# ---------------------------------------------------------------------------
# Customer message processing
# ---------------------------------------------------------------------------
async def process_whatsapp_message(body: dict):
    """Punto de entrada principal para mensajes entrantes de WhatsApp.

    Flujo:
    1. Detecta si el mensaje viene del dueño → despacha handle_owner_command.
    2. Si es un cliente → dedup + debounce.
    3. Carga (phase, history) de la DB — sesión cerrada antes del LLM call.
    4. LLM call sin conexión a DB abierta.
    5. Persiste history actualizado — nueva sesión corta.
    """
    incoming_message = struct_message_from_payload(body)
    if incoming_message is None:
        logger.warning("Received invalid WhatsApp message structure, ignoring.")
        return

    if incoming_message.contact.wa_id == settings.OWNER_WA_ID:
        await handle_owner_command(incoming_message)
    else:
        await handle_customer_message(incoming_message)


async def handle_customer_message(incoming_message: WhatsappMessage) -> None:
    user_buffer = get_userbuffer(incoming_message.contact.wa_id)

    if user_buffer.is_duplicate(incoming_message):
        logger.info(
            "Duplicate message %s from %s, skipping",
            incoming_message.id,
            incoming_message.contact.wa_id,
        )
        return

    # Agrega el mensaje al buffer y espera un momento para acumular posibles mensajes adicionales
    # del mismo usuario que lleguen en rápida sucesión (e.g., si el cliente envía varios mensajes seguidos).
    user_buffer.add_message(incoming_message)
    await user_buffer.wait_for_more_messages()
    combined_messages = user_buffer.flush()

    if not combined_messages:
        return

    wa_id = incoming_message.contact.wa_id
    name = incoming_message.contact.name
    phone = incoming_message.contact.phone
    logger.info(f"Processing buffered messages from {wa_id}: {combined_messages}")

    try:
        # Phase 1: pre-LLM DB work — get customer, load history, persist inbound message
        async with get_session() as session:
            customer = await upsert_customer(session, wa_id, phone, name)
            history = await load_conversation(session, customer.c_id)
            active_order = await load_active_order(session, customer.c_id)
            store = await store_cache.aget(session)
            products = await products_cache.aget(session)
            inbound_id = await insert_message(session, customer.c_id, "INBOUND", combined_messages)

        # Phase 2: LLM call — agent opens its own session via ChatDeps
        response_text, all_messages = await agent_generate_response(
            message=combined_messages,
            customer=customer,
            store=store,
            products=products,
            history=history,
            active_order=active_order,
        )

        response_text = parse_text_for_whatsapp(response_text)

        # Phase 3: post-LLM DB work — persist response and update inbound status
        async with get_session() as session:
            await insert_message(session, customer.c_id, "OUTBOUND", response_text, "SENT")
            await update_message_status(session, inbound_id, "PROCESSED")
            await update_conversation(session, customer.c_id, all_messages)

        outbound_message = whatsapp_client.encapsulate_text_message(wa_id, response_text)
        await send_text_message(outbound_message, wa_id)
    except Exception:
        logger.exception("Failed to process messages from %s", wa_id)


def is_valid_whatsapp_message(body: dict) -> bool:
    """Check if the incoming webhook event has a valid WhatsApp message structure."""
    return bool(
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
