from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import BriefingLog


async def save_briefing_log(session: AsyncSession, log: BriefingLog) -> BriefingLog:
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log
