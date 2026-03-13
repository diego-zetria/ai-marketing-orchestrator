"""add workflow_definitions, automation_rules, telegram_topics tables

Revision ID: g5b6c7d8e9f0
Revises: e3f4a5b6c7d8
Create Date: 2026-02-23 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'g5b6c7d8e9f0'
down_revision: Union[str, Sequence[str], None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "marketing_bot"


def upgrade() -> None:
    # -- workflow_definitions --
    op.create_table(
        "workflow_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("statuses", postgresql.JSONB, nullable=False),
        sa.Column(
            "transitions",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "transition_actions",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_default", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    # -- automation_rules --
    op.create_table(
        "automation_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("intent_type", sa.String(50), nullable=False),
        sa.Column("patterns", postgresql.JSONB, nullable=False),
        sa.Column("allowed_roles", postgresql.JSONB, nullable=False),
        sa.Column("valid_from_statuses", postgresql.JSONB, nullable=False),
        sa.Column("target_status", sa.String(50), nullable=False, server_default=""),
        sa.Column("mode", sa.String(20), nullable=False, server_default="confirm"),
        sa.Column("special_action", sa.String(100), nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("100")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_automation_rules_intent_type",
        "automation_rules",
        ["intent_type"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_automation_rules_priority",
        "automation_rules",
        ["priority"],
        schema=SCHEMA,
    )

    # -- telegram_topics --
    op.create_table(
        "telegram_topics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("topic_id", sa.BigInteger, nullable=False),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.clients.id"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_telegram_topics_client_id",
        "telegram_topics",
        ["client_id"],
        schema=SCHEMA,
    )

    # -- Add workflow_id FK to clients --
    op.add_column(
        "clients",
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.workflow_definitions.id"),
            nullable=True,
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("clients", "workflow_id", schema=SCHEMA)
    op.drop_index("ix_telegram_topics_client_id", table_name="telegram_topics", schema=SCHEMA)
    op.drop_table("telegram_topics", schema=SCHEMA)
    op.drop_index("ix_automation_rules_priority", table_name="automation_rules", schema=SCHEMA)
    op.drop_index("ix_automation_rules_intent_type", table_name="automation_rules", schema=SCHEMA)
    op.drop_table("automation_rules", schema=SCHEMA)
    op.drop_table("workflow_definitions", schema=SCHEMA)
