"""Brute-force throttling for login, and a coarse limiter for admin mutations.

Login attempts are recorded in PostgreSQL so a container restart cannot clear a
lockout. Mutation limiting is in-process, which is sufficient for the
single-backend-container deployment this project ships; if the API is ever
scaled horizontally, that limiter must move to shared storage.
"""

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.admin import LoginAttempt


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def record_login_attempt(
    db: AsyncSession, *, username: str, ip_address: str, successful: bool
) -> None:
    db.add(
        LoginAttempt(
            username=username.lower()[:64],
            ip_address=ip_address[:45],
            successful=successful,
        )
    )
    await db.commit()


async def is_login_locked(db: AsyncSession, *, username: str, ip_address: str) -> bool:
    """Locked when either the account or the source IP has exceeded the failure
    budget inside the window.

    Counting both means one attacker cannot spread guesses across many accounts
    from a single host, and a distributed attack still cannot lock a legitimate
    admin out permanently - the window is short.
    """
    window_start = _utcnow() - timedelta(minutes=settings.login_lockout_minutes)

    stmt = select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.attempted_at >= window_start,
        LoginAttempt.successful.is_(False),
        LoginAttempt.username == username.lower()[:64],
    )
    by_username = (await db.execute(stmt)).scalar_one()
    if by_username >= settings.login_max_attempts:
        return True

    stmt = select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.attempted_at >= window_start,
        LoginAttempt.successful.is_(False),
        LoginAttempt.ip_address == ip_address[:45],
    )
    by_ip = (await db.execute(stmt)).scalar_one()
    return by_ip >= settings.login_ip_max_attempts


async def clear_login_attempts(db: AsyncSession, *, username: str) -> None:
    """Called after a successful login so a legitimate admin who mistyped a few
    times is not still near the limit."""
    await db.execute(delete(LoginAttempt).where(LoginAttempt.username == username.lower()[:64]))
    await db.commit()


async def purge_old_attempts(db: AsyncSession) -> int:
    cutoff = _utcnow() - timedelta(days=7)
    result = await db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < cutoff))
    await db.commit()
    return result.rowcount or 0


class SlidingWindowLimiter:
    """Fixed-budget-per-window limiter keyed by an arbitrary string.

    In-process and therefore per-container. Used only to blunt runaway admin
    mutation loops; the security-critical login path uses the database above.
    """

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self._max = max_events
        self._window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        events = self._events[key]
        while events and now - events[0] > self._window:
            events.popleft()
        if len(events) >= self._max:
            return False
        events.append(now)
        return True

    def reset(self) -> None:
        self._events.clear()


mutation_limiter = SlidingWindowLimiter(max_events=120, window_seconds=60.0)
