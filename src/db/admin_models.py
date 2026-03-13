import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    clickup_list_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    designer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_bot.team_members.id"), nullable=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_bot.team_members.id"), nullable=True
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_bot.workflow_definitions.id"), nullable=True
    )
    # Portal-specific columns (added by approval portal migration)
    slug: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    whatsapp_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AssignmentRule(Base):
    __tablename__ = "assignment_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    default_assignee_ids: Mapped[list] = mapped_column(JSONB, default=list)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class NotificationRule(Base):
    __tablename__ = "notification_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    notify_roles: Mapped[list] = mapped_column(JSONB, nullable=False)
    message_template: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[list] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled_tools: Mapped[list] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class BrandGuideline(Base):
    __tablename__ = "brand_guidelines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_bot.clients.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AgentTool(Base):
    __tablename__ = "agent_tools"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    is_global: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    agent_access: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class HomologatedModel(Base):
    __tablename__ = "homologated_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description_pt: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_stars: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    speed_rating: Mapped[str] = mapped_column(String(20), nullable=False)
    cost_rating: Mapped[str] = mapped_column(String(20), nullable=False)
    best_for: Mapped[list] = mapped_column(JSONB, default=list)
    context_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_price_per_m: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    completion_price_per_m: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    supports_images: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_video: Mapped[bool] = mapped_column(Boolean, default=False)
    input_modalities: Mapped[list] = mapped_column(JSONB, default=lambda: ["text"])
    recommended_agents: Mapped[list] = mapped_column(JSONB, default=list)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    openrouter_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __init__(self, **kwargs: object) -> None:
        defaults = {
            "quality_stars": 3,
            "context_length": 0,
            "supports_images": False,
            "supports_tools": False,
            "supports_audio": False,
            "supports_video": False,
            "is_recommended": False,
            "display_order": 100,
            "is_active": True,
        }
        for key, value in defaults.items():
            kwargs.setdefault(key, value)
        super().__init__(**kwargs)


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    user: Mapped[str] = mapped_column(String(100), default="admin")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # e.g. "approval", "client", "alert"
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    events: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    secret: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketing_bot.webhooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# RBAC Models
# ---------------------------------------------------------------------------


class AdminRole(Base):
    __tablename__ = "admin_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_bot.admin_roles.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
