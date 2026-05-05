"""Tests for security module."""

import hashlib
import hmac

from config import settings
from security import validate_signature


class TestValidateSignature:
    def _make_sig(self, payload: bytes) -> str:
        return hmac.new(
            settings.APP_SECRET.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

    def test_valid_signature(self):
        payload = b'{"test": true}'
        sig = self._make_sig(payload)
        assert validate_signature(payload, sig) is True

    def test_invalid_signature(self):
        assert validate_signature(b'{"test": true}', "invalidsig") is False

    def test_empty_payload(self):
        sig = self._make_sig(b"")
        assert validate_signature(b"", sig) is True

    def test_tampered_payload(self):
        payload = b'{"original": true}'
        sig = self._make_sig(payload)
        assert validate_signature(b'{"tampered": true}', sig) is False
