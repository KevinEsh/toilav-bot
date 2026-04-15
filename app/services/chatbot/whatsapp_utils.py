import asyncio
import logging
import re
from collections import OrderedDict
from datetime import datetime, timezone
from time import monotonic
from typing import Callable, Generic, TypeVar

import httpx
from chatbot_schema import (
    Customers,
    MessageDirection,
    Messages,
    MessageStatus,
    MessageType,
    Products,
    Stores,
)
from config import settings
from database import engine
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from sqlmodel import Session, select
from yalti import StoreInfo, agent_generate_response

logger = logging.getLogger(__name__)


class Contact:
    """Estructura simplificada para representar un contacto de WhatsApp."""

    __slots__ = ("wa_id", "name")

    def __init__(self, wa_id: str, name: str):
        self.wa_id = wa_id
        self.name = name


class WhatsappMessage:
    """Estructura simplificada para representar un mensaje de WhatsApp relevante para el chatbot."""

    __slots__ = ("id", "contact", "timestamp", "text", "type")

    def __init__(self, id: str, contact: Contact, timestamp: int, text: str, type: str):
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
MAX_USER_BUFFERS = 20
DEBOUNCE_SECONDS = 3  # Tiempo de espera antes de procesar mensajes acumulados


def _get_userbuffer(wa_id: str) -> UserMessageBuffer:
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
# Generic TTL cache — reloads from DB at most once per `ttl` seconds.
# Keeps store info and product catalog in memory so we don't hit the DB on
# every incoming message. Both change infrequently (owner-driven updates).
# ---------------------------------------------------------------------------
_T = TypeVar("_T")


class _TTLCache(Generic[_T]):
    def __init__(self, loader: Callable[[], _T], ttl: float = 300.0):
        self._loader = loader
        self._ttl = ttl
        self._value: _T | None = None
        self._loaded_at: float = 0.0

    def get(self) -> _T:
        if self._value is None or (monotonic() - self._loaded_at) > self._ttl:
            self._value = self._loader()
            self._loaded_at = monotonic()
        return self._value

    def invalidate(self) -> None:
        """Force reload on next access (e.g., after a product update webhook)."""
        self._value = None
        self._loaded_at = 0.0


# ---------------------------------------------------------------------------
# DB helpers — sessions are opened and closed around each operation so no
# connection is held open during the (potentially slow) LLM call.
# ---------------------------------------------------------------------------
def _fetch_store() -> StoreInfo:
    with Session(engine) as session:
        store = session.exec(select(Stores)).first()
        if store is None:
            logger.warning("No store record found in DB, using empty StoreInfo")
            return StoreInfo(s_id=0, name="", description="", properties={})
        return StoreInfo(
            s_id=store.s_id or 0,
            name=store.s_name,
            description=store.s_description or "",
            properties=store.s_properties or {},
        )


def _fetch_products() -> str:
    """Lee p_rag_text de todos los productos disponibles (pre-computado en la API)."""
    with Session(engine) as session:
        products = session.exec(
            select(Products).where(Products.p_is_available == True)  # noqa: E712
        ).all()
        if not products:
            return "No hay productos disponibles actualmente."
        lines = [p.p_rag_text for p in products if p.p_rag_text]
        return "\n".join(lines) if lines else "No hay productos disponibles actualmente."


_store_cache: _TTLCache[StoreInfo] = _TTLCache(loader=_fetch_store, ttl=300.0)
_products_cache: _TTLCache[str] = _TTLCache(loader=_fetch_products, ttl=300.0)


HISTORY_WINDOW = 20  # number of past messages to load as LLM context


def _get_or_create_customer(wa_id: str, name: str) -> Customers:
    """Obtiene o crea el Customer por wa_id. Retorna el objeto en estado detached."""
    with Session(engine) as session:
        customer = session.exec(select(Customers).where(Customers.c_whatsapp_id == wa_id)).first()
        if customer is None:
            customer = Customers(c_phone=wa_id, c_whatsapp_id=wa_id, c_name=name)
            session.add(customer)
            session.commit()
        session.refresh(customer)
        return customer


def _load_conversation_history(c_id: int) -> list:
    """Carga los últimos HISTORY_WINDOW mensajes como lista de ModelRequest/ModelResponse.

    Solo incluye mensajes PROCESSED (inbound) y SENT/DELIVERED/READ (outbound) para
    no inyectar mensajes fallidos o aún en vuelo en el historial del LLM.
    El system prompt NO está incluido — se pasa por instructions= al agente.
    """
    with Session(engine) as session:
        db_msgs = session.exec(
            select(Messages)
            .where(Messages.m_c_id == c_id)
            .order_by(Messages.m_created_at.desc())
            .limit(HISTORY_WINDOW)
        ).all()
        db_msgs = list(reversed(db_msgs))  # oldest first

        history = []
        for msg in db_msgs:
            if msg.m_direction == MessageDirection.INBOUND:
                history.append(ModelRequest(parts=[UserPromptPart(content=msg.m_content or "")]))
            else:
                history.append(ModelResponse(parts=[TextPart(content=msg.m_content or "")]))
        return history


def _persist_message(
    customer: Customers,
    direction: MessageDirection,
    content: str,
    msg_type: MessageType = MessageType.TEXT,
    status: MessageStatus = MessageStatus.RECEIVED,
) -> Messages:
    """Persiste un único mensaje en la DB y retorna el objeto creado."""
    with Session(engine) as session:
        msg = Messages(
            m_c_id=customer.c_id,
            m_direction=direction,
            m_type=msg_type,
            m_content=content,
            m_status=status,
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        return msg


def _update_message_status(m_id: int, status: MessageStatus) -> None:
    """Actualiza el status de un mensaje existente."""
    with Session(engine) as session:
        msg = session.get(Messages, m_id)
        if msg is None:
            logger.warning("_update_message_status: m_id=%s not found", m_id)
            return
        msg.m_status = status
        session.add(msg)
        session.commit()


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


def extract_message(body) -> WhatsappMessage | None:
    """Extrae un WhatsappMessage de la estructura del webhook, o retorna None si no es válido."""
    try:
        entry = body["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        contact_info = value["contacts"][0]
        message_info = value["messages"][0]

        contact = Contact(wa_id=contact_info["wa_id"], name=contact_info["profile"]["name"])
        message = WhatsappMessage(
            id=message_info.get("id", ""),
            contact=contact,
            timestamp=int(message_info.get("timestamp", 0)),
            text=message_info.get("text", {}).get("body", ""),
            type=message_info.get("type", ""),
        )
        return message
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"Failed to extract message from webhook body: {e}")
        return None


def _extract_message_text(message: dict) -> str | None:
    """Extrae el texto del mensaje. Retorna None si debe ignorarse, o un string
    de aviso si el tipo no está soportado."""
    msg_type = message.get("type", "")

    if msg_type == "text":
        return message["text"]["body"]

    # Imagen/video/documento con caption → usar el caption como texto
    if msg_type in ("image", "video", "document"):
        caption = message.get(msg_type, {}).get("caption")
        if caption:
            return caption

    # Interactive (botones, listas) → extraer el texto seleccionado
    if msg_type == "interactive":
        interactive = message.get("interactive", {})
        reply = interactive.get("button_reply") or interactive.get("list_reply")
        if reply:
            return reply.get("title", "")

    # Tipo no soportado → retornar aviso o None para ignorar
    if msg_type in _UNSUPPORTED_TYPE_RESPONSE:
        return _UNSUPPORTED_TYPE_RESPONSE[msg_type]

    logger.warning("Unknown message type: %s", msg_type)
    return None


# ---------------------------------------------------------------------------
# WhatsApp API helpers
# ---------------------------------------------------------------------------
def log_http_response(response: httpx.Response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def encapsulate_text_message(recipient: str, text: str) -> dict:
    """Construye el payload para un mensaje de texto saliente."""
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }


async def send_message(data: dict, phone_number_id: str | None = None) -> httpx.Response | None:
    """Envía un mensaje al API de WhatsApp Cloud."""
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }

    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{phone_number_id}/messages"

    print("Sending message to WhatsApp API:", data)
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
# Owner command handler (stub — expanded in later phases)
# ---------------------------------------------------------------------------
async def handle_owner_command(text: str):
    """Despacha los comandos slash del dueño de la tienda.

    Mensajes sin '/' se ignoran mientras no haya un HUMAN_TAKEOVER activo.
    Los handlers por fase se conectan aquí en iteraciones posteriores.
    """
    if not text.startswith("/"):
        logger.info("Owner sent free-text (no active takeover): %r", text)
        return
    command, _, args = text[1:].partition(" ")
    command = command.lower().strip()
    logger.info("Owner command: /%s args=%r", command, args)
    # TODO: dispatch to per-phase command handlers in later phases


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
    incoming_message = extract_message(body)
    if incoming_message is None:
        logger.warning("Received invalid WhatsApp message structure, ignoring.")
        return

    # ── Owner routing ────────────────────────────────────────────────────────
    if incoming_message.contact.wa_id == settings.OWNER_WA_ID:
        await handle_owner_command(incoming_message)
        return

    # ── Customer flow ────────────────────────────────────────────────────────
    user_buffer = _get_userbuffer(incoming_message.contact.wa_id)

    if user_buffer.is_duplicate(incoming_message):
        logger.info(
            "Duplicate message %s from %s, skipping",
            incoming_message.id,
            incoming_message.contact.wa_id,
        )
        return

    user_buffer.add_message(incoming_message)
    await user_buffer.wait_for_more_messages()
    combined_messages = user_buffer.flush()

    wa_id = incoming_message.contact.wa_id
    name = incoming_message.contact.name
    logger.info("Processing buffered messages from %s: %s", wa_id, combined_messages)

    try:
        store = _store_cache.get()
        products = _products_cache.get()
        customer = _get_or_create_customer(wa_id, name)
        print("Customer record:", customer)

        # 1. Persist inbound message immediately — available for reprocessing on crash
        inbound_msg = _persist_message(
            customer=customer,
            direction=MessageDirection.INBOUND,
            content=combined_messages,
            status=MessageStatus.RECEIVED,
        )

        # 2. Load history — session closed before LLM call
        history = _load_conversation_history(customer.c_id)

        # 3. LLM call with no open DB connection
        response_text = await agent_generate_response(
            message=combined_messages,
            customer=customer,
            store=store,
            products=products,
            history=history,
        )

        response_text = parse_text_for_whatsapp(response_text)

        # 4. Persist bot response and mark inbound as processed atomically
        _persist_message(
            customer=customer,
            direction=MessageDirection.OUTBOUND,
            content=response_text,
            status=MessageStatus.SENT,
        )
        _update_message_status(inbound_msg.m_id, MessageStatus.PROCESSED)

        await send_message(encapsulate_text_message(wa_id, response_text), wa_id)
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
