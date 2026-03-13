"""Admin API endpoints for Agent Tools Registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import AgentTool

tools_router = APIRouter(prefix="/tools", tags=["tools"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ToolCreate(BaseModel):
    tool_key: str
    display_name: str
    description: str
    category: str
    is_global: bool = True
    config: dict = {}


class ToolUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    is_global: bool | None = None
    config: dict | None = None


class ToolResponse(BaseModel):
    id: str
    tool_key: str
    display_name: str
    description: str
    category: str
    is_global: bool
    config: dict

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@tools_router.get("", response_model=list[ToolResponse])
async def list_tools(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("tools", "read")),
):
    result = await session.execute(select(AgentTool))
    return [_to_response(t) for t in result.scalars().all()]


@tools_router.post("", response_model=ToolResponse, status_code=201)
async def create_tool(
    payload: ToolCreate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("tools", "create")),
):
    existing = await session.execute(
        select(AgentTool).where(AgentTool.tool_key == payload.tool_key)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail=f"Tool '{payload.tool_key}' already exists"
        )

    tool = AgentTool(**payload.model_dump())
    session.add(tool)
    await session.flush()
    await log_activity(
        session,
        action="create",
        entity_type="agent_tool",
        entity_id=str(tool.id),
        details={"tool_key": tool.tool_key},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(tool)
    return _to_response(tool)


@tools_router.put("/{tool_key}", response_model=ToolResponse)
async def update_tool(
    tool_key: str,
    payload: ToolUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("tools", "update")),
):
    result = await session.execute(
        select(AgentTool).where(AgentTool.tool_key == tool_key)
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(
            status_code=404, detail=f"Tool '{tool_key}' not found"
        )

    changes = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if getattr(tool, field) != value:
            changes[field] = value
            setattr(tool, field, value)

    if changes:
        await log_activity(
            session,
            action="update",
            entity_type="agent_tool",
            entity_id=str(tool.id),
            details=changes,
            user=_user.name,
        )
    await session.commit()
    await session.refresh(tool)
    return _to_response(tool)


@tools_router.delete("/{tool_key}", status_code=204)
async def delete_tool(
    tool_key: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("tools", "delete")),
):
    result = await session.execute(
        select(AgentTool).where(AgentTool.tool_key == tool_key)
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(
            status_code=404, detail=f"Tool '{tool_key}' not found"
        )

    await log_activity(
        session,
        action="delete",
        entity_type="agent_tool",
        entity_id=str(tool.id),
        details={"tool_key": tool_key},
        user=_user.name,
    )
    await session.delete(tool)
    await session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(tool: AgentTool) -> ToolResponse:
    return ToolResponse(
        id=str(tool.id),
        tool_key=tool.tool_key,
        display_name=tool.display_name,
        description=tool.description,
        category=tool.category,
        is_global=tool.is_global,
        config=tool.config,
    )
