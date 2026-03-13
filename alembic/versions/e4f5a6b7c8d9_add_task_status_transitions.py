"""add task_status_transitions table

Revision ID: e4f5a6b7c8d9
Revises: e3f4a5b6c7d8
Create Date: 2026-02-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "marketing_bot"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.task_status_transitions (
            id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
            task_id VARCHAR(20) NOT NULL,
            task_name VARCHAR(500),
            list_id VARCHAR(20),
            client_name VARCHAR(100),
            from_status VARCHAR(50) NOT NULL,
            to_status VARCHAR(50) NOT NULL,
            changed_by_id VARCHAR(20),
            changed_by_name VARCHAR(255),
            transitioned_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """)
    op.execute(f"""
        CREATE INDEX IF NOT EXISTS ix_task_transitions_task_id
        ON {SCHEMA}.task_status_transitions (task_id)
    """)
    op.execute(f"""
        CREATE INDEX IF NOT EXISTS ix_task_transitions_transitioned_at
        ON {SCHEMA}.task_status_transitions (transitioned_at)
    """)


def downgrade() -> None:
    op.drop_index(
        "ix_task_transitions_transitioned_at",
        table_name="task_status_transitions",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_task_transitions_task_id",
        table_name="task_status_transitions",
        schema=SCHEMA,
    )
    op.drop_table("task_status_transitions", schema=SCHEMA)
