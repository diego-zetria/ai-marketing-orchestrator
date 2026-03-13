"""add approval portal tables

Revision ID: c1a2b3d4e5f6
Revises: b4d8e2f1a390
Create Date: 2026-02-23 10:00:00.000000

Adds 7 table structures for the client approval portal:
- clients: adds portal-specific columns (slug, email, logo_url) to existing table
- approval_assets: media assets pending client approval
- asset_versions: version history for each asset
- magic_links: passwordless authentication tokens
- approval_comments: client review comments
- approval_decisions: approval/rejection records
- approval_events: full audit log
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "b4d8e2f1a390"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "marketing_bot"


def upgrade() -> None:
    """Create approval portal tables and add portal columns to clients."""
    # --- 1. Add portal-specific columns to existing clients table ---
    op.add_column(
        "clients",
        sa.Column("slug", sa.String(length=100), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "clients",
        sa.Column("email", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "clients",
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        "uq_clients_slug",
        "clients",
        ["slug"],
        schema=SCHEMA,
    )

    # --- 2. approval_assets ---
    op.create_table(
        "approval_assets",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("clickup_task_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending_review"),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["client_id"],
            [f"{SCHEMA}.clients.id"],
            name="fk_approval_assets_client_id",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_approval_assets_client_id",
        "approval_assets",
        ["client_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_approval_assets_status",
        "approval_assets",
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_approval_assets_clickup_task_id",
        "approval_assets",
        ["clickup_task_id"],
        schema=SCHEMA,
    )

    # --- 3. asset_versions ---
    op.create_table(
        "asset_versions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("file_format", sa.String(length=20), nullable=False),
        sa.Column("original_url", sa.String(length=1000), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=1000), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("uploaded_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            [f"{SCHEMA}.approval_assets.id"],
            name="fk_asset_versions_asset_id",
        ),
        sa.UniqueConstraint("asset_id", "version_number", name="uq_asset_version"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_versions_asset_id",
        "asset_versions",
        ["asset_id"],
        schema=SCHEMA,
    )

    # --- 4. magic_links ---
    op.create_table(
        "magic_links",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            [f"{SCHEMA}.approval_assets.id"],
            name="fk_magic_links_asset_id",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            [f"{SCHEMA}.clients.id"],
            name="fk_magic_links_client_id",
        ),
        sa.UniqueConstraint("token", name="uq_magic_links_token"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_magic_links_token",
        "magic_links",
        ["token"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_magic_links_active_expires",
        "magic_links",
        ["is_active", "expires_at"],
        schema=SCHEMA,
    )

    # --- 5. approval_comments ---
    op.create_table(
        "approval_comments",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=True),
        sa.Column("author_type", sa.String(length=50), nullable=False),
        sa.Column("author_name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            [f"{SCHEMA}.approval_assets.id"],
            name="fk_approval_comments_asset_id",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            [f"{SCHEMA}.asset_versions.id"],
            name="fk_approval_comments_version_id",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_approval_comments_asset_id",
        "approval_comments",
        ["asset_id"],
        schema=SCHEMA,
    )

    # --- 6. approval_decisions ---
    op.create_table(
        "approval_decisions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(length=255), nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            [f"{SCHEMA}.approval_assets.id"],
            name="fk_approval_decisions_asset_id",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            [f"{SCHEMA}.asset_versions.id"],
            name="fk_approval_decisions_version_id",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_approval_decisions_asset_id",
        "approval_decisions",
        ["asset_id"],
        schema=SCHEMA,
    )

    # --- 7. approval_events ---
    op.create_table(
        "approval_events",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            [f"{SCHEMA}.approval_assets.id"],
            name="fk_approval_events_asset_id",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_approval_events_asset_id",
        "approval_events",
        ["asset_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_approval_events_event_type",
        "approval_events",
        ["event_type"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop approval portal tables in reverse dependency order, then remove client columns."""
    # Drop tables in reverse order (children before parents)
    op.drop_table("approval_events", schema=SCHEMA)
    op.drop_table("approval_decisions", schema=SCHEMA)
    op.drop_table("approval_comments", schema=SCHEMA)
    op.drop_table("magic_links", schema=SCHEMA)
    op.drop_table("asset_versions", schema=SCHEMA)
    op.drop_table("approval_assets", schema=SCHEMA)

    # Remove portal columns from clients
    op.drop_constraint("uq_clients_slug", "clients", schema=SCHEMA, type_="unique")
    op.drop_column("clients", "logo_url", schema=SCHEMA)
    op.drop_column("clients", "email", schema=SCHEMA)
    op.drop_column("clients", "slug", schema=SCHEMA)
