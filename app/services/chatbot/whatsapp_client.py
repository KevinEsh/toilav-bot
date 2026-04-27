"""Cliente HTTP para WhatsApp Cloud Graph API.

Módulo sin dependencias de `yalti` ni `whatsapp_utils` — ambos pueden
importar desde aquí sin ciclo. Centraliza URL, headers, timeout y el
POST mismo. El manejo de errores específico (qué decirle al cliente,
qué código devolver al LLM) queda en el caller, que atrapa las
excepciones `httpx.*` que este módulo deja propagar.
"""

from __future__ import annotations

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


def _messages_url() -> str:
    return (
        f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
        f"/{settings.PHONE_NUMBER_ID}/messages"
    )


async def post_message(payload: dict, timeout: float = 10.0) -> httpx.Response:
    """POST un payload de mensaje al Graph API de WhatsApp.

    Args:
        payload: dict con el body completo (ya incluye `messaging_product`,
            `to`, `type`, y campos específicos del tipo de mensaje).
        timeout: segundos antes de `httpx.TimeoutException`.

    Returns:
        La `httpx.Response` en caso de 2xx.

    Raises:
        httpx.HTTPStatusError: respuesta 4xx/5xx (caller decide mensaje de error).
        httpx.TimeoutException: request superó `timeout`.
        httpx.HTTPError: errores de red / conexión (clase padre).
    """
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    url = _messages_url()
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
    return response
