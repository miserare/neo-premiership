"""Opaque server-side admin sessions.

The cookie carries a random 256-bit token and nothing else - no user id, no
claims, no signature to strip. Authority lives entirely in the database row, so
revocation is immediate and a leaked database dump yields only hashes.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.admin import AdminSession, AdminUser

SESSION_COOKIE_NAME = "pp_session"
CSRF_COOKIE_NAME = "pp_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo; normalise before comparing."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def hash_token(token: str) -> str:
    """SHA-256 is correct here, unlike for passwords: the token already has
    256 bits of entropy, so there is nothing to brute force and we want the
    lookup to be fast."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(
    db: AsyncSession,
    admin_user: AdminUser,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, AdminSession]:
    """Returns (raw token for the cookie, stored session). The raw token is
    never persisted and cannot be recovered from the database."""
    token = secrets.token_urlsafe(32)
    session = AdminSession(
        token_hash=hash_token(token),
        csrf_token=secrets.token_urlsafe(32),
        admin_user_id=admin_user.id,
        expires_at=_utcnow() + timedelta(hours=settings.session_ttl_hours),
        user_agent=(user_agent or "")[:200] or None,
        ip_address=(ip_address or "")[:45] or None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return token, session


async def get_valid_session(db: AsyncSession, token: str | None) -> AdminSession | None:
    """Resolve a cookie token to a live session, enforcing revocation, absolute
    expiry and idle timeout. Touches last_seen_at so an active admin is not
    logged out mid-session."""
    if not token:
        return None

    result = await db.execute(
        select(AdminSession).where(AdminSession.token_hash == hash_token(token))
    )
    session = result.unique().scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        return None

    now = _utcnow()
    if _as_utc(session.expires_at) <= now:
        return None

    idle_limit = timedelta(minutes=settings.session_idle_timeout_minutes)
    if now - _as_utc(session.last_seen_at) > idle_limit:
        # Idle sessions are revoked rather than merely rejected, so an
        # abandoned cookie cannot be resurrected.
        session.revoked_at = now
        await db.commit()
        return None

    if not session.admin_user.is_active:
        return None

    session.last_seen_at = now
    await db.commit()
    return session


async def revoke_session(db: AsyncSession, session: AdminSession) -> None:
    session.revoked_at = _utcnow()
    await db.commit()


async def revoke_all_for_user(db: AsyncSession, admin_user_id: uuid.UUID) -> int:
    """Used on password change and for 'sign out everywhere'."""
    result = await db.execute(
        update(AdminSession)
        .where(AdminSession.admin_user_id == admin_user_id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=_utcnow())
    )
    await db.commit()
    return result.rowcount or 0


async def purge_expired(db: AsyncSession) -> int:
    """Housekeeping so the table does not grow without bound."""
    from sqlalchemy import delete

    cutoff = _utcnow() - timedelta(days=30)
    result = await db.execute(delete(AdminSession).where(AdminSession.expires_at < cutoff))
    await db.commit()
    return result.rowcount or 0
