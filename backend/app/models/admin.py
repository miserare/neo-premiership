import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.db_types import GUID


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminUser(Base):
    """An administrator who can sign in to the admin area.

    Only an Argon2 hash is stored - the password itself never reaches the
    database, the logs, or any response body.
    """

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # Argon2id encoded hash, ~97 chars today; sized for parameter growth.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sa_true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    sessions: Mapped[list["AdminSession"]] = relationship(
        "AdminSession", back_populates="admin_user", cascade="all, delete-orphan", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<AdminUser username={self.username!r}>"


class AdminSession(Base):
    """An opaque server-side session.

    The browser only ever receives a random token; the database stores its
    SHA-256 hash, so a database disclosure does not yield usable session
    cookies. Sessions carry their own CSRF secret.
    """

    __tablename__ = "admin_sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    # SHA-256 hex of the cookie value. Never the token itself.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Coarse audit context. Deliberately not a full request log.
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    admin_user: Mapped["AdminUser"] = relationship("AdminUser", back_populates="sessions", lazy="joined")

    def __repr__(self) -> str:
        return f"<AdminSession user_id={self.admin_user_id} expires={self.expires_at}>"


class LoginAttempt(Base):
    """Login attempt ledger backing brute-force throttling.

    Stored in the database rather than process memory so a restart cannot clear
    a lockout, and so throttling still works if the API is ever run with more
    than one worker.
    """

    __tablename__ = "admin_login_attempts"
    __table_args__ = (Index("ix_admin_login_attempts_ip_time", "ip_address", "attempted_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    # Lower-cased username as submitted; never a password.
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    successful: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<LoginAttempt username={self.username!r} ok={self.successful}>"
