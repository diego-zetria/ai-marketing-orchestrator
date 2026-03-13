"""Cache invalidation helper for workflow/automation/topic mutations."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.admin_models import SystemConfig


async def invalidate_rules_cache(session: AsyncSession) -> None:
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == "rules_cache_version")
    )
    config = result.scalar_one_or_none()
    now = datetime.now(timezone.utc).isoformat()
    if config is None:
        config = SystemConfig(key="rules_cache_version", value={"version": now})
        session.add(config)
    else:
        config.value = {"version": now}
