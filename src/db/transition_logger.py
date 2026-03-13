"""Logs task status transitions to marketing_bot.task_status_transitions.

Used by WebhookHandler to collect data for A10 (time reports).
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


async def log_transition(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    task_id: str,
    task_name: str = "",
    list_id: str = "",
    client_name: str = "",
    from_status: str,
    to_status: str,
    changed_by_id: str = "",
    changed_by_name: str = "",
) -> None:
    """Insert a row into task_status_transitions (fire-and-forget safe)."""
    try:
        async with session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO marketing_bot.task_status_transitions "
                    "(task_id, task_name, list_id, client_name, "
                    "from_status, to_status, changed_by_id, changed_by_name) "
                    "VALUES (:task_id, :task_name, :list_id, :client_name, "
                    ":from_status, :to_status, :changed_by_id, :changed_by_name)"
                ),
                {
                    "task_id": task_id,
                    "task_name": task_name,
                    "list_id": list_id,
                    "client_name": client_name,
                    "from_status": from_status,
                    "to_status": to_status,
                    "changed_by_id": changed_by_id,
                    "changed_by_name": changed_by_name,
                },
            )
            await session.commit()
        logger.debug(
            "Logged transition: task %s %s -> %s",
            task_id, from_status, to_status,
        )
    except Exception:
        logger.exception(
            "Failed to log transition for task %s (%s -> %s)",
            task_id, from_status, to_status,
        )
