"""
Async database engine and session factory for the chatbot service.

Uses asyncpg (non-blocking). No ORM models are imported here — all queries
use raw SQL via text(), so there is no dependency on chatbot_schema.py.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import settings


def _build_url() -> str:
    url = (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    # Normalize Railway-style postgres:// and plain postgresql:// to asyncpg driver
    url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    if not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(
    _build_url(),
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
