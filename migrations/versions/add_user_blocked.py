"""Add user blocked columns

Revision ID: add_user_blocked
Revises: add_user_role
Create Date: 2026-01-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_user_blocked"
down_revision: str | Sequence[str] | None = "add_user_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_blocked and blocked_reason columns to users table."""
    op.add_column(
        "users",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("blocked_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove blocked columns from users table."""
    op.drop_column("users", "blocked_reason")
    op.drop_column("users", "is_blocked")
