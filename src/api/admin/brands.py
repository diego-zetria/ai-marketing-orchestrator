"""Admin API endpoints for Brand Guidelines."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import BrandGuideline, Client

brands_router = APIRouter(prefix="/brands", tags=["brands"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class BrandGuidelineResponse(BaseModel):
    id: str
    client_id: str | None
    content: str

    model_config = {"from_attributes": True}


class BrandGuidelineUpdate(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@brands_router.get("", response_model=list[BrandGuidelineResponse])
async def list_brand_guidelines(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("brands", "read")),
):
    result = await session.execute(select(BrandGuideline))
    guidelines = result.scalars().all()
    return [_to_response(g) for g in guidelines]


@brands_router.get("/default", response_model=BrandGuidelineResponse)
async def get_default_guideline(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("brands", "read")),
):
    result = await session.execute(
        select(BrandGuideline).where(BrandGuideline.client_id.is_(None))
    )
    guideline = result.scalar_one_or_none()
    if guideline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default brand guideline not found",
        )
    return _to_response(guideline)


@brands_router.get("/{client_id}", response_model=BrandGuidelineResponse)
async def get_client_guideline(
    client_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("brands", "read")),
):
    try:
        uid = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand guideline not found",
        )

    result = await session.execute(
        select(BrandGuideline).where(BrandGuideline.client_id == uid)
    )
    guideline = result.scalar_one_or_none()
    if guideline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand guideline not found",
        )
    return _to_response(guideline)


@brands_router.put("/default", response_model=BrandGuidelineResponse)
async def upsert_default_guideline(
    payload: BrandGuidelineUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("brands", "update")),
):
    result = await session.execute(
        select(BrandGuideline).where(BrandGuideline.client_id.is_(None))
    )
    guideline = result.scalar_one_or_none()

    if guideline is None:
        guideline = BrandGuideline(client_id=None, content=payload.content)
        session.add(guideline)
        await session.flush()

        await log_activity(
            session,
            action="create",
            entity_type="brand_guideline",
            entity_id=str(guideline.id),
            details={"type": "default"},
            user=_user.name,
        )
    else:
        if guideline.content != payload.content:
            guideline.content = payload.content
            await log_activity(
                session,
                action="update",
                entity_type="brand_guideline",
                entity_id=str(guideline.id),
                details={"type": "default"},
                user=_user.name,
            )

    await session.commit()
    await session.refresh(guideline)
    return _to_response(guideline)


@brands_router.put("/{client_id}", response_model=BrandGuidelineResponse)
async def upsert_client_guideline(
    client_id: str,
    payload: BrandGuidelineUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("brands", "update")),
):
    # Validate client exists
    try:
        uid = uuid.UUID(client_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID for client_id: '{client_id}'",
        )

    client_result = await session.execute(select(Client).where(Client.id == uid))
    if client_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{client_id}' not found",
        )

    result = await session.execute(
        select(BrandGuideline).where(BrandGuideline.client_id == uid)
    )
    guideline = result.scalar_one_or_none()

    if guideline is None:
        guideline = BrandGuideline(client_id=uid, content=payload.content)
        session.add(guideline)
        await session.flush()

        await log_activity(
            session,
            action="create",
            entity_type="brand_guideline",
            entity_id=str(guideline.id),
            details={"client_id": client_id},
            user=_user.name,
        )
    else:
        if guideline.content != payload.content:
            guideline.content = payload.content
            await log_activity(
                session,
                action="update",
                entity_type="brand_guideline",
                entity_id=str(guideline.id),
                details={"client_id": client_id},
                user=_user.name,
            )

    await session.commit()
    await session.refresh(guideline)
    return _to_response(guideline)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(guideline: BrandGuideline) -> BrandGuidelineResponse:
    return BrandGuidelineResponse(
        id=str(guideline.id),
        client_id=str(guideline.client_id) if guideline.client_id else None,
        content=guideline.content,
    )
