from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from rules import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependencias que se inyectan al agente en cada ejecución
# ---------------------------------------------------------------------------
@dataclass
class ChatDeps:
    """Dependencias del agente: identificadores del cliente y su nombre."""

    wa_id: str
    customer_name: str


# ---------------------------------------------------------------------------
# Almacén en memoria del historial de conversación por wa_id
# ---------------------------------------------------------------------------
_conversation_store: dict[str, list] = {}


def _get_history(wa_id: str) -> list:
    return _conversation_store.setdefault(wa_id, [])


# ---------------------------------------------------------------------------
# Agente principal
# ---------------------------------------------------------------------------
agent = Agent(
    model="openai:gpt-4o-mini",
    name="yalti-assistant",
    system_prompt=SYSTEM_PROMPT,
    deps_type=ChatDeps,
)


# ---------------------------------------------------------------------------
# Tool: consulta RAG (stub por ahora)
# ---------------------------------------------------------------------------
@agent.tool
async def consultar_informacion(
    ctx: RunContext[ChatDeps],
    consulta: str,
) -> str:
    """Busca información sobre productos, precios, disponibilidad, horarios,
    ubicación u otros datos de la tienda. Usa esta herramienta siempre que
    necesites datos concretos para responder al cliente.

    Args:
        consulta: La pregunta o tema a buscar en la base de conocimiento.
    """
    # TODO: Conectar con el sistema RAG real (embeddings + vector store)
    logger.info("RAG query from %s: %s", ctx.deps.wa_id, consulta)
    return (
        "No se encontró información específica para esta consulta. "
        "Por favor, indica al cliente que verificarás y le responderás pronto."
    )


# ---------------------------------------------------------------------------
# Función pública que consume el resto de la app
# ---------------------------------------------------------------------------
async def agent_generate_response(message_body: str, wa_id: str, name: str) -> str:
    """Genera una respuesta del chatbot para un mensaje de WhatsApp entrante.

    Mantiene el historial de conversación por ``wa_id`` para dar continuidad
    al diálogo.
    """
    deps = ChatDeps(wa_id=wa_id, customer_name=name)
    history = _get_history(wa_id)
    print(history)

    result = await agent.run(
        message_body,
        deps=deps,
        message_history=history,
    )

    # Actualizar historial con los mensajes nuevos
    history.extend(result.new_messages())

    return result.output
