"""Rename the faith-specific goal category to a generic religious one.

Existing rows keep their values; only the enum label changes.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE goalcategory RENAME VALUE 'ISLAMIC' TO 'RELIGIOUS'")


def downgrade() -> None:
    op.execute("ALTER TYPE goalcategory RENAME VALUE 'RELIGIOUS' TO 'ISLAMIC'")
