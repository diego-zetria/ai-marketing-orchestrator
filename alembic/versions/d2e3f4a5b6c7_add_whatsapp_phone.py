"""add whatsapp_phone to clients

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
Create Date: 2026-02-23 18:00:00.000000

Adds optional whatsapp_phone column (E.164 format, max 20 chars) to the clients
table for WhatsApp Business Cloud API notifications.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "marketing_bot"


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("whatsapp_phone", sa.String(20), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("clients", "whatsapp_phone", schema=SCHEMA)
