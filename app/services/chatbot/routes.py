import asyncio
import logging

import database  # noqa: F401 — must be imported first to add chatbot_schema to sys.path
from config import settings
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from security import verify_signature
from whatsapp_utils import (
    is_valid_whatsapp_message,
    process_whatsapp_message,
)

router = APIRouter()


def _log_task_exception(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        logging.exception("Background task failed", exc_info=task.exception())


@router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}


@router.get("/webhook")
async def webhook_get(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    """Required webhook verification for WhatsApp."""
    print(settings.VERIFY_TOKEN)
    return PlainTextResponse(hub_challenge or "")
    if hub_mode and hub_verify_token:
        if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
            logging.info("WEBHOOK_VERIFIED")
            return PlainTextResponse(hub_challenge or "")
        else:
            logging.info("VERIFICATION_FAILED")
            return JSONResponse(
                {"status": "error", "message": "Verification failed"}, status_code=403
            )
    else:
        logging.info("MISSING_PARAMETER")
        return JSONResponse({"status": "error", "message": "Missing parameters"}, status_code=400)


@router.post("/webhook", dependencies=[Depends(verify_signature)], response_model=None)
async def webhook_post(request: Request) -> dict[str, str] | JSONResponse:
    """Handle incoming webhook events from the WhatsApp API.

    Every message send will trigger 4 HTTP requests to your webhook:
    message, sent, delivered, read.
    """
    body = await request.json()

    if not is_valid_whatsapp_message(body):
        return JSONResponse(
            {"status": "error", "message": "Not a WhatsApp API event"},
            status_code=404,
        )

    # Check if it's a WhatsApp status update
    if body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("statuses"):
        logging.info("Received a WhatsApp status update.")
        return {"status": "ok"}

    task = asyncio.create_task(process_whatsapp_message(body))
    task.add_done_callback(_log_task_exception)
    # process_whatsapp_message(body)
    return {"status": "ok"}
