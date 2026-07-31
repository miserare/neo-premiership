"""Administrator authentication.

Covers the matrix required of the login system: successful login, failed login,
throttling, CSRF, session expiry, logout, revocation, credential rotation and
unauthorised mutation.
"""

from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.models.admin import AdminSession, AdminUser
from app.security.sessions import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, hash_token
from tests.conftest import (
    ADMIN_HEADERS,
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    TestingSessionLocal,
)

LOGIN = "/api/admin/login"


async def _login(client: AsyncClient, username: str, password: str):
    return await client.post(LOGIN, json={"username": username, "password": password})


# --------------------------------------------------------------- login


async def test_login_succeeds_and_sets_hardened_cookies(client: AsyncClient) -> None:
    response = await _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == ADMIN_USERNAME
    assert body["csrf_token"]

    cookies = {c.name: c for c in response.cookies.jar}
    assert SESSION_COOKIE_NAME in cookies

    raw = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in raw if c.startswith(f"{SESSION_COOKIE_NAME}="))
    # The session cookie must be unreadable from JavaScript and host-only.
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie.lower().replace("samesite=lax", "SameSite=lax")
    assert "Path=/" in session_cookie
    assert "Domain=" not in session_cookie

    csrf_cookie = next(c for c in raw if c.startswith("pp_csrf="))
    # The CSRF cookie is deliberately readable so the SPA can echo it back.
    assert "HttpOnly" not in csrf_cookie


async def test_login_never_returns_the_password_or_hash(client: AsyncClient) -> None:
    response = await _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    body = response.text
    assert ADMIN_PASSWORD not in body
    assert "password_hash" not in body
    assert "argon2" not in body


async def test_wrong_password_is_rejected(client: AsyncClient) -> None:
    response = await _login(client, ADMIN_USERNAME, "not-the-password")
    assert response.status_code == 401


async def test_unknown_user_and_wrong_password_are_indistinguishable(client: AsyncClient) -> None:
    """A differing message would confirm which usernames exist."""
    unknown = await _login(client, "nobody-here", "whatever-password")
    wrong = await _login(client, ADMIN_USERNAME, "not-the-password")

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


async def test_inactive_account_cannot_log_in(client: AsyncClient) -> None:
    async with TestingSessionLocal() as db:
        user = (
            await db.execute(select(AdminUser).where(AdminUser.username == ADMIN_USERNAME))
        ).scalar_one()
        user.is_active = False
        await db.commit()

    response = await _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert response.status_code == 401


# ------------------------------------------------------------ throttling


async def test_repeated_failures_are_throttled(client: AsyncClient) -> None:
    """After the failure budget is spent the endpoint returns 429, so an
    online guessing attack is bounded regardless of password strength."""
    statuses = []
    for _ in range(7):
        response = await _login(client, ADMIN_USERNAME, "wrong-password-here")
        statuses.append(response.status_code)

    assert 429 in statuses, statuses
    # And the correct password is refused too while the lockout stands, or the
    # throttle would be trivially bypassable.
    assert (await _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)).status_code == 429


async def test_successful_login_clears_the_failure_counter(client: AsyncClient) -> None:
    for _ in range(3):
        await _login(client, ADMIN_USERNAME, "wrong-password-here")

    assert (await _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)).status_code == 200

    # Budget reset, so a few more mistakes do not immediately lock the account.
    for _ in range(3):
        assert (await _login(client, ADMIN_USERNAME, "wrong-password-here")).status_code == 401


# ------------------------------------------------------------------ CSRF


async def test_mutation_requires_csrf_header(client: AsyncClient) -> None:
    """The session cookie alone must not authorise a write - that is exactly
    what a cross-site form post would carry."""
    cookie_only = {"Cookie": ADMIN_HEADERS["Cookie"]}

    response = await client.post(
        "/api/players", json={"username": "CsrfVictim"}, headers=cookie_only
    )

    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


async def test_mutation_rejects_a_wrong_csrf_token(client: AsyncClient) -> None:
    headers = dict(ADMIN_HEADERS)
    headers[CSRF_HEADER_NAME] = "not-the-right-token"

    response = await client.post("/api/players", json={"username": "CsrfVictim"}, headers=headers)
    assert response.status_code == 403


async def test_mutation_succeeds_with_session_and_csrf(client: AsyncClient) -> None:
    response = await client.post(
        "/api/players", json={"username": "LegitTrainer"}, headers=ADMIN_HEADERS
    )
    assert response.status_code == 201


async def test_safe_methods_do_not_require_csrf(client: AsyncClient) -> None:
    cookie_only = {"Cookie": ADMIN_HEADERS["Cookie"]}
    response = await client.get("/api/admin/session", headers=cookie_only)
    assert response.status_code == 200


# ------------------------------------------------------- session lifecycle


async def test_session_endpoint_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/admin/session")).status_code == 401


async def test_expired_session_is_rejected(client: AsyncClient) -> None:
    async with TestingSessionLocal() as db:
        session = (await db.execute(select(AdminSession))).unique().scalar_one()
        session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()

    assert (await client.get("/api/admin/session", headers=ADMIN_HEADERS)).status_code == 401


async def test_idle_session_is_rejected_and_revoked(client: AsyncClient) -> None:
    async with TestingSessionLocal() as db:
        session = (await db.execute(select(AdminSession))).unique().scalar_one()
        session.last_seen_at = datetime.now(timezone.utc) - timedelta(days=2)
        await db.commit()

    assert (await client.get("/api/admin/session", headers=ADMIN_HEADERS)).status_code == 401

    async with TestingSessionLocal() as db:
        session = (await db.execute(select(AdminSession))).unique().scalar_one()
        assert session.revoked_at is not None, "an idle session should be revoked, not just refused"


async def test_logout_revokes_the_session(client: AsyncClient) -> None:
    assert (await client.post("/api/admin/logout", headers=ADMIN_HEADERS)).status_code == 204
    # The same cookie must not work again.
    assert (await client.get("/api/admin/session", headers=ADMIN_HEADERS)).status_code == 401


async def test_logout_everywhere_revokes_other_sessions(client: AsyncClient) -> None:
    second = await _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    second_token = second.cookies.get(SESSION_COOKIE_NAME)
    second_headers = {
        "Cookie": f"{SESSION_COOKIE_NAME}={second_token}",
        CSRF_HEADER_NAME: second.json()["csrf_token"],
    }
    assert (await client.get("/api/admin/session", headers=second_headers)).status_code == 200

    assert (
        await client.post("/api/admin/logout-everywhere", headers=ADMIN_HEADERS)
    ).status_code == 204

    assert (await client.get("/api/admin/session", headers=second_headers)).status_code == 401
    assert (await client.get("/api/admin/session", headers=ADMIN_HEADERS)).status_code == 401


async def test_the_cookie_value_is_not_stored_in_the_database(client: AsyncClient) -> None:
    """Only a hash is persisted, so a database dump yields no usable cookies."""
    raw_token = ADMIN_HEADERS["Cookie"].split("=", 1)[1]

    async with TestingSessionLocal() as db:
        session = (await db.execute(select(AdminSession))).unique().scalar_one()
        assert session.token_hash != raw_token
        assert session.token_hash == hash_token(raw_token)


# --------------------------------------------------- credential rotation


async def test_password_change_requires_the_current_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/admin/password",
        json={"current_password": "wrong", "new_password": "a-much-longer-new-password"},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 401


async def test_password_change_rejects_a_weak_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/admin/password",
        json={"current_password": ADMIN_PASSWORD, "new_password": "short"},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422


async def test_password_change_rotates_and_revokes_sessions(client: AsyncClient) -> None:
    new_password = "an-entirely-new-long-password"

    response = await client.post(
        "/api/admin/password",
        json={"current_password": ADMIN_PASSWORD, "new_password": new_password},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 204

    # A cookie issued under the old password must not survive the rotation.
    assert (await client.get("/api/admin/session", headers=ADMIN_HEADERS)).status_code == 401
    assert (await _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)).status_code == 401
    assert (await _login(client, ADMIN_USERNAME, new_password)).status_code == 200


# ------------------------------------------------- unauthorised mutations


async def test_anonymous_cannot_mutate(client: AsyncClient) -> None:
    for method, path, body in (
        ("post", "/api/players", {"username": "AnonTrainer"}),
        ("post", "/api/seasons", {"name": "Anon Season", "start_date": "2026-01-01"}),
        ("put", "/api/site-links", {"stream_url": "https://example.com"}),
    ):
        response = await getattr(client, method)(path, json=body)
        assert response.status_code == 401, f"{method.upper()} {path} was not rejected"


async def test_legacy_admin_token_is_disabled_by_default(client: AsyncClient) -> None:
    """The old shared header must no longer authorise anything."""
    response = await client.post(
        "/api/players",
        json={"username": "LegacyTrainer"},
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 401


async def test_no_admin_credential_is_exposed_to_anonymous_callers(client: AsyncClient) -> None:
    transport = ASGITransport(app=client._transport.app)  # type: ignore[attr-defined]
    async with AsyncClient(transport=transport, base_url="http://test") as anon:
        home = await anon.get("/api/home")
    assert home.status_code == 200
    assert "csrf" not in home.text.lower()
    assert "token" not in home.text.lower()
