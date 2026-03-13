"""Admin API endpoints for in-app Notifications."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import Notification

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    link: str | None
    icon: str | None
    is_read: bool
    created_at: str  # ISO format

    model_config = {"from_attributes": True}


class PaginatedNotifications(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int
    per_page: int


class UnreadCountResponse(BaseModel):
    count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@notifications_router.get("", response_model=PaginatedNotifications)
async def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("notifications", "read")),
):
    # Build base query with optional filter
    base = select(Notification)
    count_base = select(func.count()).select_from(Notification)

    if unread_only:
        base = base.where(Notification.is_read.is_(False))
        count_base = count_base.where(Notification.is_read.is_(False))

    # Total count (respecting filters)
    total = (await session.execute(count_base)).scalar() or 0

    # Global unread count (always unfiltered)
    unread_count = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.is_read.is_(False))
        )
    ).scalar() or 0

    # Paginated results, newest first
    offset = (page - 1) * per_page
    stmt = base.order_by(Notification.created_at.desc()).offset(offset).limit(per_page)
    result = await session.execute(stmt)
    notifications = result.scalars().all()

    return PaginatedNotifications(
        items=[_to_response(n) for n in notifications],
        total=total,
        unread_count=unread_count,
        page=page,
        per_page=per_page,
    )


@notifications_router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("notifications", "read")),
):
    count = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.is_read.is_(False))
        )
    ).scalar() or 0
    return UnreadCountResponse(count=count)


@notifications_router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("notifications", "update")),
):
    notification = await _get_notification_or_404(session, notification_id)
    notification.is_read = True
    await session.commit()
    await session.refresh(notification)
    return _to_response(notification)


@notifications_router.patch("/mark-all-read")
async def mark_all_read(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("notifications", "update")),
):
    await session.execute(
        update(Notification).where(Notification.is_read.is_(False)).values(is_read=True)
    )
    await session.commit()
    return {"message": "All notifications marked as read"}


@notifications_router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("notifications", "delete")),
):
    notification = await _get_notification_or_404(session, notification_id)
    await session.execute(delete(Notification).where(Notification.id == notification.id))
    await session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_notification_or_404(session: AsyncSession, notification_id: str) -> Notification:
    try:
        uid = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )

    result = await session.execute(select(Notification).where(Notification.id == uid))
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    return notification


def _to_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=str(notification.id),
        title=notification.title,
        message=notification.message,
        link=notification.link,
        icon=notification.icon,
        is_read=notification.is_read,
        created_at=notification.created_at.isoformat() if notification.created_at else "",
    )
