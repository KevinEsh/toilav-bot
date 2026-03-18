import asyncio
import os
import sys

import pytest

# Ensure the chatbot package root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required env vars BEFORE any chatbot module gets imported
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test-access-token")
os.environ.setdefault("APP_ID", "test-app-id")
os.environ.setdefault("APP_SECRET", "test-app-secret")
os.environ.setdefault("WHATSAPP_API_VERSION", "v18.0")
os.environ.setdefault("PHONE_NUMBER_ID", "123456789")
os.environ.setdefault("VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("OWNER_WA_ID", "5215512345678")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")


@pytest.fixture
def sample_whatsapp_text_body():
    """Valid WhatsApp webhook body with a text message."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5215500000000",
                                "phone_number_id": "123456789",
                            },
                            "contacts": [{"profile": {"name": "Juan"}, "wa_id": "5215512345678"}],
                            "messages": [
                                {
                                    "from": "5215512345678",
                                    "id": "wamid.abc123",
                                    "timestamp": "1700000000",
                                    "text": {"body": "Hola, quiero información"},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sample_whatsapp_image_body():
    """Webhook body with an image message (no caption)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Ana"}, "wa_id": "5215500001111"}],
                            "messages": [
                                {
                                    "from": "5215500001111",
                                    "id": "wamid.img001",
                                    "timestamp": "1700000001",
                                    "type": "image",
                                    "image": {
                                        "mime_type": "image/jpeg",
                                        "sha256": "abc",
                                        "id": "img1",
                                    },
                                }
                            ],
                        }
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sample_status_update_body():
    """Webhook body with a status update (not a message)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": "wamid.status001",
                                    "status": "delivered",
                                    "timestamp": "1700000002",
                                    "recipient_id": "5215512345678",
                                }
                            ],
                        }
                    }
                ],
            }
        ],
    }
