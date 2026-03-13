"""Admin API endpoints for Activity Log (read-only, paginated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import ActivityLog

activity_router = APIRouter(prefix="/activity-log", tags=["activity"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ActivityLogResponse(BaseModel):
    id: str
    action: str
    entity_type: str | None
    entity_id: str | None
    details: dict | None
    user: str
    created_at: str  # ISO format

    model_config = {"from_attributes": True}


class PaginatedActivityLog(BaseModel):
    items: list[ActivityLogResponse]
    total: int
    page: int
    per_page: int


# Allowed sort columns for activity log listing (validated explicitly for safety)
_ACTIVITY_SORT_COLUMNS: dict[str, object] = {
    "created_at": ActivityLog.created_at,
    "action": ActivityLog.action,
    "entity_type": ActivityLog.entity_type,
    "user": ActivityLog.user,
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@activity_router.get("", response_model=PaginatedActivityLog)
async def list_activity_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("activity", "read")),
):
    # Validate sort_by against allowed set
    if sort_by not in _ACTIVITY_SORT_COLUMNS:
        sort_by = "created_at"
    sort_col = _ACTIVITY_SORT_COLUMNS[sort_by]

    # Build base query with optional filters
    base = select(ActivityLog)
    count_base = select(func.count()).select_from(ActivityLog)

    if entity_type is not None:
        base = base.where(ActivityLog.entity_type == entity_type)
        count_base = count_base.where(ActivityLog.entity_type == entity_type)
    if action is not None:
        base = base.where(ActivityLog.action == action)
        count_base = count_base.where(ActivityLog.action == action)
    if search:
        search_filter = or_(
            ActivityLog.action.ilike(f"%{search}%"),
            ActivityLog.user.ilike(f"%{search}%"),
        )
        base = base.where(search_filter)
        count_base = count_base.where(search_filter)

    # Total count
    total = (await session.execute(count_base)).scalar() or 0

    # Sorting
    order = sort_col.asc() if sort_order != "desc" else sort_col.desc()

    # Paginated results
    offset = (page - 1) * per_page
    stmt = base.order_by(order).offset(offset).limit(per_page)
    result = await session.execute(stmt)
    logs = result.scalars().all()

    return PaginatedActivityLog(
        items=[_to_response(log) for log in logs],
        total=total,
        page=page,
        per_page=per_page,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(log: ActivityLog) -> ActivityLogResponse:
    return ActivityLogResponse(
        id=str(log.id),
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        details=log.details,
        user=log.user,
        created_at=log.created_at.isoformat() if log.created_at else "",
    )
