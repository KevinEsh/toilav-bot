"""Tests for config module."""

import os

from config import Settings, configure_logging


class TestSettings:
    def test_reads_env_vars(self):
        s = Settings()
        assert s.WHATSAPP_ACCESS_TOKEN == os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        # VERIFY_TOKEN lee de NGROK_VERIFY_TOKEN por diseño actual — ver tech_debt.md
        assert s.VERIFY_TOKEN == os.environ.get("NGROK_VERIFY_TOKEN", "")

    def test_frozen(self):
        """Settings should be immutable."""
        import pytest

        s = Settings()
        with pytest.raises((AttributeError, TypeError)):
            s.WHATSAPP_ACCESS_TOKEN = "new_value"


class TestConfigureLogging:
    def test_does_not_raise(self):
        configure_logging()
