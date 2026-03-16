import hashlib
import hmac
import logging

from config import settings
from fastapi import HTTPException, Request


def validate_signature(payload: str, signature: str) -> bool:
    """Validate the incoming payload's signature against our expected signature."""
    expected_signature = hmac.new(
        bytes(settings.APP_SECRET, "latin-1"),
        msg=payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


async def verify_signature(request: Request) -> None:
    """FastAPI dependency that verifies the X-Hub-Signature-256 header."""
    signature = request.headers.get("X-Hub-Signature-256", "")[7:]  # Remove 'sha256='
    body = await request.body()
    if not validate_signature(body.decode("utf-8"), signature):
        logging.info("Signature verification failed!")
        raise HTTPException(status_code=403, detail="Invalid signature")
