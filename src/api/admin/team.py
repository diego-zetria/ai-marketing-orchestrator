from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.models import TeamMember

team_router = APIRouter(prefix="/team-members", tags=["team"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TeamMemberCreate(BaseModel):
    clickup_user_id: str
    name: str
    role: str | None = None
    telegram_chat_id: int = 0


class TeamMemberUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    telegram_chat_id: int | None = None
    active: bool | None = None


class TeamMemberResponse(BaseModel):
    id: str
    clickup_user_id: str | None
    name: str
    role: str | None
    telegram_chat_id: int
    active: bool

    model_config = {"from_attributes": True}


class PaginatedTeamMembers(BaseModel):
    items: list[TeamMemberResponse]
    total: int
    page: int
    per_page: int


# Allowed sort columns for team member listing (validated explicitly for safety)
_TEAM_SORT_COLUMNS: dict[str, object] = {
    "name": TeamMember.name,
    "role": TeamMember.role,
    "active": TeamMember.active,
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@team_router.get("", response_model=PaginatedTeamMembers)
async def list_team_members(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc"),
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("team", "read")),
):
    # Validate sort_by against allowed set
    if sort_by not in _TEAM_SORT_COLUMNS:
        sort_by = "name"
    sort_col = _TEAM_SORT_COLUMNS[sort_by]

    # Build base filters
    base = select(TeamMember)
    count_base = select(func.count()).select_from(TeamMember)

    if not include_inactive:
        base = base.where(TeamMember.active.is_(True))
        count_base = count_base.where(TeamMember.active.is_(True))

    if search:
        search_filter = TeamMember.name.ilike(f"%{search}%")
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
    members = result.scalars().all()

    return PaginatedTeamMembers(
        items=[_to_response(m) for m in members],
        total=total,
        page=page,
        per_page=per_page,
    )


@team_router.post("", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def create_team_member(
    payload: TeamMemberCreate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("team", "create")),
):
    member = TeamMember(
        clickup_user_id=payload.clickup_user_id,
        name=payload.name,
        role=payload.role,
        telegram_chat_id=payload.telegram_chat_id,
    )
    session.add(member)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Team member with clickup_user_id '{payload.clickup_user_id}' already exists",
        )

    await log_activity(
        session,
        action="create",
        entity_type="team_member",
        entity_id=str(member.id),
        details={"name": member.name, "clickup_user_id": member.clickup_user_id},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(member)
    return _to_response(member)


@team_router.put("/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: str,
    payload: TeamMemberUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("team", "update")),
):
    member = await _get_member_or_404(session, member_id)

    changes: dict = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if getattr(member, field) != value:
            changes[field] = value
            setattr(member, field, value)

    if changes:
        await log_activity(
            session,
            action="update",
            entity_type="team_member",
            entity_id=str(member.id),
            details=changes,
            user=_user.name,
        )
        await session.commit()
        await session.refresh(member)

    return _to_response(member)


@team_router.delete("/{member_id}", response_model=TeamMemberResponse)
async def delete_team_member(
    member_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("team", "delete")),
):
    member = await _get_member_or_404(session, member_id)
    member.active = False

    await log_activity(
        session,
        action="delete",
        entity_type="team_member",
        entity_id=str(member.id),
        details={"name": member.name},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(member)
    return _to_response(member)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_member_or_404(session: AsyncSession, member_id: str) -> TeamMember:
    try:
        uid = uuid.UUID(member_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")

    result = await session.execute(select(TeamMember).where(TeamMember.id == uid))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")
    return member


def _to_response(member: TeamMember) -> TeamMemberResponse:
    return TeamMemberResponse(
        id=str(member.id),
        clickup_user_id=member.clickup_user_id,
        name=member.name,
        role=member.role,
        telegram_chat_id=member.telegram_chat_id,
        active=member.active,
    )
