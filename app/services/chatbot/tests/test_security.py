"""Tests for decorators/security module."""

import hashlib
import hmac

import pytest
from config import settings

from app.services.chatbot.security import validate_signature


class TestValidateSignature:
    def _make_sig(self, payload: str) -> str:
        return hmac.new(
            settings.APP_SECRET.encode("latin-1"),
            msg=payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

    def test_valid_signature(self):
        payload = '{"test": true}'
        sig = self._make_sig(payload)
        assert validate_signature(payload, sig) is True

    def test_invalid_signature(self):
        assert validate_signature('{"test": true}', "invalidsig") is False

    def test_empty_payload(self):
        sig = self._make_sig("")
        assert validate_signature("", sig) is True

    def test_tampered_payload(self):
        payload = '{"original": true}'
        sig = self._make_sig(payload)
        assert validate_signature('{"tampered": true}', sig) is False
