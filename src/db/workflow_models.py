"""Workflow, Automation Rule and Telegram Topic models.

These models power the dynamic rules engine, replacing hardcoded YAML
config with database-driven workflows and automation rules editable
via the backoffice admin.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models import Base


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    statuses: Mapped[list] = mapped_column(JSONB, nullable=False)
    transitions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    transition_actions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    intent_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    patterns: Mapped[list] = mapped_column(JSONB, nullable=False)
    allowed_roles: Mapped[list] = mapped_column(JSONB, nullable=False)
    valid_from_statuses: Mapped[list] = mapped_column(JSONB, nullable=False)
    target_status: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="confirm")
    special_action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TelegramTopic(Base):
    __tablename__ = "telegram_topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketing_bot.clients.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
