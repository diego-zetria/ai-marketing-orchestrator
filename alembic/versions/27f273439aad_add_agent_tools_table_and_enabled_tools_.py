"""add agent_tools table and enabled_tools column

Revision ID: 27f273439aad
Revises: f5b20919fdc5
Create Date: 2026-02-22 18:16:54.374456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '27f273439aad'
down_revision: Union[str, Sequence[str], None] = 'f5b20919fdc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_tools table and add enabled_tools column to agent_configs."""
    op.create_table('agent_tools',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tool_key', sa.String(length=100), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('is_global', sa.Boolean(), nullable=False),
    sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tool_key'),
    schema='marketing_bot'
    )
    op.add_column('agent_configs',
        sa.Column('enabled_tools', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        schema='marketing_bot'
    )


def downgrade() -> None:
    """Drop enabled_tools column from agent_configs and drop agent_tools table."""
    op.drop_column('agent_configs', 'enabled_tools', schema='marketing_bot')
    op.drop_table('agent_tools', schema='marketing_bot')
