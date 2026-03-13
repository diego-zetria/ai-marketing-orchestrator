from sqlalchemy.ext.asyncio import AsyncSession

from src.db.admin_models import ActivityLog


async def log_activity(
    session: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict | None = None,
    user: str = "admin",
) -> None:
    log = ActivityLog(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=details,
        user=user,
    )
    session.add(log)
