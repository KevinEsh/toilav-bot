import asyncio
import json
import logging
import re
from collections import OrderedDict

import httpx
from config import settings
from yalti import agent_generate_response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Buffer por usuario: dedup O(1) + orden por timestamp via Timsort
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
    # TODO: evaluar si esto puede causar problemas (ej. caption vacío, o mensaje que no es realmente una consulta)
    if msg_type in ("image", "video", "document"):
        caption = message.get(msg_type, {}).get("caption")
        if caption:
            return caption

    # Interactive (botones, listas) → extraer el texto seleccionado
    # Esto es importante para que las respuestas a botones/listas también pasen por el LLM y mantengan contexto, en lugar de responder con un mensaje fijo.
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


def log_http_response(response: httpx.Response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def encapsulate_text_message(recipient: str, text: str) -> str:
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
    # Remove brackets
    text = re.sub(r"\【.*?\】", "", text).strip()
    # Convert double asterisks to single asterisks (WhatsApp bold)
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    return text


async def process_whatsapp_message(body: dict):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_type = message.get("type", "")
    message_id = message.get("id", "")
    timestamp = int(message.get("timestamp", 0))

    # Si es un tipo no soportado, ignorar silenciosamente
    if message_type in _UNSUPPORTED_TYPE_RESPONSE:
        return

    buf = _get_buffer(wa_id)
    buf.name = name

    # 1. Deduplicación: ignorar mensajes ya procesados
    if buf.is_duplicate(message_id):
        logger.info("Duplicate message %s from %s, skipping", message_id, wa_id)
        return

    # 2. Extraer texto según tipo de mensaje
    message_text = _extract_message_text(message)

    if message_text is None:
        return

    # 3. Acumular mensaje y esperar debounce
    buf.add_message(timestamp, message_text)
    await buf.wait_for_more_messages()

    # 4. Procesar mensajes acumulados
    combined_messages = buf.flush()
    logger.info("Processing buffered messages from %s: %s", wa_id, combined_messages)

    try:
        agent_response = await agent_generate_response(combined_messages, wa_id, buf.name)
        agent_response = parse_text_for_whatsapp(agent_response)

        data = encapsulate_text_message(wa_id, agent_response)
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
