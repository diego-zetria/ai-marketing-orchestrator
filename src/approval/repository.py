"""Async CRUD repository for the client approval portal.

All functions accept an AsyncSession as first argument and operate on the
approval-portal models (Client, ApprovalAsset, AssetVersion, MagicLink,
ApprovalComment, ApprovalDecision, ApprovalEvent).
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.approval.models import (
    ApprovalAsset,
    ApprovalComment,
    ApprovalDecision,
    ApprovalEvent,
    AssetVersion,
    Client,
    MagicLink,
)

MAGIC_LINK_TTL_DAYS = 7


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
async def get_client_by_list_id(session: AsyncSession, list_id: str) -> Client | None:
    """Find an active client by its ClickUp list_id."""
    stmt = select(Client).where(Client.clickup_list_id == list_id, Client.is_active.is_(True))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_client_by_slug(session: AsyncSession, slug: str) -> Client | None:
    """Find an active client by its URL slug."""
    stmt = select(Client).where(Client.slug == slug, Client.is_active.is_(True))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
async def create_asset(
    session: AsyncSession,
    *,
    client_id: uuid.UUID,
    clickup_task_id: str,
    title: str,
    description: str | None = None,
) -> ApprovalAsset:
    """Create a new approval asset linked to a ClickUp task."""
    asset = ApprovalAsset(
        client_id=client_id,
        clickup_task_id=clickup_task_id,
        title=title,
        description=description,
    )
    session.add(asset)
    await session.flush()
    return asset


async def get_asset_by_task_id(
    session: AsyncSession, clickup_task_id: str
) -> ApprovalAsset | None:
    """Find an approval asset by its ClickUp task ID."""
    stmt = select(ApprovalAsset).where(ApprovalAsset.clickup_task_id == clickup_task_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_asset_with_relations(
    session: AsyncSession, asset_id: uuid.UUID
) -> ApprovalAsset | None:
    """Load an asset with all related entities (client, versions, comments, decisions)."""
    stmt = (
        select(ApprovalAsset)
        .where(ApprovalAsset.id == asset_id)
        .options(
            selectinload(ApprovalAsset.client),
            selectinload(ApprovalAsset.versions),
            selectinload(ApprovalAsset.comments),
            selectinload(ApprovalAsset.decisions),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_asset_status(
    session: AsyncSession,
    asset_id: uuid.UUID,
    status: str,
    version: int | None = None,
) -> None:
    """Update the status (and optionally current_version) of an asset."""
    values: dict = {"status": status, "updated_at": datetime.now(timezone.utc)}
    if version is not None:
        values["current_version"] = version
    stmt = update(ApprovalAsset).where(ApprovalAsset.id == asset_id).values(**values)
    await session.execute(stmt)
    await session.flush()


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------
async def create_version(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    version_number: int,
    file_type: str,
    file_format: str,
    original_url: str,
    thumbnail_url: str | None = None,
    file_size_bytes: int | None = None,
    width: int | None = None,
    height: int | None = None,
    duration_seconds: float | None = None,
    uploaded_by: str | None = None,
) -> AssetVersion:
    """Create a new version record for an approval asset."""
    version = AssetVersion(
        asset_id=asset_id,
        version_number=version_number,
        file_type=file_type,
        file_format=file_format,
        original_url=original_url,
        thumbnail_url=thumbnail_url,
        file_size_bytes=file_size_bytes,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        uploaded_by=uploaded_by,
    )
    session.add(version)
    await session.flush()
    return version


# ---------------------------------------------------------------------------
# Magic Links
# ---------------------------------------------------------------------------
async def create_magic_link(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    client_id: uuid.UUID,
) -> MagicLink:
    """Generate a magic-link token with a 7-day TTL."""
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=MAGIC_LINK_TTL_DAYS)
    link = MagicLink(
        token=token,
        asset_id=asset_id,
        client_id=client_id,
        expires_at=expires_at,
    )
    session.add(link)
    await session.flush()
    return link


async def validate_magic_link(session: AsyncSession, token: str) -> MagicLink | None:
    """Validate a magic-link token: must be active and not expired.

    On success, increments access_count and sets accessed_at.
    Returns the MagicLink if valid, None otherwise.
    """
    now = datetime.now(timezone.utc)
    stmt = select(MagicLink).where(
        MagicLink.token == token,
        MagicLink.is_active.is_(True),
        MagicLink.expires_at > now,
    )
    result = await session.execute(stmt)
    link = result.scalar_one_or_none()
    if link is None:
        return None

    link.access_count += 1
    link.accessed_at = now
    await session.flush()
    return link


async def deactivate_magic_links(session: AsyncSession, asset_id: uuid.UUID) -> None:
    """Deactivate all active magic links for an asset."""
    stmt = (
        update(MagicLink)
        .where(MagicLink.asset_id == asset_id, MagicLink.is_active.is_(True))
        .values(is_active=False)
    )
    await session.execute(stmt)
    await session.flush()


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
async def add_comment(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    version_id: uuid.UUID | None,
    author_type: str,
    author_name: str,
    content: str,
) -> ApprovalComment:
    """Add a review comment to an asset (optionally tied to a version)."""
    comment = ApprovalComment(
        asset_id=asset_id,
        version_id=version_id,
        author_type=author_type,
        author_name=author_name,
        content=content,
    )
    session.add(comment)
    await session.flush()
    return comment


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------
async def save_decision(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    version_id: uuid.UUID,
    decision: str,
    decided_by: str,
    comment: str | None = None,
) -> ApprovalDecision:
    """Record an approval or rejection decision for an asset version."""
    record = ApprovalDecision(
        asset_id=asset_id,
        version_id=version_id,
        decision=decision,
        decided_by=decided_by,
        comment=comment,
    )
    session.add(record)
    await session.flush()
    return record


# ---------------------------------------------------------------------------
# Events (Audit Log)
# ---------------------------------------------------------------------------
async def log_event(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    event_type: str,
    actor: str | None = None,
    metadata: dict | None = None,
) -> ApprovalEvent:
    """Write an audit-log entry for an approval action.

    If *actor* is None, defaults to ``"system"``.
    Note: The ORM attribute is ``metadata_`` (with trailing underscore).
    """
    event = ApprovalEvent(
        asset_id=asset_id,
        event_type=event_type,
        actor=actor or "system",
        metadata_=metadata,
    )
    session.add(event)
    await session.flush()
    return event


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
async def get_pending_assets_older_than(
    session: AsyncSession, days: int
) -> list[ApprovalAsset]:
    """Return assets still in 'pending_review' that were created more than *days* ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(ApprovalAsset).where(
        ApprovalAsset.status == "pending_review",
        ApprovalAsset.created_at < cutoff,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
