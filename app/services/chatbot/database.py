"""
Database engine and session for the chatbot service.

Connects to the same PostgreSQL instance as the rest of the platform.
The schema (SQLModel table definitions) lives in app/services/database/chatbot_schema.py
and is mounted into this container at /schema so we can import it without duplication.
"""

import sys
from pathlib import Path

from config import settings
from sqlmodel import Session, SQLModel, create_engine

# Make the shared schema importable.  In Docker the volume is mounted at /schema;
# locally the relative path is used as a fallback.
_schema_candidates = [
    Path("/schema"),
    Path(__file__).parent.parent / "database",
]
for _p in _schema_candidates:
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
        break

# Import all table definitions so SQLModel.metadata is aware of them.
from chatbot_schema import CHATBOT_MODELS  # noqa: F401, E402

DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

engine = create_engine(DATABASE_URL, echo=False)


def get_session():
    with Session(engine) as session:
        yield session
