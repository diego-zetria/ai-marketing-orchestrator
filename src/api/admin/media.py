"""Admin API endpoints for Media Library browsing."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.admin.activity_helper import log_activity
from src.api.admin.auth import CurrentUser, require_permission
from src.api.admin.deps import get_db
from src.approval.models import ApprovalAsset, ApprovalEvent, AssetVersion
from src.db.admin_models import Client

logger = logging.getLogger(__name__)

media_router = APIRouter(prefix="/media", tags=["media"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class LatestVersionResponse(BaseModel):
    version_number: int
    file_url: str | None
    thumbnail_url: str | None
    file_type: str
    file_size: int | None
    created_at: str


class MediaAssetResponse(BaseModel):
    id: str
    title: str
    client_id: str
    client_name: str
    status: str
    latest_version: LatestVersionResponse | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class PaginatedMedia(BaseModel):
    items: list[MediaAssetResponse]
    total: int
    page: int
    per_page: int


class MediaVersionResponse(BaseModel):
    id: str
    version_number: int
    file_type: str
    file_format: str
    file_url: str
    thumbnail_url: str | None
    file_size: int | None
    width: int | None
    height: int | None
    duration_seconds: float | None
    uploaded_by: str | None
    created_at: str


class MediaEventResponse(BaseModel):
    id: str
    event_type: str
    actor: str
    metadata_: dict | None
    created_at: str


class MediaAssetDetail(MediaAssetResponse):
    description: str | None
    clickup_task_id: str
    current_version: int
    versions: list[MediaVersionResponse]
    events: list[MediaEventResponse]


class ClientMediaCount(BaseModel):
    client_id: str
    client_name: str
    count: int


class MediaStatsResponse(BaseModel):
    total_assets: int
    total_size_bytes: int
    by_status: dict[str, int]
    by_client: list[ClientMediaCount]


# Allowed sort columns (validated explicitly for safety)
_MEDIA_SORT_COLUMNS: dict[str, object] = {
    "created_at": ApprovalAsset.created_at,
    "updated_at": ApprovalAsset.updated_at,
    "title": ApprovalAsset.title,
    "status": ApprovalAsset.status,
}

# Valid media type prefixes for file_type filtering
_MEDIA_TYPE_PREFIXES: dict[str, str] = {
    "image": "image",
    "video": "video",
    "document": "document",
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@media_router.get("/stats", response_model=MediaStatsResponse)
async def get_media_stats(
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("media", "read")),
):
    """Media statistics for the dashboard."""
    # Total assets
    total_assets = (
        await session.execute(select(func.count()).select_from(ApprovalAsset))
    ).scalar() or 0

    # Total storage size (sum of file_size_bytes across all versions)
    total_size = (
        await session.execute(select(func.coalesce(func.sum(AssetVersion.file_size_bytes), 0)))
    ).scalar() or 0

    # Assets by status
    status_rows = (
        await session.execute(
            select(ApprovalAsset.status, func.count().label("cnt")).group_by(ApprovalAsset.status)
        )
    ).all()
    by_status: dict[str, int] = {row.status: row.cnt for row in status_rows}

    # Assets by client
    client_rows = (
        await session.execute(
            select(
                ApprovalAsset.client_id,
                Client.display_name,
                func.count().label("cnt"),
            )
            .join(Client, ApprovalAsset.client_id == Client.id)
            .group_by(ApprovalAsset.client_id, Client.display_name)
            .order_by(func.count().desc())
        )
    ).all()
    by_client = [
        ClientMediaCount(
            client_id=str(row.client_id),
            client_name=row.display_name,
            count=row.cnt,
        )
        for row in client_rows
    ]

    return MediaStatsResponse(
        total_assets=total_assets,
        total_size_bytes=int(total_size),
        by_status=by_status,
        by_client=by_client,
    )


@media_router.get("", response_model=PaginatedMedia)
async def list_media(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    client_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    media_type: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("media", "read")),
):
    """Paginated list of media assets with latest version info."""
    # Validate sort_by against allowed set
    if sort_by not in _MEDIA_SORT_COLUMNS:
        sort_by = "created_at"
    sort_col = _MEDIA_SORT_COLUMNS[sort_by]

    # Build base query and count query
    base = select(ApprovalAsset).options(
        selectinload(ApprovalAsset.client),
        selectinload(ApprovalAsset.versions),
    )
    count_base = select(func.count()).select_from(ApprovalAsset)

    # --- Filters ---

    if client_id:
        uid = _parse_uuid_or_400(client_id, "client_id")
        base = base.where(ApprovalAsset.client_id == uid)
        count_base = count_base.where(ApprovalAsset.client_id == uid)

    if status_filter:
        base = base.where(ApprovalAsset.status == status_filter)
        count_base = count_base.where(ApprovalAsset.status == status_filter)

    if media_type and media_type in _MEDIA_TYPE_PREFIXES:
        # Filter assets that have at least one version with the matching file_type
        prefix = _MEDIA_TYPE_PREFIXES[media_type]
        version_sub = (
            select(AssetVersion.asset_id)
            .where(AssetVersion.file_type.ilike(f"{prefix}%"))
            .distinct()
            .subquery()
        )
        base = base.where(ApprovalAsset.id.in_(select(version_sub.c.asset_id)))
        count_base = count_base.where(ApprovalAsset.id.in_(select(version_sub.c.asset_id)))

    if search:
        search_filter = ApprovalAsset.title.ilike(f"%{search}%")
        base = base.where(search_filter)
        count_base = count_base.where(search_filter)

    # Total count
    total = (await session.execute(count_base)).scalar() or 0

    # Sorting
    order = sort_col.asc() if sort_dir != "desc" else sort_col.desc()

    # Paginated results
    offset = (page - 1) * per_page
    stmt = base.order_by(order).offset(offset).limit(per_page)
    result = await session.execute(stmt)
    assets = result.scalars().all()

    return PaginatedMedia(
        items=[_to_media_response(a) for a in assets],
        total=total,
        page=page,
        per_page=per_page,
    )


@media_router.get("/{asset_id}", response_model=MediaAssetDetail)
async def get_media_detail(
    asset_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("media", "read")),
):
    """Full asset detail with all versions and approval events."""
    asset = await _get_asset_or_404(session, asset_id)
    return _to_media_detail(asset)


@media_router.delete("/{asset_id}", response_model=MediaAssetResponse)
async def archive_media(
    asset_id: str,
    session: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(require_permission("media", "delete")),
):
    """Soft-delete (archive) a media asset by setting status to 'archived'."""
    asset = await _get_asset_or_404(session, asset_id)

    if asset.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset is already archived",
        )

    old_status = asset.status
    asset.status = "archived"

    await log_activity(
        session,
        action="archive",
        entity_type="media_asset",
        entity_id=str(asset.id),
        details={"title": asset.title, "old_status": old_status},
        user=_user.name,
    )
    await session.commit()
    await session.refresh(asset)

    return _to_media_response(asset)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_uuid_or_400(value: str, field_name: str) -> uuid.UUID:
    """Parse a string as UUID, raising HTTP 400 on failure."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID for {field_name}: '{value}'",
        )


async def _get_asset_or_404(session: AsyncSession, asset_id: str) -> ApprovalAsset:
    uid = _parse_uuid_or_400(asset_id, "asset_id")

    result = await session.execute(
        select(ApprovalAsset)
        .options(
            selectinload(ApprovalAsset.client),
            selectinload(ApprovalAsset.versions),
            selectinload(ApprovalAsset.events),
        )
        .where(ApprovalAsset.id == uid)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media asset not found",
        )
    return asset


def _get_latest_version(asset: ApprovalAsset) -> AssetVersion | None:
    """Return the version with the highest version_number, or None."""
    if not asset.versions:
        return None
    return max(asset.versions, key=lambda v: v.version_number)


def _to_media_response(asset: ApprovalAsset) -> MediaAssetResponse:
    latest = _get_latest_version(asset)
    latest_version = None
    if latest is not None:
        latest_version = LatestVersionResponse(
            version_number=latest.version_number,
            file_url=latest.original_url,
            thumbnail_url=latest.thumbnail_url,
            file_type=latest.file_type,
            file_size=latest.file_size_bytes,
            created_at=latest.created_at.isoformat() if latest.created_at else "",
        )

    return MediaAssetResponse(
        id=str(asset.id),
        title=asset.title,
        client_id=str(asset.client_id),
        client_name=asset.client.display_name if asset.client else "",
        status=asset.status,
        latest_version=latest_version,
        created_at=asset.created_at.isoformat() if asset.created_at else "",
        updated_at=asset.updated_at.isoformat() if asset.updated_at else "",
    )


def _to_media_detail(asset: ApprovalAsset) -> MediaAssetDetail:
    latest = _get_latest_version(asset)
    latest_version = None
    if latest is not None:
        latest_version = LatestVersionResponse(
            version_number=latest.version_number,
            file_url=latest.original_url,
            thumbnail_url=latest.thumbnail_url,
            file_type=latest.file_type,
            file_size=latest.file_size_bytes,
            created_at=latest.created_at.isoformat() if latest.created_at else "",
        )

    return MediaAssetDetail(
        id=str(asset.id),
        title=asset.title,
        client_id=str(asset.client_id),
        client_name=asset.client.display_name if asset.client else "",
        status=asset.status,
        latest_version=latest_version,
        created_at=asset.created_at.isoformat() if asset.created_at else "",
        updated_at=asset.updated_at.isoformat() if asset.updated_at else "",
        description=asset.description,
        clickup_task_id=asset.clickup_task_id,
        current_version=asset.current_version,
        versions=[
            _to_version_response(v)
            for v in sorted(asset.versions, key=lambda v: v.version_number, reverse=True)
        ],
        events=[
            _to_event_response(e)
            for e in sorted(asset.events, key=lambda e: e.created_at, reverse=True)
        ],
    )


def _to_version_response(version: AssetVersion) -> MediaVersionResponse:
    return MediaVersionResponse(
        id=str(version.id),
        version_number=version.version_number,
        file_type=version.file_type,
        file_format=version.file_format,
        file_url=version.original_url,
        thumbnail_url=version.thumbnail_url,
        file_size=version.file_size_bytes,
        width=version.width,
        height=version.height,
        duration_seconds=version.duration_seconds,
        uploaded_by=version.uploaded_by,
        created_at=version.created_at.isoformat() if version.created_at else "",
    )


def _to_event_response(event: ApprovalEvent) -> MediaEventResponse:
    return MediaEventResponse(
        id=str(event.id),
        event_type=event.event_type,
        actor=event.actor,
        metadata_=event.metadata_,
        created_at=event.created_at.isoformat() if event.created_at else "",
    )
