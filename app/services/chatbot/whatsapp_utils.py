import asyncio
import logging
import re
from collections import OrderedDict

import httpx
from chatbot_schema import ConversationPhase
from config import settings
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
# DB helpers — sessions are opened and closed around each operation so no
# connection is held open during the (potentially slow) LLM call.
# ---------------------------------------------------------------------------
def _load_store() -> StoreInfo:
    """Lee el registro de la tienda y lo devuelve como StoreInfo.

    Asume una sola tienda (single-tenant). La sesión se abre y cierra aquí.
    """
    # for session in get_session():
    #     store = session.exec(select(Stores)).first()
    #     if store is None:
    #         return StoreInfo(name="", description="", properties={})
    return StoreInfo(
        name="Tremenda Nuez",
        description="Tienda de nueces y frutos secos online desde WhatsApp. No tenemos tienda fisica, ya que nuestro objetivo es brindar a nuestros clientes la mejor experiencia de compra desde WhatsApp directamente a su puerta",
        properties={},
    )


# In-memory conversation store — dummy implementation, replace with DB
# TODO: Replace with DB-backed persistence (Conversations table)
_conversation_store: dict[str, tuple[ConversationPhase, list]] = {}


def _load_conversation(contact: Contact) -> tuple[ConversationPhase, list]:
    """Returns (phase, history) for a contact. Creates a new entry if not found."""
    return _conversation_store.get(contact.wa_id, (ConversationPhase.GREETING, []))


def _persist_conversation(wa_id: str, phase: ConversationPhase, history: list) -> None:
    """Saves the updated phase and history to the in-memory store."""
    _conversation_store[wa_id] = (phase, history)


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


async def send_message(data: dict):
    """Envía un mensaje al API de WhatsApp Cloud."""
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }

    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.PHONE_NUMBER_ID}/messages"

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
        store = _load_store()
        phase, history = _load_conversation(incoming_message.contact)

        response_text, new_history = await agent_generate_response(
            message=combined_messages,
            wa_id=wa_id,
            name=name,
            store=store,
            history=history,
        )

        _persist_conversation(wa_id, phase, new_history)
        response_text = parse_text_for_whatsapp(response_text)
        await send_message(encapsulate_text_message(wa_id, response_text))
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
