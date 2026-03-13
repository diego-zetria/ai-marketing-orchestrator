"""SQLAlchemy ORM models for the client approval portal.

Maps to the 7 tables created by migration c1a2b3d4e5f6:
- clients (extended with portal columns via admin_models.Client)
- approval_assets
- asset_versions
- magic_links
- approval_comments
- approval_decisions
- approval_events
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.admin_models import Client
from src.db.models import Base

# Re-export Client so consumers can import from src.approval.models
__all__ = [
    "Client",
    "ApprovalAsset",
    "AssetVersion",
    "MagicLink",
    "ApprovalComment",
    "ApprovalDecision",
    "ApprovalEvent",
]


class ApprovalAsset(Base):
    """Media asset pending client approval, linked to a ClickUp task."""

    __tablename__ = "approval_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.clients.id"),
        nullable=False,
        index=True,
    )
    clickup_task_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending_review"
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    client: Mapped["Client"] = relationship(
        "Client", backref="approval_assets", lazy="selectin"
    )
    versions: Mapped[list["AssetVersion"]] = relationship(
        back_populates="asset", lazy="selectin"
    )
    comments: Mapped[list["ApprovalComment"]] = relationship(
        back_populates="asset", lazy="selectin"
    )
    decisions: Mapped[list["ApprovalDecision"]] = relationship(
        back_populates="asset", lazy="selectin"
    )
    events: Mapped[list["ApprovalEvent"]] = relationship(
        back_populates="asset", lazy="selectin"
    )
    magic_links: Mapped[list["MagicLink"]] = relationship(
        back_populates="asset", lazy="selectin"
    )


class AssetVersion(Base):
    """Version history for an approval asset (images, videos, documents)."""

    __tablename__ = "asset_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.approval_assets.id"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    original_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    asset: Mapped["ApprovalAsset"] = relationship(back_populates="versions")
    comments: Mapped[list["ApprovalComment"]] = relationship(
        back_populates="version", lazy="selectin"
    )
    decisions: Mapped[list["ApprovalDecision"]] = relationship(
        back_populates="version", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("asset_id", "version_number", name="uq_asset_version"),
        {"schema": "marketing_bot"},
    )


class MagicLink(Base):
    """Passwordless authentication token for client portal access."""

    __tablename__ = "magic_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.approval_assets.id"),
        nullable=False,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.clients.id"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    asset: Mapped["ApprovalAsset"] = relationship(back_populates="magic_links")
    client: Mapped["Client"] = relationship("Client", backref="magic_links")


class ApprovalComment(Base):
    """Client review comment on an asset or specific version."""

    __tablename__ = "approval_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.approval_assets.id"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.asset_versions.id"),
        nullable=True,
    )
    author_type: Mapped[str] = mapped_column(String(50), nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    asset: Mapped["ApprovalAsset"] = relationship(back_populates="comments")
    version: Mapped["AssetVersion | None"] = relationship(back_populates="comments")


class ApprovalDecision(Base):
    """Approval or rejection record for an asset version."""

    __tablename__ = "approval_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.approval_assets.id"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.asset_versions.id"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(255), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    asset: Mapped["ApprovalAsset"] = relationship(back_populates="decisions")
    version: Mapped["AssetVersion"] = relationship(back_populates="decisions")


class ApprovalEvent(Base):
    """Full audit log for all approval-related actions."""

    __tablename__ = "approval_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.approval_assets.id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    asset: Mapped["ApprovalAsset"] = relationship(back_populates="events")
