"""add administrator accounts, sessions and login attempts

Replaces the shared X-Admin-Token with real accounts. No administrator is
created here: there is deliberately no default password to leak or forget.
Bootstrap the first account with `python -m app.cli create-admin --username admin`.

Revision ID: d92a4f6b1c07
Revises: c58b74e91a20
Create Date: 2026-07-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app


revision: str = "d92a4f6b1c07"
down_revision: Union[str, None] = "c58b74e91a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", app.utils.db_types.GUID(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        # Argon2id encoded hash. Never a plaintext or reversible value.
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_users_username"), "admin_users", ["username"], unique=True)

    op.create_table(
        "admin_sessions",
        sa.Column("id", app.utils.db_types.GUID(), nullable=False),
        # SHA-256 of the cookie value, so a database dump yields no usable cookies.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("admin_user_id", app.utils.db_types.GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=200), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_sessions_token_hash"), "admin_sessions", ["token_hash"], unique=True)
    op.create_index(
        op.f("ix_admin_sessions_admin_user_id"), "admin_sessions", ["admin_user_id"], unique=False
    )

    op.create_table(
        "admin_login_attempts",
        sa.Column("id", app.utils.db_types.GUID(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("successful", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_login_attempts_username"), "admin_login_attempts", ["username"], unique=False
    )
    op.create_index(
        op.f("ix_admin_login_attempts_attempted_at"),
        "admin_login_attempts",
        ["attempted_at"],
        unique=False,
    )
    # Supports the per-IP failure count inside the lockout window.
    op.create_index(
        "ix_admin_login_attempts_ip_time",
        "admin_login_attempts",
        ["ip_address", "attempted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_login_attempts_ip_time", table_name="admin_login_attempts")
    op.drop_index(op.f("ix_admin_login_attempts_attempted_at"), table_name="admin_login_attempts")
    op.drop_index(op.f("ix_admin_login_attempts_username"), table_name="admin_login_attempts")
    op.drop_table("admin_login_attempts")
    op.drop_index(op.f("ix_admin_sessions_admin_user_id"), table_name="admin_sessions")
    op.drop_index(op.f("ix_admin_sessions_token_hash"), table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_index(op.f("ix_admin_users_username"), table_name="admin_users")
    op.drop_table("admin_users")
