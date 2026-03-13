"""Admin API endpoints for Agent Configurations."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import AgentConfig

agents_router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AgentConfigUpdate(BaseModel):
    model_id: str | None = None
    instructions: list[str] | None = None
    is_active: bool | None = None
    enabled_tools: list[str] | None = None


class AgentConfigResponse(BaseModel):
    id: str
    agent_name: str
    model_id: str
    instructions: list
    is_active: bool
    enabled_tools: list

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@agents_router.get("", response_model=list[AgentConfigResponse])
async def list_agent_configs(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("agents", "read")),
):
    result = await session.execute(select(AgentConfig))
    configs = result.scalars().all()
    return [_to_response(c) for c in configs]


@agents_router.put("/{agent_name}", response_model=AgentConfigResponse)
async def upsert_agent_config(
    agent_name: str,
    payload: AgentConfigUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("agents", "update")),
):
    # Try to find existing config
    result = await session.execute(
        select(AgentConfig).where(AgentConfig.agent_name == agent_name)
    )
    config = result.scalar_one_or_none()

    if config is None:
        # Create new config (upsert) with sensible defaults
        config = AgentConfig(
            agent_name=agent_name,
            model_id=payload.model_id or "openrouter/auto",
            instructions=payload.instructions or [],
            is_active=payload.is_active if payload.is_active is not None else True,
            enabled_tools=payload.enabled_tools or [],
        )
        session.add(config)
        await session.flush()

        await log_activity(
            session,
            action="create",
            entity_type="agent_config",
            entity_id=str(config.id),
            details={"agent_name": agent_name},
            user=_user.name,
        )
    else:
        # Update existing config
        changes: dict = {}
        for field, value in payload.model_dump(exclude_unset=True).items():
            if getattr(config, field) != value:
                changes[field] = value
                setattr(config, field, value)

        if changes:
            await log_activity(
                session,
                action="update",
                entity_type="agent_config",
                entity_id=str(config.id),
                details=changes,
                user=_user.name,
            )

    await session.commit()
    await session.refresh(config)
    return _to_response(config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(config: AgentConfig) -> AgentConfigResponse:
    return AgentConfigResponse(
        id=str(config.id),
        agent_name=config.agent_name,
        model_id=config.model_id,
        instructions=config.instructions,
        is_active=config.is_active,
        enabled_tools=config.enabled_tools,
    )
