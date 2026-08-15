"""OAuth clients and authorization codes for ChatGPT MCP connectors."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.String(255), primary_key=True),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("redirect_uris", sa.JSON(), nullable=False),
        sa.Column(
            "token_endpoint_auth_method",
            sa.String(64),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "oauth_auth_codes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("client_id", sa.String(512), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("redirect_uri", sa.String(2048), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("resource", sa.String(512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_oauth_auth_codes_client_id", "oauth_auth_codes", ["client_id"])
    op.create_index("ix_oauth_auth_codes_user_id", "oauth_auth_codes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_oauth_auth_codes_user_id", table_name="oauth_auth_codes")
    op.drop_index("ix_oauth_auth_codes_client_id", table_name="oauth_auth_codes")
    op.drop_table("oauth_auth_codes")
    op.drop_table("oauth_clients")
