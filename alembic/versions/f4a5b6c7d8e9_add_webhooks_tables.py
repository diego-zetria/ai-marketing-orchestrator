"""add webhooks tables

Revision ID: f4a5b6c7d8e9
Revises: e4f5a6b7c8d9
Create Date: 2026-02-23 23:00:00.000000

Adds webhooks and webhook_deliveries tables for the admin backoffice
webhook management system.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "marketing_bot"


def upgrade() -> None:
    # -- webhooks table --
    op.create_table(
        "webhooks",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("events", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("secret", sa.String(100), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_webhooks_is_active",
        "webhooks",
        ["is_active"],
        schema=SCHEMA,
    )

    # -- webhook_deliveries table --
    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "webhook_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.webhooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(100), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "success",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_webhook_deliveries_webhook_id",
        "webhook_deliveries",
        ["webhook_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_webhook_deliveries_created_at",
        "webhook_deliveries",
        ["created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_deliveries_created_at",
        table_name="webhook_deliveries",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_webhook_deliveries_webhook_id",
        table_name="webhook_deliveries",
        schema=SCHEMA,
    )
    op.drop_table("webhook_deliveries", schema=SCHEMA)
    op.drop_index("ix_webhooks_is_active", table_name="webhooks", schema=SCHEMA)
    op.drop_table("webhooks", schema=SCHEMA)
