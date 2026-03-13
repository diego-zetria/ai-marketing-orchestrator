"""Admin API endpoints for Automation Rules."""

from __future__ import annotations

import re
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.cache_invalidation import invalidate_rules_cache
from src.api.admin.deps import get_db
from src.db.workflow_models import AutomationRule

automations_router = APIRouter(prefix="/automations", tags=["automations"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AutomationCreate(BaseModel):
    name: str
    display_name: str
    intent_type: str
    patterns: list[str]
    allowed_roles: list[str]
    valid_from_statuses: list[str]
    target_status: str = ""
    mode: str = "confirm"
    special_action: str | None = None
    priority: int = 100


class AutomationUpdate(BaseModel):
    display_name: str | None = None
    intent_type: str | None = None
    patterns: list[str] | None = None
    allowed_roles: list[str] | None = None
    valid_from_statuses: list[str] | None = None
    target_status: str | None = None
    mode: str | None = None
    special_action: str | None = None
    priority: int | None = None


class AutomationResponse(BaseModel):
    id: str
    name: str
    display_name: str
    intent_type: str
    patterns: list
    allowed_roles: list
    valid_from_statuses: list
    target_status: str
    mode: str
    special_action: str | None
    priority: int
    is_active: bool

    model_config = {"from_attributes": True}


class PatternTestRequest(BaseModel):
    text: str
    user_role: str | None = None
    current_status: str | None = None


class PatternTestResponse(BaseModel):
    matched: bool
    intent_type: str | None = None
    matched_pattern: str | None = None
    target_status: str | None = None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_patterns(patterns: list[str]) -> None:
    """Raise 422 if any pattern is not a valid regex."""
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid regex pattern '{pattern}': {exc}",
            )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@automations_router.get("", response_model=list[AutomationResponse])
async def list_automations(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("automations", "read")),
):
    result = await session.execute(
        select(AutomationRule).order_by(AutomationRule.priority)
    )
    rules = result.scalars().all()
    return [_automation_to_response(r) for r in rules]


@automations_router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(
    automation_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("automations", "read")),
):
    result = await session.execute(
        select(AutomationRule).where(AutomationRule.id == _uuid.UUID(automation_id))
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Automation rule '{automation_id}' not found",
        )
    return _automation_to_response(rule)


@automations_router.post(
    "",
    response_model=AutomationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_automation(
    payload: AutomationCreate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("automations", "create")),
):
    _validate_patterns(payload.patterns)

    rule = AutomationRule(
        name=payload.name,
        display_name=payload.display_name,
        intent_type=payload.intent_type,
        patterns=payload.patterns,
        allowed_roles=payload.allowed_roles,
        valid_from_statuses=payload.valid_from_statuses,
        target_status=payload.target_status,
        mode=payload.mode,
        special_action=payload.special_action,
        priority=payload.priority,
    )
    session.add(rule)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Automation rule with name '{payload.name}' already exists",
        )

    await log_activity(
        session,
        action="create",
        entity_type="automation_rule",
        entity_id=str(rule.id),
        details={"name": payload.name, "intent_type": payload.intent_type},
        user=_user.name,
    )
    await invalidate_rules_cache(session)
    await session.commit()
    await session.refresh(rule)
    return _automation_to_response(rule)


@automations_router.put("/{automation_id}", response_model=AutomationResponse)
async def update_automation(
    automation_id: str,
    payload: AutomationUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("automations", "update")),
):
    result = await session.execute(
        select(AutomationRule).where(AutomationRule.id == _uuid.UUID(automation_id))
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Automation rule '{automation_id}' not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "patterns" in update_data:
        _validate_patterns(update_data["patterns"])

    changes: dict = {}
    for field, value in update_data.items():
        if getattr(rule, field) != value:
            changes[field] = value
            setattr(rule, field, value)

    if changes:
        await log_activity(
            session,
            action="update",
            entity_type="automation_rule",
            entity_id=str(rule.id),
            details=changes,
            user=_user.name,
        )
        await invalidate_rules_cache(session)
        await session.commit()
        await session.refresh(rule)

    return _automation_to_response(rule)


@automations_router.delete("/{automation_id}", response_model=AutomationResponse)
async def delete_automation(
    automation_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("automations", "delete")),
):
    result = await session.execute(
        select(AutomationRule).where(AutomationRule.id == _uuid.UUID(automation_id))
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Automation rule '{automation_id}' not found",
        )

    rule.is_active = False

    await log_activity(
        session,
        action="delete",
        entity_type="automation_rule",
        entity_id=str(rule.id),
        details={"name": rule.name},
        user=_user.name,
    )
    await invalidate_rules_cache(session)
    await session.commit()
    await session.refresh(rule)
    return _automation_to_response(rule)


@automations_router.post(
    "/{automation_id}/test",
    response_model=PatternTestResponse,
)
async def test_automation_patterns(
    automation_id: str,
    payload: PatternTestRequest,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("automations", "read")),
):
    result = await session.execute(
        select(AutomationRule).where(AutomationRule.id == _uuid.UUID(automation_id))
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Automation rule '{automation_id}' not found",
        )

    # Check role if provided
    if payload.user_role and payload.user_role not in rule.allowed_roles:
        return PatternTestResponse(matched=False)

    # Check status if provided
    if payload.current_status and payload.current_status not in rule.valid_from_statuses:
        return PatternTestResponse(matched=False)

    # Test patterns
    for pattern in rule.patterns:
        compiled = re.compile(pattern, re.IGNORECASE)
        if compiled.search(payload.text):
            return PatternTestResponse(
                matched=True,
                intent_type=rule.intent_type,
                matched_pattern=pattern,
                target_status=rule.target_status,
            )

    return PatternTestResponse(matched=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _automation_to_response(rule: AutomationRule) -> AutomationResponse:
    return AutomationResponse(
        id=str(rule.id),
        name=rule.name,
        display_name=rule.display_name,
        intent_type=rule.intent_type,
        patterns=rule.patterns,
        allowed_roles=rule.allowed_roles,
        valid_from_statuses=rule.valid_from_statuses,
        target_status=rule.target_status,
        mode=rule.mode,
        special_action=rule.special_action,
        priority=rule.priority,
        is_active=rule.is_active,
    )
