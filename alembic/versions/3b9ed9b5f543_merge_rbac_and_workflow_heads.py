"""merge rbac and workflow heads

Revision ID: 3b9ed9b5f543
Revises: a1b2c3d4e5f6, g5b6c7d8e9f0
Create Date: 2026-02-23 23:15:28.356044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b9ed9b5f543'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'g5b6c7d8e9f0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
