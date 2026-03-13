"""Admin API endpoints for Dashboard stats and recent activity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.approval.models import ApprovalAsset
from src.db.admin_models import (
    ActivityLog,
    AgentConfig,
    AssignmentRule,
    Client,
    NotificationRule,
)
from src.db.models import TeamMember

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class DashboardStats(BaseModel):
    total_team_members: int
    total_clients: int
    total_rules: int
    total_agents: int
    recent_activity_count: int
    pending_approvals: int
    approved_this_month: int
    overdue_approvals: int
    avg_revisions: float
    approval_rate: float


class ActivityLogEntry(BaseModel):
    id: str
    action: str
    entity_type: str | None
    entity_id: str | None
    details: dict | None
    user: str
    created_at: str

    model_config = {"from_attributes": True}


class TrendPoint(BaseModel):
    week: str
    pending: int
    approved: int
    changes_requested: int


class ApprovalTrendsResponse(BaseModel):
    trends: list[TrendPoint]


class PipelineEntry(BaseModel):
    status: str
    label: str
    count: int


class ApprovalPipelineResponse(BaseModel):
    pipeline: list[PipelineEntry]


# ---------------------------------------------------------------------------
# Status label mapping
# ---------------------------------------------------------------------------

_STATUS_LABELS: dict[str, str] = {
    "pending_review": "Pendente",
    "approved": "Aprovado",
    "changes_requested": "Alteracao",
    "expired": "Expirado",
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@dashboard_router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("dashboard", "read")),
):
    team_count = (await session.execute(select(func.count()).select_from(TeamMember))).scalar() or 0
    client_count = (await session.execute(select(func.count()).select_from(Client))).scalar() or 0

    assignment_count = (
        await session.execute(select(func.count()).select_from(AssignmentRule))
    ).scalar() or 0
    notification_count = (
        await session.execute(select(func.count()).select_from(NotificationRule))
    ).scalar() or 0
    total_rules = assignment_count + notification_count

    agent_count = (
        await session.execute(select(func.count()).select_from(AgentConfig))
    ).scalar() or 0
    activity_count = (
        await session.execute(select(func.count()).select_from(ActivityLog))
    ).scalar() or 0

    pending_approvals = (
        await session.execute(
            select(func.count())
            .select_from(ApprovalAsset)
            .where(ApprovalAsset.status == "pending_review")
        )
    ).scalar() or 0

    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    approved_this_month = (
        await session.execute(
            select(func.count())
            .select_from(ApprovalAsset)
            .where(
                ApprovalAsset.status == "approved",
                ApprovalAsset.updated_at >= first_of_month,
            )
        )
    ).scalar() or 0

    # Overdue approvals: pending_review older than 3 days
    overdue_cutoff = now - timedelta(days=3)
    overdue_approvals = (
        await session.execute(
            select(func.count())
            .select_from(ApprovalAsset)
            .where(
                ApprovalAsset.status == "pending_review",
                ApprovalAsset.created_at < overdue_cutoff,
            )
        )
    ).scalar() or 0

    # Average revisions (current_version across all assets)
    avg_revisions_raw = (
        await session.execute(
            select(func.avg(ApprovalAsset.current_version)).select_from(ApprovalAsset)
        )
    ).scalar()
    avg_revisions = round(float(avg_revisions_raw), 2) if avg_revisions_raw else 0.0

    # Approval rate: approved / total * 100
    total_assets = (
        await session.execute(select(func.count()).select_from(ApprovalAsset))
    ).scalar() or 0
    approved_total = (
        await session.execute(
            select(func.count())
            .select_from(ApprovalAsset)
            .where(ApprovalAsset.status == "approved")
        )
    ).scalar() or 0
    approval_rate = round((approved_total / total_assets) * 100, 1) if total_assets > 0 else 0.0

    return DashboardStats(
        total_team_members=team_count,
        total_clients=client_count,
        total_rules=total_rules,
        total_agents=agent_count,
        recent_activity_count=activity_count,
        pending_approvals=pending_approvals,
        approved_this_month=approved_this_month,
        overdue_approvals=overdue_approvals,
        avg_revisions=avg_revisions,
        approval_rate=approval_rate,
    )


@dashboard_router.get("/activity", response_model=list[ActivityLogEntry])
async def get_recent_activity(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("dashboard", "read")),
):
    result = await session.execute(
        select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(20)
    )
    logs = result.scalars().all()
    return [_to_entry(log) for log in logs]


@dashboard_router.get("/approval-trends", response_model=ApprovalTrendsResponse)
async def get_approval_trends(
    days: int = Query(default=30, ge=7, le=365),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("dashboard", "read")),
):
    """Return weekly approval counts for the last N days (for area chart)."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # Truncate created_at to week start and group by (week, status)
    week_col = func.date_trunc("week", ApprovalAsset.created_at).label("week")
    stmt = (
        select(
            week_col,
            ApprovalAsset.status,
            func.count().label("cnt"),
        )
        .where(ApprovalAsset.created_at >= cutoff)
        .group_by(week_col, ApprovalAsset.status)
        .order_by(week_col)
    )
    rows = (await session.execute(stmt)).all()

    # Build a dict keyed by week ISO date string
    week_data: dict[str, dict[str, int]] = {}
    for row in rows:
        week_dt = row.week
        if hasattr(week_dt, "strftime"):
            week_key = week_dt.strftime("%Y-%m-%d")
        else:
            week_key = str(week_dt)[:10]
        if week_key not in week_data:
            week_data[week_key] = {"pending": 0, "approved": 0, "changes_requested": 0}
        status = row.status
        if status == "pending_review":
            week_data[week_key]["pending"] += row.cnt
        elif status == "approved":
            week_data[week_key]["approved"] += row.cnt
        elif status == "changes_requested":
            week_data[week_key]["changes_requested"] += row.cnt

    # Fill in missing weeks with zeros
    _fill_missing_weeks(week_data, cutoff, now)

    trends = [
        TrendPoint(
            week=week_key,
            pending=counts["pending"],
            approved=counts["approved"],
            changes_requested=counts["changes_requested"],
        )
        for week_key, counts in sorted(week_data.items())
    ]

    return ApprovalTrendsResponse(trends=trends)


@dashboard_router.get("/approval-pipeline", response_model=ApprovalPipelineResponse)
async def get_approval_pipeline(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("dashboard", "read")),
):
    """Return current counts of approvals by status (for bar chart)."""
    stmt = (
        select(
            ApprovalAsset.status,
            func.count().label("cnt"),
        )
        .group_by(ApprovalAsset.status)
        .order_by(ApprovalAsset.status)
    )
    rows = (await session.execute(stmt)).all()

    # Build pipeline entries, including statuses with zero counts
    status_counts: dict[str, int] = {status: 0 for status in _STATUS_LABELS}
    for row in rows:
        if row.status in status_counts:
            status_counts[row.status] = row.cnt

    pipeline = [
        PipelineEntry(
            status=status,
            label=_STATUS_LABELS[status],
            count=count,
        )
        for status, count in status_counts.items()
    ]

    return ApprovalPipelineResponse(pipeline=pipeline)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_entry(log: ActivityLog) -> ActivityLogEntry:
    return ActivityLogEntry(
        id=str(log.id),
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        details=log.details,
        user=log.user,
        created_at=log.created_at.isoformat() if log.created_at else "",
    )


def _fill_missing_weeks(
    week_data: dict[str, dict[str, int]],
    start: datetime,
    end: datetime,
) -> None:
    """Ensure every week between start and end has an entry (zeros if missing)."""
    # Find the Monday (ISO week start) on or before the start date
    start_monday = start - timedelta(days=start.weekday())
    current = start_monday
    while current <= end:
        week_key = current.strftime("%Y-%m-%d")
        if week_key not in week_data:
            week_data[week_key] = {"pending": 0, "approved": 0, "changes_requested": 0}
        current += timedelta(weeks=1)
