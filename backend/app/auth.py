"""Administrator authentication.

Authority comes from an opaque server-side session identified by an HttpOnly
cookie. The previous shared X-Admin-Token is retained only as an explicitly
enabled migration path (see settings.legacy_admin_token_enabled) and is off by
default in production.
"""

import secrets

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.admin import AdminSession
from app.security import sessions as session_store
from app.security.csrf import require_csrf
from app.security.throttle import mutation_limiter


def client_ip(request: Request) -> str:
    """The caller's address.

    Only consults X-Forwarded-For when the app is configured to sit behind a
    trusted proxy, otherwise any client could spoof its way around IP
    throttling by setting the header itself.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Left-most entry is the original client; the rest are proxies.
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _session_from_request(request: Request, db: AsyncSession) -> AdminSession | None:
    token = request.cookies.get(session_store.SESSION_COOKIE_NAME)
    return await session_store.get_valid_session(db, token)


async def current_admin_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_admin_token: str | None = Header(default=None),
) -> AdminSession:
    """Require an authenticated administrator.

    Raises 401 with a deliberately vague message: distinguishing "no session"
    from "expired" from "revoked" tells an attacker more than it helps a user,
    who simply needs to sign in again.
    """
    session = await _session_from_request(request, db)

    if session is None and settings.legacy_admin_token_enabled:
        # Transitional only. Guarded by an explicit setting so it cannot be the
        # accidental production state, and it still enforces rate limiting.
        expected = settings.admin_token
        if expected and x_admin_token and secrets.compare_digest(x_admin_token, expected):
            if not mutation_limiter.allow(f"legacy:{client_ip(request)}"):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
                )
            return _LegacyTokenSession()  # type: ignore[return-value]

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Cookie"},
        )

    require_csrf(request, session)

    if not mutation_limiter.allow(f"session:{session.id}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )

    return session


class _LegacyTokenSession:
    """Stand-in so legacy-token callers satisfy the same dependency shape.

    Deliberately not an AdminSession: it has no database row, cannot be
    revoked, and exists only until the legacy path is switched off.
    """

    id = "legacy-token"
    csrf_token = ""

    @property
    def admin_user(self):  # pragma: no cover - trivial
        return None


# Backwards-compatible name used by existing routers as a dependency.
async def require_admin(session: AdminSession = Depends(current_admin_session)) -> AdminSession:
    return session


async def optional_admin_session(
    request: Request, db: AsyncSession = Depends(get_db)
) -> AdminSession | None:
    """For endpoints that reveal more to an administrator but still serve the
    public. Never raises, and never enforces CSRF - it gates reads only."""
    try:
        return await _session_from_request(request, db)
    except Exception:  # pragma: no cover - defensive; a bad cookie is not fatal
        return None
