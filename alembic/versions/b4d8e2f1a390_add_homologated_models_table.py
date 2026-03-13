"""add homologated_models table

Revision ID: b4d8e2f1a390
Revises: a3c7e1d5f920
Create Date: 2026-02-22 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b4d8e2f1a390'
down_revision: Union[str, Sequence[str], None] = 'a3c7e1d5f920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('homologated_models',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('description_pt', sa.Text(), nullable=False),
        sa.Column('tier', sa.String(length=20), nullable=False),
        sa.Column('quality_stars', sa.SmallInteger(), nullable=False, server_default='3'),
        sa.Column('speed_rating', sa.String(length=20), nullable=False),
        sa.Column('cost_rating', sa.String(length=20), nullable=False),
        sa.Column('best_for', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('context_length', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prompt_price_per_m', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('completion_price_per_m', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('supports_images', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('supports_tools', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('supports_audio', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('supports_video', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('input_modalities', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='["text"]'),
        sa.Column('recommended_agents', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_recommended', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('openrouter_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_id'),
        schema='marketing_bot'
    )
    op.create_index('idx_homologated_models_tier', 'homologated_models', ['tier'], schema='marketing_bot')
    op.create_index('idx_homologated_models_active', 'homologated_models', ['is_active'], schema='marketing_bot')


def downgrade() -> None:
    op.drop_index('idx_homologated_models_active', table_name='homologated_models', schema='marketing_bot')
    op.drop_index('idx_homologated_models_tier', table_name='homologated_models', schema='marketing_bot')
    op.drop_table('homologated_models', schema='marketing_bot')
