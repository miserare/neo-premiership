import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import client_ip, current_admin_session
from app.config import settings
from app.database import get_db
from app.models.admin import AdminSession, AdminUser
from app.security import sessions as session_store
from app.security import throttle
from app.security.passwords import (
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# One message for every failure mode. Distinguishing "no such user" from "wrong
# password" from "locked" hands an attacker a username oracle.
LOGIN_FAILED_DETAIL = "Invalid username or password"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class SessionInfo(BaseModel):
    username: str
    expires_at: str
    csrf_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=1, max_length=256)


def _set_session_cookies(response: Response, token: str, csrf_token: str) -> None:
    max_age = settings.session_ttl_hours * 3600
    response.set_cookie(
        session_store.SESSION_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,          # unreadable from JavaScript, so XSS cannot exfiltrate it
        secure=settings.cookies_secure,
        samesite="lax",         # blocks the common cross-site POST while keeping normal navigation
        path="/",               # no Domain attribute: host-only, not shared with subdomains
    )
    response.set_cookie(
        session_store.CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        httponly=False,         # deliberately readable: the SPA echoes it in a header
        secure=settings.cookies_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    for name in (session_store.SESSION_COOKIE_NAME, session_store.CSRF_COOKIE_NAME):
        response.delete_cookie(name, path="/")


@router.post("/login", response_model=SessionInfo)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SessionInfo:
    username = payload.username.strip().lower()
    ip = client_ip(request)

    if await throttle.is_login_locked(db, username=username, ip_address=ip):
        # 429 rather than 401 so a legitimate admin understands why waiting helps.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
        )

    result = await db.execute(select(AdminUser).where(AdminUser.username == username))
    user = result.scalar_one_or_none()

    # verify_password runs a real Argon2 verification even when user is None,
    # so a missing account costs the same time as a wrong password.
    stored_hash = user.password_hash if user is not None else None
    password_ok = verify_password(stored_hash, payload.password)

    if user is None or not user.is_active or not password_ok:
        await throttle.record_login_attempt(db, username=username, ip_address=ip, successful=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILED_DETAIL)

    # Opportunistically upgrade a hash written with weaker parameters.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        await db.commit()

    await throttle.record_login_attempt(db, username=username, ip_address=ip, successful=True)
    await throttle.clear_login_attempts(db, username=username)

    token, session = await session_store.create_session(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=ip,
    )
    _set_session_cookies(response, token, session.csrf_token)

    return SessionInfo(
        username=user.username,
        expires_at=session.expires_at.isoformat(),
        csrf_token=session.csrf_token,
    )


@router.get("/session", response_model=SessionInfo)
async def read_session(session: AdminSession = Depends(current_admin_session)) -> SessionInfo:
    """Who am I? Used by the SPA on load to decide whether to show the admin UI."""
    return SessionInfo(
        username=session.admin_user.username,
        expires_at=session.expires_at.isoformat(),
        csrf_token=session.csrf_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: AdminSession = Depends(current_admin_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    await session_store.revoke_session(db, session)
    _clear_session_cookies(response)


@router.post("/logout-everywhere", status_code=status.HTTP_204_NO_CONTENT)
async def logout_everywhere(
    response: Response,
    session: AdminSession = Depends(current_admin_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke every session for this administrator - the recovery action if a
    device is lost or a cookie is suspected stolen."""
    await session_store.revoke_all_for_user(db, session.admin_user_id)
    _clear_session_cookies(response)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    response: Response,
    session: AdminSession = Depends(current_admin_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    user = session.admin_user
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILED_DETAIL)

    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    from datetime import datetime, timezone

    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    await db.commit()

    # Rotating the credential invalidates every existing session, including
    # this one, so a stolen cookie does not outlive the password it came from.
    await session_store.revoke_all_for_user(db, user.id)
    _clear_session_cookies(response)


class AdminSessionSummary(BaseModel):
    id: uuid.UUID
    created_at: str
    last_seen_at: str
    expires_at: str
    ip_address: str | None
    user_agent: str | None
    current: bool


@router.get("/sessions", response_model=list[AdminSessionSummary])
async def list_sessions(
    session: AdminSession = Depends(current_admin_session),
    db: AsyncSession = Depends(get_db),
) -> list[AdminSessionSummary]:
    result = await db.execute(
        select(AdminSession)
        .where(
            AdminSession.admin_user_id == session.admin_user_id,
            AdminSession.revoked_at.is_(None),
        )
        .order_by(AdminSession.last_seen_at.desc())
    )
    return [
        AdminSessionSummary(
            id=row.id,
            created_at=row.created_at.isoformat(),
            last_seen_at=row.last_seen_at.isoformat(),
            expires_at=row.expires_at.isoformat(),
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            current=row.id == session.id,
        )
        for row in result.unique().scalars().all()
    ]
