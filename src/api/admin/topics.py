"""Admin API endpoints for Telegram Topics."""

from __future__ import annotations

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import get_current_admin
from src.api.admin.cache_invalidation import invalidate_rules_cache
from src.api.admin.deps import get_db
from src.db.workflow_models import TelegramTopic

topics_router = APIRouter(prefix="/topics", tags=["topics"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TopicCreate(BaseModel):
    name: str
    label: str
    topic_id: int
    client_id: str | None = None


class TopicUpdate(BaseModel):
    label: str | None = None
    topic_id: int | None = None
    client_id: str | None = None
    is_active: bool | None = None


class TopicResponse(BaseModel):
    id: str
    name: str
    label: str
    topic_id: int
    client_id: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@topics_router.get("", response_model=list[TopicResponse])
async def list_topics(
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    result = await session.execute(select(TelegramTopic))
    topics = result.scalars().all()
    return [_topic_to_response(t) for t in topics]


@topics_router.post(
    "",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_topic(
    payload: TopicCreate,
    session: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    topic = TelegramTopic(
        name=payload.name,
        label=payload.label,
        topic_id=payload.topic_id,
        client_id=_uuid.UUID(payload.client_id) if payload.client_id else None,
    )
    session.add(topic)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Topic with name '{payload.name}' already exists",
        )

    await log_activity(
        session,
        action="create",
        entity_type="telegram_topic",
        entity_id=str(topic.id),
        details={"name": payload.name, "topic_id": payload.topic_id},
        user=admin,
    )
    await invalidate_rules_cache(session)
    await session.commit()
    await session.refresh(topic)
    return _topic_to_response(topic)


@topics_router.put("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: str,
    payload: TopicUpdate,
    session: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    result = await session.execute(
        select(TelegramTopic).where(TelegramTopic.id == _uuid.UUID(topic_id))
    )
    topic = result.scalar_one_or_none()
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic '{topic_id}' not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "client_id" in update_data and update_data["client_id"] is not None:
        update_data["client_id"] = _uuid.UUID(update_data["client_id"])

    changes: dict = {}
    for field, value in update_data.items():
        if getattr(topic, field) != value:
            changes[field] = value
            setattr(topic, field, value)

    if changes:
        await log_activity(
            session,
            action="update",
            entity_type="telegram_topic",
            entity_id=str(topic.id),
            details=changes,
            user=admin,
        )
        await invalidate_rules_cache(session)
        await session.commit()
        await session.refresh(topic)

    return _topic_to_response(topic)


@topics_router.delete("/{topic_id}", response_model=TopicResponse)
async def delete_topic(
    topic_id: str,
    session: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    result = await session.execute(
        select(TelegramTopic).where(TelegramTopic.id == _uuid.UUID(topic_id))
    )
    topic = result.scalar_one_or_none()
    if topic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic '{topic_id}' not found",
        )

    topic.is_active = False

    await log_activity(
        session,
        action="delete",
        entity_type="telegram_topic",
        entity_id=str(topic.id),
        details={"name": topic.name},
        user=admin,
    )
    await invalidate_rules_cache(session)
    await session.commit()
    await session.refresh(topic)
    return _topic_to_response(topic)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _topic_to_response(topic: TelegramTopic) -> TopicResponse:
    return TopicResponse(
        id=str(topic.id),
        name=topic.name,
        label=topic.label,
        topic_id=topic.topic_id,
        client_id=str(topic.client_id) if topic.client_id else None,
        is_active=topic.is_active,
    )
