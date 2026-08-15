"""Enforce one active team per user and one open challenge per team.

Both invariants are also guarded in the service layer; these indexes exist so a
race between two concurrent requests cannot produce a state the app cannot
represent (get_membership and get_participant both assume a single row).
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ONE_ACTIVE_TEAM = "uq_team_members_one_active_team"
ONE_OPEN_CHALLENGE = "uq_challenges_one_open_per_team"


def upgrade() -> None:
    op.create_index(
        ONE_ACTIVE_TEAM,
        "team_members",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        ONE_OPEN_CHALLENGE,
        "challenges",
        ["team_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('DRAFT', 'UPCOMING', 'ACTIVE')"),
    )


def downgrade() -> None:
    op.drop_index(ONE_OPEN_CHALLENGE, table_name="challenges")
    op.drop_index(ONE_ACTIVE_TEAM, table_name="team_members")
