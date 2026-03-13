"""Admin API endpoints for System Configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import SystemConfig

system_router = APIRouter(prefix="/system-config", tags=["system"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SystemConfigResponse(BaseModel):
    key: str
    value: dict | list | str | int | float | bool
    description: str | None

    model_config = {"from_attributes": True}


class SystemConfigUpdate(BaseModel):
    value: dict | list | str | int | float | bool
    description: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@system_router.get("", response_model=list[SystemConfigResponse])
async def list_system_configs(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("system", "read")),
):
    result = await session.execute(select(SystemConfig))
    configs = result.scalars().all()
    return [_to_response(c) for c in configs]


@system_router.get("/{key}", response_model=SystemConfigResponse)
async def get_system_config(
    key: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("system", "read")),
):
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"System config '{key}' not found",
        )
    return _to_response(config)


@system_router.put("/{key}", response_model=SystemConfigResponse)
async def upsert_system_config(
    key: str,
    payload: SystemConfigUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("system", "update")),
):
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()

    if config is None:
        # Create new config entry
        config = SystemConfig(
            key=key,
            value=payload.value,
            description=payload.description,
        )
        session.add(config)
        await session.flush()

        await log_activity(
            session,
            action="create",
            entity_type="system_config",
            entity_id=key,
            details={"value": _serialize_value(payload.value)},
            user=_user.name,
        )
    else:
        # Update existing config
        changes: dict = {}
        if config.value != payload.value:
            changes["value"] = _serialize_value(payload.value)
            config.value = payload.value
        if payload.description is not None and config.description != payload.description:
            changes["description"] = payload.description
            config.description = payload.description

        if changes:
            await log_activity(
                session,
                action="update",
                entity_type="system_config",
                entity_id=key,
                details=changes,
                user=_user.name,
            )

    await session.commit()
    await session.refresh(config)
    return _to_response(config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_value(value: dict | list | str | int | float | bool) -> str:
    """Convert value to a string suitable for activity log details."""
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value)
    return str(value)


def _to_response(config: SystemConfig) -> SystemConfigResponse:
    return SystemConfigResponse(
        key=config.key,
        value=config.value,
        description=config.description,
    )
