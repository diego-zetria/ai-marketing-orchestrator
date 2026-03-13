"""Shared database dependency for admin API modules."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine
    if _engine is None:
        from src.config.settings import Settings

        settings = Settings()
        _engine = create_async_engine(settings.database_url, echo=False)
    return _engine


async def get_db():
    global _session_factory
    if _session_factory is None:
        engine = _get_engine()
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with _session_factory() as session:
        yield session
