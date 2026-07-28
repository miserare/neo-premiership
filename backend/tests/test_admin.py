import pytest
from httpx import AsyncClient

from app.config import settings
from tests.conftest import ADMIN_TOKEN, ADMIN_HEADERS


async def test_verify_session_accepts_valid_token(client: AsyncClient) -> None:
    response = await client.get("/api/admin/session", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_verify_session_rejects_wrong_token(client: AsyncClient) -> None:
    response = await client.get("/api/admin/session", headers={"X-Admin-Token": "not-the-token"})

    assert response.status_code == 401


async def test_verify_session_rejects_missing_token(client: AsyncClient) -> None:
    response = await client.get("/api/admin/session")

    assert response.status_code == 401


@pytest.fixture
def unconfigured_admin_token():
    """Temporarily unset the server's admin token to exercise the fail-closed path."""
    settings.admin_token = None
    yield
    settings.admin_token = ADMIN_TOKEN


async def test_verify_session_reports_unconfigured_server(
    client: AsyncClient, unconfigured_admin_token: None
) -> None:
    """503, not 401 - the admin UI shows a different fix for each ("set
    ADMIN_TOKEN on the server" vs "check the token you typed")."""
    response = await client.get("/api/admin/session", headers=ADMIN_HEADERS)

    assert response.status_code == 503
