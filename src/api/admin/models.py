"""Admin API endpoints for AI Models Catalog."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import HomologatedModel
from src.integrations.openrouter.sync import sync_models as do_sync

models_router = APIRouter(prefix="/models", tags=["models"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ModelCreate(BaseModel):
    model_id: str
    provider: str
    display_name: str
    description_pt: str
    tier: Literal["premium", "recommended", "fast", "specialist", "router"]
    quality_stars: int = Field(ge=1, le=5, default=3)
    speed_rating: Literal["fast", "moderate", "slow"]
    cost_rating: Literal["budget", "moderate", "premium", "ultra"]
    best_for: list[str] = []
    recommended_agents: list[str] = []
    is_recommended: bool = False
    display_order: int = 100


class ModelUpdate(BaseModel):
    display_name: str | None = None
    description_pt: str | None = None
    tier: Literal["premium", "recommended", "fast", "specialist", "router"] | None = None
    quality_stars: int | None = Field(default=None, ge=1, le=5)
    speed_rating: Literal["fast", "moderate", "slow"] | None = None
    cost_rating: Literal["budget", "moderate", "premium", "ultra"] | None = None
    best_for: list[str] | None = None
    recommended_agents: list[str] | None = None
    is_recommended: bool | None = None
    display_order: int | None = None
    is_active: bool | None = None


class ModelResponse(BaseModel):
    id: str
    model_id: str
    provider: str
    display_name: str
    description_pt: str
    tier: str
    quality_stars: int
    speed_rating: str
    cost_rating: str
    best_for: list[str]
    context_length: int
    prompt_price_per_m: float | None
    completion_price_per_m: float | None
    supports_images: bool
    supports_tools: bool
    supports_audio: bool
    supports_video: bool
    input_modalities: list[str]
    recommended_agents: list[str]
    is_recommended: bool
    display_order: int
    is_active: bool
    last_synced_at: str | None
    updated_at: str

    model_config = {"from_attributes": True}


class SyncResponse(BaseModel):
    synced: int
    not_found: list[str]
    errors: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@models_router.get("", response_model=list[ModelResponse])
async def list_models(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("models", "read")),
):
    result = await session.execute(
        select(HomologatedModel)
        .where(HomologatedModel.is_active == True)  # noqa: E712
        .order_by(HomologatedModel.display_order, HomologatedModel.display_name)
    )
    return [_to_response(m) for m in result.scalars().all()]


@models_router.get("/recommendations/{agent_name}", response_model=list[ModelResponse])
async def get_recommendations(
    agent_name: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("models", "read")),
):
    """Get models recommended for a specific agent."""
    result = await session.execute(
        select(HomologatedModel).where(HomologatedModel.is_active == True)  # noqa: E712
    )
    models = [
        m for m in result.scalars().all()
        if agent_name in (m.recommended_agents or [])
    ]
    return [_to_response(m) for m in models]


@models_router.get("/{model_uuid}", response_model=ModelResponse)
async def get_model(
    model_uuid: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("models", "read")),
):
    result = await session.execute(
        select(HomologatedModel).where(HomologatedModel.id == model_uuid)
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return _to_response(model)


@models_router.post("", response_model=ModelResponse, status_code=201)
async def create_model(
    payload: ModelCreate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("models", "create")),
):
    existing = await session.execute(
        select(HomologatedModel).where(HomologatedModel.model_id == payload.model_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Model '{payload.model_id}' already exists",
        )

    model = HomologatedModel(**payload.model_dump())
    session.add(model)
    await session.flush()
    await log_activity(
        session,
        action="create",
        entity_type="homologated_model",
        entity_id=str(model.id),
        details={"model_id": model.model_id},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(model)
    return _to_response(model)


@models_router.put("/{model_uuid}", response_model=ModelResponse)
async def update_model(
    model_uuid: str,
    payload: ModelUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("models", "update")),
):
    result = await session.execute(
        select(HomologatedModel).where(HomologatedModel.id == model_uuid)
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    changes = {}
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        if getattr(model, field_name) != value:
            changes[field_name] = value
            setattr(model, field_name, value)

    if changes:
        await log_activity(
            session,
            action="update",
            entity_type="homologated_model",
            entity_id=str(model.id),
            details=changes,
            user=_user.name,
        )
    await session.commit()
    await session.refresh(model)
    return _to_response(model)


@models_router.delete("/{model_uuid}", status_code=204)
async def delete_model(
    model_uuid: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("models", "delete")),
):
    result = await session.execute(
        select(HomologatedModel).where(HomologatedModel.id == model_uuid)
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    await log_activity(
        session,
        action="delete",
        entity_type="homologated_model",
        entity_id=str(model.id),
        details={"model_id": model.model_id},
        user=_user.name,
    )
    await session.delete(model)
    await session.commit()


@models_router.post("/sync", response_model=SyncResponse)
async def sync_openrouter(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("models", "update")),
):
    """Sync pricing and specs from OpenRouter API for all active models."""
    try:
        result = await do_sync(session)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to sync with OpenRouter: {exc}",
        ) from exc
    await log_activity(
        session,
        action="sync",
        entity_type="homologated_model",
        entity_id="all",
        details={"synced": result.synced, "not_found": result.not_found},
        user=_user.name,
    )
    return SyncResponse(
        synced=result.synced,
        not_found=result.not_found,
        errors=result.errors,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(model: HomologatedModel) -> ModelResponse:
    return ModelResponse(
        id=str(model.id),
        model_id=model.model_id,
        provider=model.provider,
        display_name=model.display_name,
        description_pt=model.description_pt,
        tier=model.tier,
        quality_stars=model.quality_stars,
        speed_rating=model.speed_rating,
        cost_rating=model.cost_rating,
        best_for=model.best_for or [],
        context_length=model.context_length,
        prompt_price_per_m=(
            float(model.prompt_price_per_m)
            if model.prompt_price_per_m is not None
            else None
        ),
        completion_price_per_m=(
            float(model.completion_price_per_m)
            if model.completion_price_per_m is not None
            else None
        ),
        supports_images=model.supports_images,
        supports_tools=model.supports_tools,
        supports_audio=model.supports_audio,
        supports_video=model.supports_video,
        input_modalities=model.input_modalities or ["text"],
        recommended_agents=model.recommended_agents or [],
        is_recommended=model.is_recommended,
        display_order=model.display_order,
        is_active=model.is_active,
        last_synced_at=model.last_synced_at.isoformat() if model.last_synced_at else None,
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
    )
