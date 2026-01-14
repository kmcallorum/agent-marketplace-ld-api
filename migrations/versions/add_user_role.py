"""Add user role column

Revision ID: add_user_role
Revises: 633ad2530216
Create Date: 2026-01-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_user_role"
down_revision: str | Sequence[str] | None = "633ad2530216"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add role column to users table."""
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
    )

    # Set kmcallorum as admin
    op.execute("UPDATE users SET role = 'admin' WHERE username = 'kmcallorum'")


def downgrade() -> None:
    """Remove role column from users table."""
    op.drop_column("users", "role")
