"""
Phase router for the Yalti chatbot.

A lightweight classifier agent (no tools, structured output only) that reads
the incoming message + conversation history and suggests which ConversationPhase
should handle the response.

The router NEVER writes to the DB and NEVER executes transitions directly.
Code in _validate_phase_transition() enforces which transitions are valid.
"""

import logging

from chatbot_schema import ConversationPhase
from pydantic import BaseModel, Field
from pydantic_ai import Agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------
class PhaseRouterOutput(BaseModel):
    phase: ConversationPhase = Field(
        description="La fase más apropiada para manejar el mensaje actual."
    )
    reasoning: str = Field(
        description="Explicación breve de por qué se eligió esa fase. Solo para debugging."
    )


# ---------------------------------------------------------------------------
# Router agent — no tools, classification only
# ---------------------------------------------------------------------------
_ROUTER_PROMPT = """\
Eres un clasificador de intención para un chatbot de tienda online en WhatsApp.
Dado el último mensaje del cliente y el historial de la conversación, elige
la fase que debe manejar la respuesta.

FASES DISPONIBLES:
- GREETING: El cliente inicia o retoma la conversación con un saludo o sin
  intención clara. Usar solo si no hay historial previo relevante.
- QA_LOOP: El cliente hace preguntas sobre productos, precios, disponibilidad,
  horarios, zonas de entrega, métodos de pago, promociones u otros temas de
  la tienda.
- ORDER_BUILDING: El cliente expresa intención explícita de comprar
  (quiero ordenar, dame X unidades de Y, cómo pido, etc.).

REGLAS:
- Si hay historial previo (conversación ya iniciada), no regreses a GREETING.
- Solo elige ORDER_BUILDING si el cliente expresa intención de compra explícita.
- Si hay ambigüedad entre QA_LOOP y ORDER_BUILDING, elige QA_LOOP.
- Responde únicamente con la fase correcta y un razonamiento breve.
"""

_router_agent: Agent[None, PhaseRouterOutput] = Agent(
    model="openai:gpt-4o-mini",
    name="phase-router",
    output_type=PhaseRouterOutput,
)

# ---------------------------------------------------------------------------
# Phase classification
# ---------------------------------------------------------------------------

# Stable phases sustain multi-turn exchanges within themselves.
# Once one is established (history exists), the executor's structured output
# signals transitions via `suggested_next_phase` — no router call needed.
_STABLE_PHASES = {
    ConversationPhase.QA_LOOP,
    ConversationPhase.ORDER_BUILDING,
    ConversationPhase.COLLECTING_DETAILS,
    ConversationPhase.PENDING_DELIVERY,
    ConversationPhase.DELIVERY_IN_COURSE,
}

# Phases that can only be advanced by owner commands — router can never set them
_OWNER_ONLY_PHASES = {
    ConversationPhase.PENDING_APPROVAL,
    ConversationPhase.PENDING_PAYMENT,
    ConversationPhase.PENDING_DELIVERY,
    ConversationPhase.DELIVERY_IN_COURSE,
    ConversationPhase.COMPLETED,
}

# Allowed router-driven transitions per current phase
_ALLOWED_TRANSITIONS: dict[ConversationPhase, set[ConversationPhase]] = {
    ConversationPhase.GREETING: {
        ConversationPhase.GREETING,
        ConversationPhase.QA_LOOP,
        ConversationPhase.ORDER_BUILDING,
    },
    ConversationPhase.QA_LOOP: {
        ConversationPhase.QA_LOOP,
        ConversationPhase.ORDER_BUILDING,
    },
    ConversationPhase.ORDER_BUILDING: {
        ConversationPhase.QA_LOOP,  # Customer changed their mind
        ConversationPhase.ORDER_BUILDING,
    },
}


def validate_phase_transition(
    current: ConversationPhase,
    suggested: ConversationPhase,
) -> ConversationPhase:
    """Pure-code guard: enforces which transitions are valid.

    Used both by the router (pre-execution) and by yalti (post-execution,
    when the executor signals a transition via suggested_next_phase).
    Owner-only phases and unknown transitions fall back to `current`.
    """
    if suggested in _OWNER_ONLY_PHASES:
        logger.warning("Suggested owner-only phase %s from %s — ignoring", suggested, current)
        return current

    allowed = _ALLOWED_TRANSITIONS.get(current, {current})
    if suggested not in allowed:
        logger.warning("Disallowed transition %s → %s — ignoring", current, suggested)
        return current

    return suggested


async def route_phase(
    message: str,
    history: list,
    current_phase: ConversationPhase,
) -> ConversationPhase:
    """Classify the incoming message and return the phase that should handle it.

    Skips the LLM call when:
    - Phase is owner-only (can only advance via owner commands), or
    - Phase is stable and history exists (executor signals transitions instead).

    Never raises: on any error it falls back to `current_phase`.
    """
    if current_phase in _OWNER_ONLY_PHASES:
        return current_phase

    if current_phase in _STABLE_PHASES and len(history) > 0:
        logger.debug("Router skipped — stable phase %s with existing history", current_phase)
        return current_phase

    try:
        result = await _router_agent.run(
            message,
            message_history=history,
            instructions=_ROUTER_PROMPT,
        )
        suggested = result.output.phase
        logger.info(
            "Router: %s → %s | reason: %s",
            current_phase.value,
            suggested.value,
            result.output.reasoning,
        )
        return validate_phase_transition(current_phase, suggested)
    except Exception:
        logger.exception("Phase router failed, falling back to current phase %s", current_phase)
        return current_phase
