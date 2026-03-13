"""Agno PostgresDb setup for agent session persistence.

Provides a shared PostgresDb instance backed by the same RDS used by
the rest of the application.  Agno uses psycopg (sync driver), so this
module converts the ``postgresql+asyncpg://`` URL used elsewhere into
``postgresql+psycopg://``.
"""
import logging
import re

logger = logging.getLogger(__name__)

_instance = None


def _convert_url(db_url: str) -> str:
    """Convert async SQLAlchemy URL to psycopg format for Agno.

    ``postgresql+asyncpg://`` → ``postgresql+psycopg://``
    ``postgresql://`` (plain) is kept as-is.
    """
    return re.sub(
        r"^postgresql\+asyncpg://",
        "postgresql+psycopg://",
        db_url,
    )


def get_agent_db(db_url: str):
    """Return a shared ``PostgresDb`` instance (lazy singleton).

    The import of ``agno.storage.postgres`` is deferred so the module can
    be imported even when ``psycopg`` is not installed (e.g. in tests).
    """
    global _instance
    if _instance is not None:
        return _instance

    from agno.storage.postgres import PostgresDb

    psycopg_url = _convert_url(db_url)
    _instance = PostgresDb(
        table_name="agno_agent_sessions",
        db_url=psycopg_url,
    )
    logger.info("Agno PostgresDb initialized (table=agno_agent_sessions)")
    return _instance


def reset_agent_db() -> None:
    """Reset the singleton — useful for tests."""
    global _instance
    _instance = None
