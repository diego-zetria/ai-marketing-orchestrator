"""add notifications table

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-02-23 22:00:00.000000

Adds in-app notifications table for the admin backoffice panel.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "marketing_bot"


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_notifications_is_read",
        "notifications",
        ["is_read"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_notifications_created_at",
        "notifications",
        ["created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_created_at", table_name="notifications", schema=SCHEMA)
    op.drop_index("ix_notifications_is_read", table_name="notifications", schema=SCHEMA)
    op.drop_table("notifications", schema=SCHEMA)
