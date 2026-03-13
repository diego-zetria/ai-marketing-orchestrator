"""Admin API endpoints for Workflow Definitions."""

from __future__ import annotations

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
from src.db.workflow_models import WorkflowDefinition

workflows_router = APIRouter(prefix="/workflows", tags=["workflows"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class WorkflowCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None
    statuses: list[str]
    transitions: dict = {}
    transition_actions: dict = {}
    is_default: bool = False


class WorkflowUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    statuses: list[str] | None = None
    transitions: dict | None = None
    transition_actions: dict | None = None
    is_default: bool | None = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str | None
    statuses: list
    transitions: dict
    transition_actions: dict
    is_default: bool
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_transitions(statuses: list[str], transitions: dict) -> None:
    """Raise 422 if any transition key or target is not in statuses."""
    status_set = set(statuses)
    for from_status, targets in transitions.items():
        if from_status not in status_set:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Transition source '{from_status}' is not in statuses list",
            )
        target_list = targets if isinstance(targets, list) else [targets]
        for to_status in target_list:
            if to_status not in status_set:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Transition target '{to_status}' is not in statuses list",
                )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@workflows_router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    is_active: bool | None = None,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("workflows", "read")),
):
    stmt = select(WorkflowDefinition)
    if is_active is not None:
        stmt = stmt.where(WorkflowDefinition.is_active == is_active)
    result = await session.execute(stmt)
    workflows = result.scalars().all()
    return [_workflow_to_response(w) for w in workflows]


@workflows_router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("workflows", "read")),
):
    result = await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == _uuid.UUID(workflow_id))
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found",
        )
    return _workflow_to_response(workflow)


@workflows_router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    payload: WorkflowCreate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("workflows", "create")),
):
    _validate_transitions(payload.statuses, payload.transitions)

    workflow = WorkflowDefinition(
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        statuses=payload.statuses,
        transitions=payload.transitions,
        transition_actions=payload.transition_actions,
        is_default=payload.is_default,
    )
    session.add(workflow)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow with name '{payload.name}' already exists",
        )

    await log_activity(
        session,
        action="create",
        entity_type="workflow_definition",
        entity_id=str(workflow.id),
        details={"name": payload.name},
        user=_user.name,
    )
    await invalidate_rules_cache(session)
    await session.commit()
    await session.refresh(workflow)
    return _workflow_to_response(workflow)


@workflows_router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("workflows", "update")),
):
    result = await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == _uuid.UUID(workflow_id))
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Validate transitions if either statuses or transitions are changing
    new_statuses = update_data.get("statuses", workflow.statuses)
    new_transitions = update_data.get("transitions", workflow.transitions)
    if "statuses" in update_data or "transitions" in update_data:
        _validate_transitions(new_statuses, new_transitions)

    changes: dict = {}
    for field, value in update_data.items():
        if getattr(workflow, field) != value:
            changes[field] = value
            setattr(workflow, field, value)

    if changes:
        await log_activity(
            session,
            action="update",
            entity_type="workflow_definition",
            entity_id=str(workflow.id),
            details=changes,
            user=_user.name,
        )
        await invalidate_rules_cache(session)
        await session.commit()
        await session.refresh(workflow)

    return _workflow_to_response(workflow)


@workflows_router.delete("/{workflow_id}", response_model=WorkflowResponse)
async def delete_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("workflows", "delete")),
):
    result = await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == _uuid.UUID(workflow_id))
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found",
        )

    workflow.is_active = False

    await log_activity(
        session,
        action="delete",
        entity_type="workflow_definition",
        entity_id=str(workflow.id),
        details={"name": workflow.name},
        user=_user.name,
    )
    await invalidate_rules_cache(session)
    await session.commit()
    await session.refresh(workflow)
    return _workflow_to_response(workflow)


@workflows_router.put("/{workflow_id}/set-default", response_model=WorkflowResponse)
async def set_default_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("workflows", "update")),
):
    result = await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == _uuid.UUID(workflow_id))
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found",
        )

    # Unmark all other workflows as default
    all_result = await session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.is_default == True)  # noqa: E712
    )
    for other in all_result.scalars().all():
        other.is_default = False

    workflow.is_default = True

    await log_activity(
        session,
        action="set_default",
        entity_type="workflow_definition",
        entity_id=str(workflow.id),
        details={"name": workflow.name},
        user=_user.name,
    )
    await invalidate_rules_cache(session)
    await session.commit()
    await session.refresh(workflow)
    return _workflow_to_response(workflow)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _workflow_to_response(workflow: WorkflowDefinition) -> WorkflowResponse:
    return WorkflowResponse(
        id=str(workflow.id),
        name=workflow.name,
        display_name=workflow.display_name,
        description=workflow.description,
        statuses=workflow.statuses,
        transitions=workflow.transitions,
        transition_actions=workflow.transition_actions,
        is_default=workflow.is_default,
        is_active=workflow.is_active,
    )
