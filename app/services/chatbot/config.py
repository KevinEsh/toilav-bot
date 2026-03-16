import logging
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    WHATSAPP_ACCESS_TOKEN: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    )
    YOUR_PHONE_NUMBER: str = field(default_factory=lambda: os.getenv("YOUR_PHONE_NUMBER", ""))
    APP_ID: str = field(default_factory=lambda: os.getenv("APP_ID", ""))
    APP_SECRET: str = field(default_factory=lambda: os.getenv("APP_SECRET", ""))
    RECIPIENT_WAID: str = field(default_factory=lambda: os.getenv("RECIPIENT_WAID", ""))
    WHATSAPP_API_VERSION: str = field(default_factory=lambda: os.getenv("WHATSAPP_API_VERSION", ""))
    PHONE_NUMBER_ID: str = field(default_factory=lambda: os.getenv("PHONE_NUMBER_ID", ""))
    NGROK_VERIFY_TOKEN: str = field(default_factory=lambda: os.getenv("NGROK_VERIFY_TOKEN", ""))


settings = Settings()


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
