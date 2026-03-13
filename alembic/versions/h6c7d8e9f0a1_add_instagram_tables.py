"""add instagram analytics tables

Revision ID: h6c7d8e9f0a1
Revises: 3b9ed9b5f543
Create Date: 2026-02-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "3b9ed9b5f543"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "marketing_bot"


def upgrade() -> None:
    # instagram_accounts: OAuth tokens per client
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.instagram_accounts (
            id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
            client_name VARCHAR(100) NOT NULL UNIQUE,
            ig_user_id VARCHAR(50) NOT NULL,
            ig_username VARCHAR(100),
            access_token TEXT NOT NULL,
            token_expires_at TIMESTAMPTZ NOT NULL,
            page_id VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """)

    # media_insights: per-post Instagram metrics
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.media_insights (
            id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
            ig_media_id VARCHAR(50) NOT NULL UNIQUE,
            client_name VARCHAR(100) NOT NULL,
            media_type VARCHAR(20) NOT NULL,
            caption TEXT,
            permalink VARCHAR(500),
            published_at TIMESTAMPTZ NOT NULL,
            clickup_task_id VARCHAR(20),
            reach INT DEFAULT 0,
            views INT DEFAULT 0,
            likes INT DEFAULT 0,
            comments INT DEFAULT 0,
            saves INT DEFAULT 0,
            shares INT DEFAULT 0,
            total_interactions INT DEFAULT 0,
            avg_watch_time_s FLOAT,
            synced_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """)
    op.execute(f"""
        CREATE INDEX IF NOT EXISTS ix_media_insights_client_name
        ON {SCHEMA}.media_insights (client_name)
    """)
    op.execute(f"""
        CREATE INDEX IF NOT EXISTS ix_media_insights_published_at
        ON {SCHEMA}.media_insights (published_at)
    """)

    # account_insights: daily account-level metrics
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.account_insights (
            id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
            client_name VARCHAR(100) NOT NULL,
            date DATE NOT NULL,
            reach INT DEFAULT 0,
            views INT DEFAULT 0,
            follower_count INT DEFAULT 0,
            synced_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            UNIQUE (client_name, date)
        )
    """)


def downgrade() -> None:
    op.drop_index("ix_media_insights_published_at", table_name="media_insights", schema=SCHEMA)
    op.drop_index("ix_media_insights_client_name", table_name="media_insights", schema=SCHEMA)
    op.drop_table("account_insights", schema=SCHEMA)
    op.drop_table("media_insights", schema=SCHEMA)
    op.drop_table("instagram_accounts", schema=SCHEMA)
