"""Admin API endpoints for Assignment Rules and Notification Rules."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import AssignmentRule, NotificationRule

rules_router = APIRouter(prefix="/rules", tags=["rules"])


# ---------------------------------------------------------------------------
# Pydantic schemas – Assignment Rules
# ---------------------------------------------------------------------------


class AssignmentRuleUpdate(BaseModel):
    default_assignee_ids: list[str] | None = None
    tags: list[str] | None = None


class AssignmentRuleResponse(BaseModel):
    id: str
    service_type: str
    default_assignee_ids: list
    tags: list

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pydantic schemas – Notification Rules
# ---------------------------------------------------------------------------


class NotificationRuleCreate(BaseModel):
    status: str
    notify_roles: list[str]
    message_template: str
    is_active: bool = True


class NotificationRuleUpdate(BaseModel):
    notify_roles: list[str] | None = None
    message_template: str | None = None
    is_active: bool | None = None


class NotificationRuleResponse(BaseModel):
    id: str
    status: str
    notify_roles: list
    message_template: str
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Assignment Rule endpoints
# ---------------------------------------------------------------------------


@rules_router.get("/assignment", response_model=list[AssignmentRuleResponse])
async def list_assignment_rules(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("rules", "read")),
):
    result = await session.execute(select(AssignmentRule))
    rules = result.scalars().all()
    return [_assignment_to_response(r) for r in rules]


@rules_router.put("/assignment/{service_type}", response_model=AssignmentRuleResponse)
async def upsert_assignment_rule(
    service_type: str,
    payload: AssignmentRuleUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("rules", "update")),
):
    # Try to find existing rule
    result = await session.execute(
        select(AssignmentRule).where(AssignmentRule.service_type == service_type)
    )
    rule = result.scalar_one_or_none()

    if rule is None:
        # Create new rule (upsert)
        rule = AssignmentRule(
            service_type=service_type,
            default_assignee_ids=payload.default_assignee_ids or [],
            tags=payload.tags or [],
        )
        session.add(rule)
        await session.flush()

        await log_activity(
            session,
            action="create",
            entity_type="assignment_rule",
            entity_id=str(rule.id),
            details={"service_type": service_type},
            user=_user.name,
        )
    else:
        # Update existing rule
        changes: dict = {}
        for field, value in payload.model_dump(exclude_unset=True).items():
            if getattr(rule, field) != value:
                changes[field] = value
                setattr(rule, field, value)

        if changes:
            await log_activity(
                session,
                action="update",
                entity_type="assignment_rule",
                entity_id=str(rule.id),
                details=changes,
                user=_user.name,
            )

    await session.commit()
    await session.refresh(rule)
    return _assignment_to_response(rule)


# ---------------------------------------------------------------------------
# Notification Rule endpoints
# ---------------------------------------------------------------------------


@rules_router.get("/notification", response_model=list[NotificationRuleResponse])
async def list_notification_rules(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("rules", "read")),
):
    result = await session.execute(select(NotificationRule))
    rules = result.scalars().all()
    return [_notification_to_response(r) for r in rules]


@rules_router.post(
    "/notification",
    response_model=NotificationRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_rule(
    payload: NotificationRuleCreate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("rules", "create")),
):
    rule = NotificationRule(
        status=payload.status,
        notify_roles=payload.notify_roles,
        message_template=payload.message_template,
        is_active=payload.is_active,
    )
    session.add(rule)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Notification rule for status '{payload.status}' already exists",
        )

    await log_activity(
        session,
        action="create",
        entity_type="notification_rule",
        entity_id=str(rule.id),
        details={"status": payload.status},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(rule)
    return _notification_to_response(rule)


@rules_router.put("/notification/{rule_status}", response_model=NotificationRuleResponse)
async def update_notification_rule(
    rule_status: str,
    payload: NotificationRuleUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("rules", "update")),
):
    result = await session.execute(
        select(NotificationRule).where(NotificationRule.status == rule_status)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification rule for status '{rule_status}' not found",
        )

    changes: dict = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if getattr(rule, field) != value:
            changes[field] = value
            setattr(rule, field, value)

    if changes:
        await log_activity(
            session,
            action="update",
            entity_type="notification_rule",
            entity_id=str(rule.id),
            details=changes,
            user=_user.name,
        )
        await session.commit()
        await session.refresh(rule)

    return _notification_to_response(rule)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assignment_to_response(rule: AssignmentRule) -> AssignmentRuleResponse:
    return AssignmentRuleResponse(
        id=str(rule.id),
        service_type=rule.service_type,
        default_assignee_ids=rule.default_assignee_ids,
        tags=rule.tags,
    )


def _notification_to_response(rule: NotificationRule) -> NotificationRuleResponse:
    return NotificationRuleResponse(
        id=str(rule.id),
        status=rule.status,
        notify_roles=rule.notify_roles,
        message_template=rule.message_template,
        is_active=rule.is_active,
    )
