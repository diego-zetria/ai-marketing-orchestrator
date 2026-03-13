"""add knowledge_documents table

Revision ID: a3c7e1d5f920
Revises: 27f273439aad
Create Date: 2026-02-22 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a3c7e1d5f920'
down_revision: Union[str, Sequence[str], None] = '27f273439aad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create knowledge_documents table."""
    op.create_table('knowledge_documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('file_key', sa.String(length=500), nullable=True),
        sa.Column('file_name', sa.String(length=500), nullable=True),
        sa.Column('file_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('agent_access', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='marketing_bot'
    )


def downgrade() -> None:
    """Drop knowledge_documents table."""
    op.drop_table('knowledge_documents', schema='marketing_bot')
