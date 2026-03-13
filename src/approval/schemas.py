"""Pydantic v2 request/response schemas for the client approval portal API.

These schemas define the contract between the Next.js frontend and the
FastAPI/Lambda backend. All response schemas use `from_attributes = True`
so they can be constructed directly from SQLAlchemy ORM instances.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ApproveRequest(BaseModel):
    """Client approves the current asset version."""

    comment: str | None = None


class RequestChangesRequest(BaseModel):
    """Client requests changes on the current asset version."""

    comment: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed description of the changes needed",
    )


class AddCommentRequest(BaseModel):
    """Client adds a comment to the asset."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Comment text",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ClientResponse(BaseModel):
    """Serialized client info for the portal frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    logo_url: str | None


class VersionResponse(BaseModel):
    """Serialized asset version with media metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    file_type: str
    file_format: str
    media_url: str | None = None
    thumbnail_url: str | None = None
    file_size_bytes: int | None
    width: int | None
    height: int | None
    duration_seconds: float | None
    uploaded_by: str | None
    created_at: datetime


class CommentResponse(BaseModel):
    """Serialized approval comment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_type: str
    author_name: str
    content: str
    created_at: datetime


class DecisionResponse(BaseModel):
    """Serialized approval decision record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    decision: str
    comment: str | None
    decided_by: str
    decided_at: datetime


class AssetResponse(BaseModel):
    """Serialized approval asset (summary level)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status: str
    current_version: int
    created_at: datetime
    updated_at: datetime


class AssetDetailResponse(BaseModel):
    """Full asset detail with nested related entities."""

    model_config = ConfigDict(from_attributes=True)

    asset: AssetResponse
    client: ClientResponse
    current_version: VersionResponse | None
    versions: list[VersionResponse]
    comments: list[CommentResponse]
    decisions: list[DecisionResponse]


class AuthValidateResponse(BaseModel):
    """Response after successful magic-link validation."""

    model_config = ConfigDict(from_attributes=True)

    jwt: str
    asset: AssetDetailResponse


class DecisionResultResponse(BaseModel):
    """Response after recording an approval or change-request decision."""

    model_config = ConfigDict(from_attributes=True)

    decision: DecisionResponse
    asset: AssetResponse
