from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import logging

from app.database import Base, get_db
from app.main import app
from app.models.admin import AdminUser
from app.security.passwords import hash_password
from app.security.sessions import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, create_session
from app.security.throttle import mutation_limiter

# The test administrator. Password is only ever used to seed a hash; the tests
# authenticate with a real session, not by bypassing auth.
ADMIN_USERNAME = "testadmin"
ADMIN_PASSWORD = "correct-horse-battery-staple"

# Populated per test by the _admin_session fixture below. Mutated in place so
# `from tests.conftest import ADMIN_HEADERS` keeps working across modules.
#
# Carrying the session cookie in a Cookie header (rather than on the client)
# means every existing `headers=ADMIN_HEADERS` call site authenticates through
# the real session lookup and the real CSRF check.
ADMIN_HEADERS: dict[str, str] = {}

# A single shared in-memory SQLite connection (via StaticPool) so every
# session in a test sees the same tables - a plain in-memory DB is otherwise
# torn down as soon as its one connection closes.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db

# The app configures DEBUG logging in development, which buries test failures
# under thousands of SQL lines. Tests assert on responses, not on logs.
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)


@pytest_asyncio.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def _admin_session(setup_database: None) -> AsyncGenerator[None, None]:
    """Create the test administrator and a live session for each test."""
    # Throttle state is per-process; reset it so one test's failed logins do not
    # lock out the next test.
    mutation_limiter.reset()

    async with TestingSessionLocal() as db:
        user = AdminUser(
            username=ADMIN_USERNAME,
            password_hash=hash_password(ADMIN_PASSWORD),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        token, session = await create_session(db, user)
        csrf = session.csrf_token

    ADMIN_HEADERS.clear()
    ADMIN_HEADERS.update(
        {
            "Cookie": f"{SESSION_COOKIE_NAME}={token}",
            CSRF_HEADER_NAME: csrf,
        }
    )
    yield
    ADMIN_HEADERS.clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Anonymous client. Requests are unauthenticated unless ADMIN_HEADERS is
    passed explicitly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_client() -> AsyncGenerator[AsyncClient, None]:
    """Client pre-authenticated as the test administrator, for tests that read
    more naturally without repeating the headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=dict(ADMIN_HEADERS)
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Direct DB access for setting up fixture data (matches, standings, etc.)
    that has no public write endpoint of its own."""
    async with TestingSessionLocal() as session:
        yield session
