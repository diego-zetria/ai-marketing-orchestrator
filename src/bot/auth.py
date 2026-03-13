import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import TeamMember

logger = logging.getLogger(__name__)


async def is_user_authorized(
    user_id: int,
    allowed_ids: list[int],
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> bool:
    """Check if a Telegram user is authorized.

    1. Query TeamMember table for active member with matching telegram_chat_id
    2. Fallback to static allowed_ids list (env var, for admin/bootstrap)
    """
    if session_factory:
        try:
            async with session_factory() as session:
                result = await session.execute(
                    select(TeamMember.id).where(
                        TeamMember.telegram_chat_id == user_id,
                        TeamMember.active.is_(True),
                    )
                )
                if result.scalar_one_or_none() is not None:
                    return True
        except Exception:
            logger.exception("Error checking team member authorization for user %s", user_id)

    return user_id in allowed_ids
