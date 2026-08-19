"""Nudge notification types and per-user mute preferences."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

NEW_NOTIFICATION_TYPES = (
    "CHECKIN_DUE",
    "STREAK_AT_RISK",
    "MEMBER_QUIET",
    "PACE_BEHIND",
)


def upgrade() -> None:
    for value in NEW_NOTIFICATION_TYPES:
        op.execute(sa.text(f"ALTER TYPE notificationtype ADD VALUE '{value}'"))
    op.add_column(
        "users",
        sa.Column(
            "muted_notification_types",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "muted_notification_types")
    # PostgreSQL cannot drop a single enum value without recreating the type.
