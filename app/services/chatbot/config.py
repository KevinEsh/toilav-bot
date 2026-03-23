import logging
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # WhatsApp Cloud API
    WHATSAPP_ACCESS_TOKEN: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    )
    WHATSAPP_API_VERSION: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_API_VERSION", "v18.0")
    )
    PHONE_NUMBER_ID: str = field(default_factory=lambda: os.getenv("PHONE_NUMBER_ID", ""))
    APP_ID: str = field(default_factory=lambda: os.getenv("APP_ID", ""))
    APP_SECRET: str = field(default_factory=lambda: os.getenv("APP_SECRET", ""))
    VERIFY_TOKEN: str = field(default_factory=lambda: os.getenv("NGROK_VERIFY_TOKEN", ""))

    # Owner identification — messages from this wa_id are treated as owner commands
    OWNER_WA_ID: str = field(default_factory=lambda: os.getenv("OWNER_WA_ID", ""))

    # Database
    POSTGRES_USER: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "admin"))
    POSTGRES_PASSWORD: str = field(
        default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "password")
    )
    POSTGRES_HOST: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    POSTGRES_PORT: str = field(default_factory=lambda: os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "chatbot"))


settings = Settings()


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
