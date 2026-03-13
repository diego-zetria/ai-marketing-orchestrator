"""add RBAC tables (admin_roles, admin_users)

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-02-23

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "marketing_bot"


def upgrade() -> None:
    # -- admin_roles --
    op.create_table(
        "admin_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("permissions", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    # -- admin_users --
    op.create_table(
        "admin_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role_id",
            UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.admin_roles.id"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
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

    # -- Seed default roles --
    op.execute(f"""
        INSERT INTO {SCHEMA}.admin_roles (id, name, description, permissions) VALUES
        (
            'a0000000-0000-0000-0000-000000000001',
            'admin',
            'Administrador com acesso total',
            '{{"dashboard":["read"],"clients":["read","create","update","delete"],"approvals":["read","create","update","delete"],"team":["read","create","update","delete"],"rules":["read","create","update","delete"],"brands":["read","create","update","delete"],"agents":["read","create","update","delete"],"tools":["read","create","update","delete"],"knowledge":["read","create","update","delete"],"models":["read","create","update","delete"],"system":["read","update"],"users":["read","create","update","delete"],"media":["read","delete"],"webhooks":["read","create","update","delete"],"notifications":["read","update","delete"],"activity":["read"],"workflows":["read","create","update","delete"],"automations":["read","create","update","delete"]}}'
        ),
        (
            'a0000000-0000-0000-0000-000000000002',
            'manager',
            'Gerente com acesso a gestao de clientes e conteudo',
            '{{"dashboard":["read"],"clients":["read","create","update"],"approvals":["read","create","update"],"team":["read"],"rules":["read","update"],"brands":["read","update"],"agents":["read"],"tools":["read"],"knowledge":["read","update"],"models":["read"],"system":["read"],"users":[],"media":["read"],"webhooks":["read"],"notifications":["read","update"],"activity":["read"],"workflows":["read"],"automations":["read"]}}'
        ),
        (
            'a0000000-0000-0000-0000-000000000003',
            'viewer',
            'Visualizador com acesso somente leitura',
            '{{"dashboard":["read"],"clients":["read"],"approvals":["read"],"team":["read"],"rules":["read"],"brands":["read"],"agents":["read"],"tools":["read"],"knowledge":["read"],"models":["read"],"system":["read"],"users":[],"media":["read"],"webhooks":["read"],"notifications":["read"],"activity":["read"],"workflows":["read"],"automations":["read"]}}'
        )
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("admin_users", schema=SCHEMA)
    op.drop_table("admin_roles", schema=SCHEMA)
