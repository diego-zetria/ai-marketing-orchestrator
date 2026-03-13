"""Admin API endpoints for Webhook Management."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.db.admin_models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)

webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

WEBHOOK_EVENTS = [
    "client_created",
    "client_updated",
    "client_deleted",
    "member_created",
    "member_updated",
    "approval_status_changed",
    "approval_comment_added",
]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class WebhookCreate(BaseModel):
    url: str
    description: str | None = None
    events: list[str]
    secret: str | None = None
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one event is required")
        invalid = [e for e in v if e not in WEBHOOK_EVENTS]
        if invalid:
            raise ValueError(f"Invalid events: {invalid}. Valid: {WEBHOOK_EVENTS}")
        return v


class WebhookUpdate(BaseModel):
    url: str | None = None
    description: str | None = None
    events: list[str] | None = None
    secret: str | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            if not v:
                raise ValueError("At least one event is required")
            invalid = [e for e in v if e not in WEBHOOK_EVENTS]
            if invalid:
                raise ValueError(f"Invalid events: {invalid}. Valid: {WEBHOOK_EVENTS}")
        return v


class LastDeliveryInfo(BaseModel):
    status_code: int | None
    success: bool
    created_at: str  # ISO format


class WebhookResponse(BaseModel):
    id: str
    url: str
    description: str | None
    events: list[str]
    is_active: bool
    created_at: str  # ISO format
    updated_at: str  # ISO format
    last_delivery: LastDeliveryInfo | None

    model_config = {"from_attributes": True}


class PaginatedWebhooks(BaseModel):
    items: list[WebhookResponse]
    total: int
    page: int
    per_page: int


class DeliveryResponse(BaseModel):
    id: str
    event: str
    payload: dict
    status_code: int | None
    response_body: str | None
    error: str | None
    duration_ms: int | None
    success: bool
    created_at: str  # ISO format

    model_config = {"from_attributes": True}


class PaginatedDeliveries(BaseModel):
    items: list[DeliveryResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@webhooks_router.get("", response_model=PaginatedWebhooks)
async def list_webhooks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("webhooks", "read")),
):
    # Total count
    count_base = select(func.count()).select_from(Webhook)
    total = (await session.execute(count_base)).scalar() or 0

    # Paginated results, newest first
    offset = (page - 1) * per_page
    stmt = (
        select(Webhook)
        .order_by(Webhook.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await session.execute(stmt)
    webhooks = result.scalars().all()

    # Fetch last delivery for each webhook in one query
    webhook_ids = [w.id for w in webhooks]
    last_deliveries: dict[uuid.UUID, WebhookDelivery] = {}
    if webhook_ids:
        # Subquery: max created_at per webhook_id
        sub = (
            select(
                WebhookDelivery.webhook_id,
                func.max(WebhookDelivery.created_at).label("max_created_at"),
            )
            .where(WebhookDelivery.webhook_id.in_(webhook_ids))
            .group_by(WebhookDelivery.webhook_id)
            .subquery()
        )
        delivery_stmt = select(WebhookDelivery).join(
            sub,
            (WebhookDelivery.webhook_id == sub.c.webhook_id)
            & (WebhookDelivery.created_at == sub.c.max_created_at),
        )
        delivery_result = await session.execute(delivery_stmt)
        for d in delivery_result.scalars().all():
            last_deliveries[d.webhook_id] = d

    return PaginatedWebhooks(
        items=[_to_webhook_response(w, last_deliveries.get(w.id)) for w in webhooks],
        total=total,
        page=page,
        per_page=per_page,
    )


@webhooks_router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    payload: WebhookCreate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("webhooks", "create")),
):
    webhook = Webhook(
        url=payload.url,
        description=payload.description,
        events=payload.events,
        secret=payload.secret,
        is_active=payload.is_active,
    )
    session.add(webhook)
    await session.flush()

    await log_activity(
        session,
        action="create",
        entity_type="webhook",
        entity_id=str(webhook.id),
        details={"url": webhook.url, "events": webhook.events},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(webhook)

    return _to_webhook_response(webhook, last_delivery=None)


@webhooks_router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    payload: WebhookUpdate,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("webhooks", "update")),
):
    webhook = await _get_webhook_or_404(session, webhook_id)

    update_data = payload.model_dump(exclude_unset=True)
    changes: dict = {}
    for field, value in update_data.items():
        current = getattr(webhook, field)
        if current != value:
            changes[field] = value
            setattr(webhook, field, value)

    if changes:
        await log_activity(
            session,
            action="update",
            entity_type="webhook",
            entity_id=str(webhook.id),
            details=changes,
            user=_user.name,
        )
        await session.commit()
        await session.refresh(webhook)

    # Fetch last delivery for response
    last_delivery = await _get_last_delivery(session, webhook.id)
    return _to_webhook_response(webhook, last_delivery)


@webhooks_router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("webhooks", "delete")),
):
    webhook = await _get_webhook_or_404(session, webhook_id)

    await log_activity(
        session,
        action="delete",
        entity_type="webhook",
        entity_id=str(webhook.id),
        details={"url": webhook.url},
        user=_user.name,
    )

    await session.execute(delete(Webhook).where(Webhook.id == webhook.id))
    await session.commit()


@webhooks_router.get("/{webhook_id}/deliveries", response_model=PaginatedDeliveries)
async def list_deliveries(
    webhook_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("webhooks", "read")),
):
    webhook = await _get_webhook_or_404(session, webhook_id)

    # Total count
    count_base = (
        select(func.count())
        .select_from(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook.id)
    )
    total = (await session.execute(count_base)).scalar() or 0

    # Paginated results, newest first
    offset = (page - 1) * per_page
    stmt = (
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook.id)
        .order_by(WebhookDelivery.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await session.execute(stmt)
    deliveries = result.scalars().all()

    return PaginatedDeliveries(
        items=[_to_delivery_response(d) for d in deliveries],
        total=total,
        page=page,
        per_page=per_page,
    )


@webhooks_router.post("/{webhook_id}/test", response_model=DeliveryResponse)
async def test_webhook(
    webhook_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("webhooks", "update")),
):
    webhook = await _get_webhook_or_404(session, webhook_id)

    test_payload = {
        "event": "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "webhook_id": str(webhook.id),
    }

    delivery = await _send_webhook(webhook, event="test", payload=test_payload)
    session.add(delivery)

    await log_activity(
        session,
        action="test",
        entity_type="webhook",
        entity_id=str(webhook.id),
        details={"success": delivery.success, "status_code": delivery.status_code},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(delivery)

    return _to_delivery_response(delivery)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_webhook_or_404(session: AsyncSession, webhook_id: str) -> Webhook:
    try:
        uid = uuid.UUID(webhook_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found"
        )

    result = await session.execute(select(Webhook).where(Webhook.id == uid))
    webhook = result.scalar_one_or_none()
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found"
        )
    return webhook


async def _get_last_delivery(
    session: AsyncSession, webhook_id: uuid.UUID
) -> WebhookDelivery | None:
    stmt = (
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _send_webhook(
    webhook: Webhook, *, event: str, payload: dict
) -> WebhookDelivery:
    """Send an HTTP POST to the webhook URL and return a WebhookDelivery record."""
    headers = {"Content-Type": "application/json"}

    # Add HMAC signature header if secret is configured
    if webhook.secret:
        import hashlib
        import hmac
        import json

        body_bytes = json.dumps(payload, default=str).encode()
        signature = hmac.new(
            webhook.secret.encode(), body_bytes, hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"

    status_code = None
    response_body = None
    error = None
    success = False
    start = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(webhook.url, json=payload, headers=headers)
            status_code = resp.status_code
            response_body = resp.text[:2000]  # Cap response body size
            success = 200 <= resp.status_code < 300
    except httpx.TimeoutException:
        error = "Request timed out after 10s"
    except httpx.RequestError as exc:
        error = str(exc)[:500]
    except Exception as exc:
        error = f"Unexpected error: {str(exc)[:450]}"

    duration_ms = int((time.monotonic() - start) * 1000)

    return WebhookDelivery(
        webhook_id=webhook.id,
        event=event,
        payload=payload,
        status_code=status_code,
        response_body=response_body,
        error=error,
        duration_ms=duration_ms,
        success=success,
    )


def _to_webhook_response(
    webhook: Webhook, last_delivery: WebhookDelivery | None
) -> WebhookResponse:
    last_delivery_info = None
    if last_delivery is not None:
        last_delivery_info = LastDeliveryInfo(
            status_code=last_delivery.status_code,
            success=last_delivery.success,
            created_at=(
                last_delivery.created_at.isoformat()
                if last_delivery.created_at
                else ""
            ),
        )

    return WebhookResponse(
        id=str(webhook.id),
        url=webhook.url,
        description=webhook.description,
        events=webhook.events or [],
        is_active=webhook.is_active,
        created_at=webhook.created_at.isoformat() if webhook.created_at else "",
        updated_at=webhook.updated_at.isoformat() if webhook.updated_at else "",
        last_delivery=last_delivery_info,
    )


def _to_delivery_response(delivery: WebhookDelivery) -> DeliveryResponse:
    return DeliveryResponse(
        id=str(delivery.id),
        event=delivery.event,
        payload=delivery.payload,
        status_code=delivery.status_code,
        response_body=delivery.response_body,
        error=delivery.error,
        duration_ms=delivery.duration_ms,
        success=delivery.success,
        created_at=delivery.created_at.isoformat() if delivery.created_at else "",
    )
