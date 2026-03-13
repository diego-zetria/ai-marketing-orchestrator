import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    __table_args__ = {"schema": "marketing_bot"}


class BriefingLog(Base):
    __tablename__ = "briefing_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw_briefing: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tasks_created: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    clickup_user_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, default=0)
    skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
