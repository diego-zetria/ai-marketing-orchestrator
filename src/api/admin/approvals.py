"""Admin API endpoints for managing approval assets."""

from __future__ import annotations

import logging
import uuid

import boto3
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.api.admin.notification_helper import create_notification
from src.approval.models import (
    ApprovalAsset,
    ApprovalComment,
    ApprovalDecision,
    ApprovalEvent,
    AssetVersion,
)

logger = logging.getLogger(__name__)

approvals_router = APIRouter(prefix="/approvals", tags=["approvals"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ApprovalStats(BaseModel):
    total_assets: int
    pending_review: int
    approved: int
    changes_requested: int


class ApprovalAssetResponse(BaseModel):
    id: str
    client_name: str
    title: str
    status: str
    current_version: int
    clickup_task_id: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class AssetVersionResponse(BaseModel):
    id: str
    version_number: int
    file_type: str
    file_format: str
    original_url: str
    thumbnail_url: str | None
    file_size_bytes: int | None
    created_at: str


class CommentResponse(BaseModel):
    id: str
    author_type: str
    author_name: str
    content: str
    created_at: str


class DecisionResponse(BaseModel):
    id: str
    version_id: str
    decision: str
    comment: str | None
    decided_by: str
    decided_at: str


class EventResponse(BaseModel):
    id: str
    event_type: str
    actor: str
    metadata_: dict | None
    created_at: str


class ApprovalAssetDetail(ApprovalAssetResponse):
    description: str | None
    versions: list[AssetVersionResponse]
    comments: list[CommentResponse]
    decisions: list[DecisionResponse]


class PaginatedApprovals(BaseModel):
    items: list[ApprovalAssetResponse]
    total: int
    page: int
    per_page: int


class AddCommentRequest(BaseModel):
    content: str


# Allowed sort columns for approval listing (validated explicitly for safety)
_APPROVAL_SORT_COLUMNS: dict[str, object] = {
    "created_at": ApprovalAsset.created_at,
    "title": ApprovalAsset.title,
    "status": ApprovalAsset.status,
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@approvals_router.get("/stats", response_model=ApprovalStats)
async def get_approval_stats(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("approvals", "read")),
):
    result = await session.execute(
        select(
            func.count().label("total"),
            func.count().filter(ApprovalAsset.status == "pending_review").label("pending"),
            func.count().filter(ApprovalAsset.status == "approved").label("approved"),
            func.count().filter(ApprovalAsset.status == "changes_requested").label("changes"),
        ).select_from(ApprovalAsset)
    )
    row = result.one()
    return ApprovalStats(
        total_assets=row.total,
        pending_review=row.pending,
        approved=row.approved,
        changes_requested=row.changes,
    )


@approvals_router.get("", response_model=PaginatedApprovals)
async def list_approvals(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    client_id: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("approvals", "read")),
):
    # Validate sort_by against allowed set
    if sort_by not in _APPROVAL_SORT_COLUMNS:
        sort_by = "created_at"
    sort_col = _APPROVAL_SORT_COLUMNS[sort_by]

    # Build base filters
    base = select(ApprovalAsset).options(selectinload(ApprovalAsset.client))
    count_base = select(func.count()).select_from(ApprovalAsset)

    if status_filter:
        base = base.where(ApprovalAsset.status == status_filter)
        count_base = count_base.where(ApprovalAsset.status == status_filter)
    if client_id:
        try:
            uid = uuid.UUID(client_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid client_id")
        base = base.where(ApprovalAsset.client_id == uid)
        count_base = count_base.where(ApprovalAsset.client_id == uid)
    if search:
        search_filter = ApprovalAsset.title.ilike(f"%{search}%")
        base = base.where(search_filter)
        count_base = count_base.where(search_filter)

    # Total count
    total = (await session.execute(count_base)).scalar() or 0

    # Sorting
    order = sort_col.asc() if sort_order != "desc" else sort_col.desc()

    # Paginated results
    offset = (page - 1) * per_page
    stmt = base.order_by(order).offset(offset).limit(per_page)
    result = await session.execute(stmt)
    assets = result.scalars().all()

    return PaginatedApprovals(
        items=[_to_asset_response(a) for a in assets],
        total=total,
        page=page,
        per_page=per_page,
    )


@approvals_router.get("/{asset_id}", response_model=ApprovalAssetDetail)
async def get_approval_detail(
    asset_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("approvals", "read")),
):
    asset = await _get_asset_or_404(session, asset_id)
    return _to_asset_detail(asset)


@approvals_router.get("/{asset_id}/events", response_model=list[EventResponse])
async def get_approval_events(
    asset_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("approvals", "read")),
):
    asset = await _get_asset_or_404(session, asset_id)
    events = sorted(asset.events, key=lambda e: e.created_at)
    return [_to_event_response(e) for e in events]


@approvals_router.get("/{asset_id}/media-url/{version_id}")
async def get_media_url(
    asset_id: str,
    version_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("approvals", "read")),
):
    asset = await _get_asset_or_404(session, asset_id)

    try:
        vid = uuid.UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    version = next((v for v in asset.versions if v.id == vid), None)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    # Parse bucket and key from original_url (s3://bucket/key)
    url = version.original_url
    if url.startswith("s3://"):
        parts = url[5:].split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate pre-signed URL for this media type",
        )

    s3 = boto3.client("s3")
    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600,
    )
    return {"url": presigned_url}


@approvals_router.post(
    "/{asset_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    asset_id: str,
    payload: AddCommentRequest,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("approvals", "create")),
):
    asset = await _get_asset_or_404(session, asset_id)

    comment = ApprovalComment(
        asset_id=asset.id,
        author_type="admin",
        author_name=_user.name,
        content=payload.content,
    )
    session.add(comment)

    await log_activity(
        session,
        action="add_comment",
        entity_type="approval_asset",
        entity_id=str(asset.id),
        details={"content": payload.content[:200]},
        user=_user.name,
    )
    await create_notification(
        session,
        title="Novo comentario",
        message=f"Comentario adicionado em '{asset.title}'.",
        link=f"/admin/approvals/{asset.id}",
        icon="approval",
    )
    await session.commit()
    await session.refresh(comment)
    return _to_comment_response(comment)


@approvals_router.post("/{asset_id}/resend-email")
async def resend_email(
    asset_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("approvals", "update")),
):
    asset = await _get_asset_or_404(session, asset_id)

    # Find active magic link for this asset
    magic_link = next(
        (ml for ml in asset.magic_links if ml.is_active),
        None,
    )
    if magic_link is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active magic link found for this asset",
        )

    # Get client email
    client = asset.client
    if not client or not client.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client has no email configured",
        )

    # Find latest version thumbnail
    latest_version = max(asset.versions, key=lambda v: v.version_number, default=None)
    thumbnail_url = latest_version.thumbnail_url or "" if latest_version else ""

    from src.approval.services.email import EmailService
    from src.config.settings import Settings

    settings = Settings()

    email_service = EmailService(
        from_email=getattr(settings, "approval_from_email", "approvals@example.com"),
        portal_domain=getattr(settings, "approval_portal_domain", "https://approvals.example.com"),
    )
    await email_service.send_new_asset_email(
        to_email=client.email,
        client_name=client.display_name,
        asset_title=asset.title,
        thumbnail_url=thumbnail_url,
        magic_link_token=magic_link.token,
        version_number=asset.current_version,
    )

    await log_activity(
        session,
        action="resend_email",
        entity_type="approval_asset",
        entity_id=str(asset.id),
        details={"to_email": client.email},
        user=_user.name,
    )
    await session.commit()

    return {"message": "Email reenviado com sucesso"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_asset_or_404(session: AsyncSession, asset_id: str) -> ApprovalAsset:
    try:
        uid = uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval asset not found",
        )

    result = await session.execute(
        select(ApprovalAsset)
        .options(
            selectinload(ApprovalAsset.client),
            selectinload(ApprovalAsset.versions),
            selectinload(ApprovalAsset.comments),
            selectinload(ApprovalAsset.decisions),
            selectinload(ApprovalAsset.events),
            selectinload(ApprovalAsset.magic_links),
        )
        .where(ApprovalAsset.id == uid)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval asset not found",
        )
    return asset


def _to_asset_response(asset: ApprovalAsset) -> ApprovalAssetResponse:
    return ApprovalAssetResponse(
        id=str(asset.id),
        client_name=asset.client.display_name if asset.client else "",
        title=asset.title,
        status=asset.status,
        current_version=asset.current_version,
        clickup_task_id=asset.clickup_task_id,
        created_at=asset.created_at.isoformat() if asset.created_at else "",
        updated_at=asset.updated_at.isoformat() if asset.updated_at else "",
    )


def _to_asset_detail(asset: ApprovalAsset) -> ApprovalAssetDetail:
    return ApprovalAssetDetail(
        id=str(asset.id),
        client_name=asset.client.display_name if asset.client else "",
        title=asset.title,
        status=asset.status,
        current_version=asset.current_version,
        clickup_task_id=asset.clickup_task_id,
        created_at=asset.created_at.isoformat() if asset.created_at else "",
        updated_at=asset.updated_at.isoformat() if asset.updated_at else "",
        description=asset.description,
        versions=[
            _to_version_response(v)
            for v in sorted(asset.versions, key=lambda v: v.version_number)
        ],
        comments=[
            _to_comment_response(c)
            for c in sorted(asset.comments, key=lambda c: c.created_at)
        ],
        decisions=[
            _to_decision_response(d)
            for d in sorted(asset.decisions, key=lambda d: d.decided_at)
        ],
    )


def _to_version_response(version: AssetVersion) -> AssetVersionResponse:
    return AssetVersionResponse(
        id=str(version.id),
        version_number=version.version_number,
        file_type=version.file_type,
        file_format=version.file_format,
        original_url=version.original_url,
        thumbnail_url=version.thumbnail_url,
        file_size_bytes=version.file_size_bytes,
        created_at=version.created_at.isoformat() if version.created_at else "",
    )


def _to_comment_response(comment: ApprovalComment) -> CommentResponse:
    return CommentResponse(
        id=str(comment.id),
        author_type=comment.author_type,
        author_name=comment.author_name,
        content=comment.content,
        created_at=comment.created_at.isoformat() if comment.created_at else "",
    )


def _to_decision_response(decision: ApprovalDecision) -> DecisionResponse:
    return DecisionResponse(
        id=str(decision.id),
        version_id=str(decision.version_id),
        decision=decision.decision,
        comment=decision.comment,
        decided_by=decision.decided_by,
        decided_at=decision.decided_at.isoformat() if decision.decided_at else "",
    )


def _to_event_response(event: ApprovalEvent) -> EventResponse:
    return EventResponse(
        id=str(event.id),
        event_type=event.event_type,
        actor=event.actor,
        metadata_=event.metadata_,
        created_at=event.created_at.isoformat() if event.created_at else "",
    )
