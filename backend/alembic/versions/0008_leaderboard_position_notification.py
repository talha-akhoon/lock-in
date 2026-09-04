"""Notify a member when their dashboard rank number changes."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE notificationtype ADD VALUE 'LEADERBOARD_POSITION'"))


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value without recreating the type.
    pass
