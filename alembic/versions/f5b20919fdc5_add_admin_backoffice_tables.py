"""add admin backoffice tables

Revision ID: f5b20919fdc5
Revises: 9a136b5d1856
Create Date: 2026-02-22 16:53:40.596449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5b20919fdc5'
down_revision: Union[str, Sequence[str], None] = '9a136b5d1856'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — create admin backoffice tables in marketing_bot schema."""
    op.create_table('activity_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=True),
    sa.Column('entity_id', sa.String(length=100), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('user', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='marketing_bot'
    )
    op.create_table('agent_configs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('agent_name', sa.String(length=100), nullable=False),
    sa.Column('model_id', sa.String(length=200), nullable=False),
    sa.Column('instructions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('agent_name'),
    schema='marketing_bot'
    )
    op.create_table('assignment_rules',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('service_type', sa.String(length=50), nullable=False),
    sa.Column('default_assignee_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('service_type'),
    schema='marketing_bot'
    )
    op.create_table('notification_rules',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('notify_roles', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('message_template', sa.String(length=500), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('status'),
    schema='marketing_bot'
    )
    op.create_table('system_config',
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key'),
    schema='marketing_bot'
    )
    # Add columns to existing team_members table (created in first migration)
    op.add_column('team_members', sa.Column('role', sa.String(length=50), nullable=True), schema='marketing_bot')
    op.add_column('team_members', sa.Column('telegram_chat_id', sa.BigInteger(), nullable=False, server_default='0'), schema='marketing_bot')
    op.add_column('team_members', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True), schema='marketing_bot')
    op.create_table('clients',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('clickup_list_id', sa.String(length=100), nullable=True),
    sa.Column('designer_id', sa.UUID(), nullable=True),
    sa.Column('account_id', sa.UUID(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['marketing_bot.team_members.id'], ),
    sa.ForeignKeyConstraint(['designer_id'], ['marketing_bot.team_members.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name'),
    schema='marketing_bot'
    )
    op.create_table('brand_guidelines',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['marketing_bot.clients.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='marketing_bot'
    )


def downgrade() -> None:
    """Downgrade schema — drop admin backoffice tables."""
    op.drop_table('brand_guidelines', schema='marketing_bot')
    op.drop_table('clients', schema='marketing_bot')
    op.drop_table('system_config', schema='marketing_bot')
    op.drop_table('notification_rules', schema='marketing_bot')
    op.drop_table('assignment_rules', schema='marketing_bot')
    op.drop_table('agent_configs', schema='marketing_bot')
    op.drop_table('activity_log', schema='marketing_bot')
