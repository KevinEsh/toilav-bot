import asyncio
import json
import logging
import re
from collections import OrderedDict
from datetime import datetime, timezone

import httpx
from chatbot_schema import Conversations, ConversationPhase, Customers
from config import settings
from database import get_session
from sqlmodel import select
from yalti import agent_generate_response

logger = logging.getLogger(__name__)


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

    __slots__ = ("wa_id", "name", "_seen", "_messages", "_seq", "_max_seen", "_debounce_timer")

    def __init__(self, wa_id: str, max_seen: int = 50):
        self.wa_id: str = wa_id
        self.name: str = ""
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._messages: list[tuple[int, int, str]] = []  # (timestamp, seq, text)
        self._seq: int = 0
        self._max_seen: int = max_seen
        self._debounce_timer: asyncio.Task | None = None

    def is_duplicate(self, message_id: str) -> bool:
        """Retorna True si el message_id ya fue visto. Si no, lo registra."""
        if message_id in self._seen:
            return True
        self._seen[message_id] = None
        if len(self._seen) > self._max_seen:
            self._seen.popitem(last=False)
        return False

    def add_message(self, timestamp: int, text: str) -> None:
        """Inserta un mensaje en el buffer."""
        self._messages.append((timestamp, self._seq, text))
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
        return combined_message


# Un buffer por usuario, creado lazily con evicción LRU
_user_buffers: OrderedDict[str, UserMessageBuffer] = OrderedDict()
MAX_USER_BUFFERS = 20
DEBOUNCE_SECONDS = 5  # Tiempo de espera antes de procesar mensajes acumulados


def _get_buffer(wa_id: str) -> UserMessageBuffer:
    """Obtiene o crea el buffer para un usuario. Evicta el más antiguo si se excede el límite."""
    if wa_id in _user_buffers:
        _user_buffers.move_to_end(wa_id)
        return _user_buffers[wa_id]
    buf = UserMessageBuffer(wa_id)
    _user_buffers[wa_id] = buf
    if len(_user_buffers) > MAX_USER_BUFFERS:
        _user_buffers.popitem(last=False)
    return buf


# ---------------------------------------------------------------------------
# DB helpers — sessions are opened and closed around each operation so no
# connection is held open during the (potentially slow) LLM call.
# ---------------------------------------------------------------------------
def _load_conversation(wa_id: str, name: str) -> tuple[ConversationPhase, list]:
    """Upsert Customer + Conversation, return (phase, history) as plain values.

    The session is opened, committed, and closed here — not passed downstream.
    """
    for session in get_session():
        customer = session.exec(
            select(Customers).where(Customers.c_whatsapp_id == wa_id)
        ).first()
        if customer is None:
            customer = Customers(c_whatsapp_id=wa_id, c_phone=wa_id, c_name=name)
            session.add(customer)
        elif customer.c_name != name:
            customer.c_name = name

        conv = session.exec(
            select(Conversations).where(Conversations.cv_wa_id == wa_id)
        ).first()
        if conv is None:
            conv = Conversations(cv_wa_id=wa_id)
            session.add(conv)

        session.commit()
        session.refresh(conv)
        # Copy primitive values out before the session closes
        return conv.cv_phase, list(conv.cv_history)


def _persist_conversation(wa_id: str, phase: ConversationPhase, history: list) -> None:
    """Persist the updated phase and history back to the DB after the LLM call."""
    for session in get_session():
        conv = session.exec(
            select(Conversations).where(Conversations.cv_wa_id == wa_id)
        ).first()
        if conv is None:
            return
        conv.cv_phase = phase
        conv.cv_history = history
        conv.cv_updated_at = datetime.now(timezone.utc)
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


def encapsulate_text_message(recipient: str, text: str) -> str:
    """Construye el payload JSON para un mensaje de texto saliente."""
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


async def send_message(data: str):
    """Envía un mensaje al API de WhatsApp Cloud."""
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }

    url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.PHONE_NUMBER_ID}/messages"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, content=data, headers=headers, timeout=10)
            response.raise_for_status()
        except httpx.TimeoutException:
            logging.error("Timeout occurred while sending message")
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
    5. Persiste (phase, history) actualizado — nueva sesión corta.
    """
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_id = message.get("id", "")
    timestamp = int(message.get("timestamp", 0))

    # ── Owner routing ────────────────────────────────────────────────────────
    if wa_id == settings.OWNER_WA_ID:
        text = _extract_message_text(message)
        if text:
            await handle_owner_command(text)
        return

    # ── Customer flow ────────────────────────────────────────────────────────
    buf = _get_buffer(wa_id)
    buf.name = name

    if buf.is_duplicate(message_id):
        logger.info("Duplicate message %s from %s, skipping", message_id, wa_id)
        return

    message_text = _extract_message_text(message)
    if message_text is None:
        return

    buf.add_message(timestamp, message_text)
    await buf.wait_for_more_messages()

    combined_messages = buf.flush()
    logger.info("Processing buffered messages from %s: %s", wa_id, combined_messages)

    try:
        # 1. Load state — session opens and closes here
        phase, history = _load_conversation(wa_id, name)

        # 2. LLM call — no DB connection held during this await
        response_text, new_phase, new_history = await agent_generate_response(
            message=combined_messages,
            wa_id=wa_id,
            name=name,
            phase=phase,
            history=history,
        )

        # 3. Persist updated state — new short session
        _persist_conversation(wa_id, new_phase, new_history)

        response_text = parse_text_for_whatsapp(response_text)
        data = encapsulate_text_message(wa_id, response_text)
        await send_message(data)
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
