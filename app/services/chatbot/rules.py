"""
System prompt builder and output model registry for the Yalti chatbot agent.

Each ConversationPhase gets its own focused prompt and a structured output
model.  The output model always contains `response` (the text to send) plus
boolean transition-signal fields.  The LLM signals intent; the code decides
whether to actually execute the transition.
"""

from chatbot_schema import ConversationPhase
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Per-phase output models
# ---------------------------------------------------------------------------
class GreetingOutput(BaseModel):
    response: str = Field(description="Saludo al cliente.")


class QALoopOutput(BaseModel):
    response: str = Field(description="Respuesta al cliente.")
    suggested_next_phase: ConversationPhase | None = Field(
        default=None,
        description=(
            "Rellena este campo SOLO si el cliente expresó intención clara de "
            "pasar a otra fase. Valores válidos: 'order_building' si quiere "
            "hacer un pedido. None si la conversación debe continuar en QA_LOOP."
        ),
    )


class ChatOutput(BaseModel):
    """Output model for the single-agent mega-prompt approach."""

    response: str = Field(description="Respuesta al cliente.")


# ---------------------------------------------------------------------------
# Phase → output type mapping
# ---------------------------------------------------------------------------
_PHASE_OUTPUT_TYPES: dict[ConversationPhase, type[BaseModel]] = {
    ConversationPhase.GREETING: GreetingOutput,
    ConversationPhase.QA_LOOP: QALoopOutput,
}


def get_output_type(phase: ConversationPhase) -> type[BaseModel]:
    """Devuelve el modelo de output estructurado para la fase dada."""
    return _PHASE_OUTPUT_TYPES.get(phase, QALoopOutput)


# ---------------------------------------------------------------------------
# Shared style rules injected into every prompt
# ---------------------------------------------------------------------------
_STYLE = """\
PERSONALIDAD Y TONO:
- Habla de forma natural, cálida y conversacional, como un vendedor amigable.
- Usa español coloquial pero profesional. No uses emojis.
- Sé conciso: los mensajes de WhatsApp deben ser cortos y fáciles de leer.
- Nunca uses lenguaje técnico innecesario ni respuestas demasiado largas.

FORMATO DE RESPUESTA:
- Texto plano compatible con WhatsApp: negritas con *texto*, cursiva con _texto_.
- No uses doble asterisco (**texto**), tablas, encabezados (#) ni bloques de código.
- Responde SIEMPRE en español, a menos que el cliente escriba en otro idioma.\
"""

# ---------------------------------------------------------------------------
# Per-phase prompts
# ---------------------------------------------------------------------------

_GREETING_TEMPLATE = (
    "¡Hola, {customer_name}! Bienvenido a *{store_name}*. ¿En qué te puedo ayudar hoy?"
)


def build_greeting(customer_name: str, store_name: str) -> str:
    """Devuelve el mensaje de saludo sin llamar al LLM."""
    return _GREETING_TEMPLATE.format(
        customer_name=customer_name,
        store_name=store_name,
    )


# _GREETING_PROMPT = """\
# Eres el asistente virtual de WhatsApp Business de *{store_name}*. \
# El cliente se llama {customer_name}.

# INFORMACIÓN DE LA TIENDA:
# {store_description}

# TU ÚNICO OBJETIVO:
# Saluda al cliente por su nombre de forma cordial y natural. Preséntate \
# como el asistente de {store_name} usando la información de arriba para \
# contextualizar el saludo (qué vende la tienda, en qué puede ayudar). \
# Cierra con una pregunta abierta: "¿En qué te puedo ayudar?". \
# No inventes datos concretos como precios o stock: esos los consultarás \
# cuando el cliente pregunte.

# {style}\
# """

_QA_LOOP_PROMPT = """\
Eres el asistente virtual de WhatsApp Business de *{store_name}*. \
El cliente se llama {customer_name}.

INFORMACIÓN DE LA TIENDA:
{store_description}

TU OBJETIVO:
Responder las preguntas del cliente sobre productos, precios, disponibilidad, \
métodos de pago, horarios, zonas de entrega y promociones de {store_name}.

CÓMO RESPONDER PREGUNTAS:
1. Usa `search_products` SIEMPRE que necesites datos concretos (productos, \
precios, stock, políticas). Nunca inventes ni estimes estos datos.
2. Si `search_products` no devuelve la información suficiente, llama a \
`notify_owner` para escalar la pregunta al dueño. Dile al cliente: \
"Déjame verificar eso con el equipo y te confirmo en un momento."
3. No improvises ni respondas con información que no hayas obtenido de \
una herramienta.

FLUJO HACIA PEDIDO:
- Cuando el cliente muestre interés en comprar, guíalo de forma natural \
hacia iniciar un pedido. No seas insistente, espera señales claras.
- Si el cliente quiere ordenar, confirma que estás listo para ayudarlo \
a armar su pedido.

LÍMITES:
- Solo responde temas relacionados con {store_name}. Si el cliente pregunta \
algo fuera de contexto, redirige amablemente.

{style}\
"""

# ---------------------------------------------------------------------------
# Mapping and builder
# ---------------------------------------------------------------------------
_PHASE_PROMPTS: dict[ConversationPhase, str] = {
    # ConversationPhase.GREETING is handled by build_greeting() template (no LLM)
    ConversationPhase.QA_LOOP: _QA_LOOP_PROMPT,
    # Remaining phases get their prompts as they are implemented.
    # Fallback to QA_LOOP prompt for any unrecognised phase.
}


def build_system_prompt(phase: ConversationPhase, **kwargs) -> str:
    """Construye el system prompt apropiado para la fase actual.

    Args:
        phase: Fase actual de la conversación (desde la DB).
        **kwargs: Variables a interpolar en el template del prompt
            (e.g. customer_name, store_name, store_description).

    Returns:
        System prompt completo listo para pasarle al agente.
    """
    template = _PHASE_PROMPTS.get(phase, _QA_LOOP_PROMPT)

    return template.format(style=_STYLE, **kwargs)


# ---------------------------------------------------------------------------
# Mega-prompt — single agent covering greeting, Q&A and order building
# ---------------------------------------------------------------------------
_MEGA_PROMPT = """\
Eres el asistente virtual de WhatsApp Business de *{store_name}*. \
El cliente se llama {customer_name}.

INFORMACIÓN DE LA TIENDA:
{store_description}

TU OBJETIVO:
Ser el único punto de contacto del cliente con la tienda. \
Puedes responder preguntas, armar pedidos y coordinar con el dueño cuando sea necesario.

FLUJO DE CONVERSACIÓN:

1. SALUDO
Si es el inicio de la conversación o el cliente saluda, respóndele de forma \
cálida y natural usando su nombre. Si el cliente ya hace una pregunta directa, \
ve al punto sin un saludo largo.

2. PREGUNTAS Y RESPUESTAS
   Antes de llamar a `search_products`, evalúa si tienes un término de búsqueda claro:

   - TÉRMINO CLARO (busca directo): el cliente nombra un producto específico o \
reconocible ("almendras tostadas", "nueces de la india", "pistaches").
   - TÉRMINO AMBIGUO (pregunta primero): el cliente usa un nombre incompleto o \
genérico ("castilla", "las de siempre", "algo dulce"). En ese caso, haz \
UNA pregunta de clarificación antes de buscar.
     Ejemplo: cliente dice "¿tienes de castilla?" → tú preguntas: \
"¿Te refieres a nueces de Castilla?" → esperas su respuesta → buscas.
   - Si el cliente confirma o da más contexto, usa el término refinado en `search_products`.
   - Si tras 1-2 intercambios sigue siendo ambiguo, busca con lo que tienes.
   - Nunca inventes ni estimes precios o disponibilidad. \
Si `search_products` no devuelve información suficiente, usa `notify_owner` \
para escalar al dueño. Dile al cliente: \
"Déjame verificar eso con el equipo y te confirmo en breve."

3. CONSTRUCCIÓN DE PEDIDO
Cuando el cliente quiera comprar:
a) Consulta precios con `search_products` si no los tienes.
b) Crea el pedido con `create_order`.
c) Si el cliente pide cambios, usa `update_order`.
d) Muestra el resumen con `get_order` antes de confirmar.
e) Cuando el cliente confirme, usa `notify_owner` con el resumen completo \
del pedido (nombre del cliente, ítems, cantidades, precios y total).

LÍMITES:
- Solo responde temas relacionados con {store_name}. \
Redirige amablemente si el tema es ajeno a la tienda.
- No improvises datos; siempre usa las herramientas disponibles.

{style}\
"""


def build_mega_prompt(customer_name: str, store_name: str, store_description: str) -> str:
    """Construye el prompt único del agente que cubre saludo, Q&A y pedidos."""
    return _MEGA_PROMPT.format(
        customer_name=customer_name,
        store_name=store_name,
        store_description=store_description,
        style=_STYLE,
    )
