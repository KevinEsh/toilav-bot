from __future__ import annotations

import logging
from dataclasses import dataclass

from chatbot_schema import ConversationPhase
from pydantic_ai import Agent, RunContext
from rules import build_system_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependencias que se inyectan al agente en cada ejecución
# ---------------------------------------------------------------------------
@dataclass
class ChatDeps:
    """Dependencias del agente: identificadores del cliente y fase actual."""

    wa_id: str
    customer_name: str
    phase: ConversationPhase


# ---------------------------------------------------------------------------
# Agente principal
# ---------------------------------------------------------------------------
agent = Agent(
    model="openai:gpt-4o-mini",
    name="yalti-assistant",
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
async def agent_generate_response(
    message: str,
    wa_id: str,
    name: str,
    phase: ConversationPhase,
    history: list,
) -> tuple[str, ConversationPhase, list]:
    """Genera una respuesta del chatbot para un mensaje de WhatsApp entrante.

    Recibe el historial y la fase como valores planos (sin sesión de DB abierta).
    Devuelve una tupla (response_text, new_phase, new_history) para que el
    llamador pueda persistir los cambios en una sesión separada y breve.

    La fase sólo cambia cuando el código detecta una condición de transición
    (nunca por decisión directa del LLM).

    Args:
        message: Texto del mensaje del cliente (posiblemente combinado tras debounce).
        wa_id: WhatsApp ID del cliente.
        name: Nombre del cliente.
        phase: Fase actual de la conversación según la DB.
        history: Historial serializado de mensajes pydantic-ai.

    Returns:
        Tupla (texto_de_respuesta, fase_nueva, historial_nuevo).
    """
    deps = ChatDeps(wa_id=wa_id, customer_name=name, phase=phase)
    system_prompt = build_system_prompt(phase=phase, customer_name=name)

    result = await agent.run(
        message,
        deps=deps,
        message_history=history,
        system_prompt=system_prompt,
    )

    new_history = history + list(result.new_messages())

    # ── Phase transition logic ───────────────────────────────────────────────
    # The LLM never decides phase changes directly.  Transitions are triggered
    # here by code inspecting the result or structured output.
    # For now: GREETING transitions to QA_LOOP after the first bot response.
    new_phase = phase
    if phase == ConversationPhase.GREETING:
        new_phase = ConversationPhase.QA_LOOP

    return result.output, new_phase, new_history
