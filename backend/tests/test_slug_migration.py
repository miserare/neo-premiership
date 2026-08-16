"""The slug backfill in revision b8e1d3a67c25, against real PostgreSQL.

Same rationale as test_playoff_round_migration: the SQLite suite never runs a
migration, so only a live PostgreSQL can prove what this one does to populated
data.

    MIGRATION_TEST_DATABASE_URL=postgresql+asyncpg://ci:ci@localhost:5432/ci

Without it these tests skip.
"""

import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parent.parent

MIGRATION_DB_URL = os.environ.get("MIGRATION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not MIGRATION_DB_URL, reason="MIGRATION_TEST_DATABASE_URL is not set; needs a real PostgreSQL database"
)

# The revision immediately before the one under test.
LEGACY_REVISION = "e4a7c2b8d5f1"
SLUG_REVISION = "b8e1d3a67c25"


def _alembic(command: list[str], url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "ENVIRONMENT": "development", "DATABASE_URL": url}
    return subprocess.run(
        ["alembic", *command], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True
    )


async def _reset_to_legacy_schema(url: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()
    result = _alembic(["upgrade", LEGACY_REVISION], url)
    assert result.returncode == 0, result.stderr


# Real production names, including the two that carry a parenthetical second
# name and the one pair that collides on a naive slug. Ordered join_dates,
# because the backfill resolves collisions by seniority.
LEGACY_PLAYERS = [
    ("11111111-1111-4111-8111-111111111111", "Psykick", "2024-01-01"),
    ("22222222-2222-4222-8222-222222222222", "Spectre (Nizhinsky)", "2024-01-02"),
    ("33333333-3333-4333-8333-333333333333", "AEL (Cheeburbur)", "2024-01-03"),
    ("44444444-4444-4444-8444-444444444444", "Michael Talks Football", "2024-01-04"),
    ("55555555-5555-4555-8555-555555555555", "T10S", "2024-01-05"),
    ("66666666-6666-4666-8666-666666666666", "Brazilian Fury", "2024-01-06"),
    # Not in production, but the collision case has to be exercised somewhere:
    # both of these slugify to "caps-lock", and the older one keeps it.
    ("77777777-7777-4777-8777-777777777777", "Caps Lock", "2024-01-07"),
    ("88888888-8888-4888-8888-888888888888", "caps-lock", "2024-01-08"),
    # No ASCII at all, so nothing can be derived and the fallback must fire.
    ("99999999-9999-4999-8999-999999999999", "限界突破", "2024-01-09"),
]

LEGACY_SEASONS = [
    ("a0000000-0000-4000-8000-000000000001", "Season 1", "2024-05-31"),
    ("a0000000-0000-4000-8000-000000000004", "Season 4", "2025-06-14"),
    ("a0000000-0000-4000-8000-000000000007", "Season 7", "2026-08-13"),
    # A future season whose name has no number in it at all.
    ("a0000000-0000-4000-8000-000000000008", "Summer Invitational 2027", "2027-06-01"),
]


async def _seed_legacy_rows(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        for player_id, username, joined in LEGACY_PLAYERS:
            await conn.execute(
                text(
                    "INSERT INTO players (id, username, join_date, is_active, is_placeholder,"
                    " elo_rating, initial_elo_rating)"
                    " VALUES (:id, :username, :joined, true, false, 1000, 1000)"
                ),
                {
                    "id": player_id,
                    "username": username,
                    "joined": datetime.fromisoformat(joined).replace(tzinfo=timezone.utc),
                },
            )
        for season_id, name, start in LEGACY_SEASONS:
            await conn.execute(
                text(
                    "INSERT INTO seasons (id, name, start_date, overview)"
                    " VALUES (:id, :name, :start, :overview)"
                ),
                {
                    "id": season_id,
                    "name": name,
                    "start": date.fromisoformat(start),
                    "overview": f"{name} overview",
                },
            )
        # One match, so the homepage-highlighting columns are exercised against a
        # populated table rather than an empty one.
        await conn.execute(
            text(
                "INSERT INTO matches (id, season_id, home_player_id, away_player_id, status, stage,"
                " scheduled_at)"
                " VALUES ('b0000000-0000-4000-8000-000000000001',"
                " 'a0000000-0000-4000-8000-000000000007',"
                " '11111111-1111-4111-8111-111111111111',"
                " '22222222-2222-4222-8222-222222222222',"
                " 'scheduled', 'group', TIMESTAMPTZ '2026-08-22 04:00+00')"
            )
        )
    await engine.dispose()


async def _fetch(url: str, query: str) -> list[dict]:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text(query))).mappings().all()
    await engine.dispose()
    return [dict(row) for row in rows]


@pytest.fixture
async def migrated_url() -> str:
    assert MIGRATION_DB_URL is not None
    await _reset_to_legacy_schema(MIGRATION_DB_URL)
    await _seed_legacy_rows(MIGRATION_DB_URL)
    result = _alembic(["upgrade", SLUG_REVISION], MIGRATION_DB_URL)
    assert result.returncode == 0, result.stderr
    return MIGRATION_DB_URL


async def test_player_slugs_are_backfilled_from_usernames(migrated_url: str) -> None:
    rows = await _fetch(migrated_url, "SELECT username, slug FROM players ORDER BY join_date")
    slugs = {row["username"]: row["slug"] for row in rows}

    assert slugs["Psykick"] == "psykick"
    assert slugs["Michael Talks Football"] == "michael-talks-football"
    assert slugs["T10S"] == "t10s"
    assert slugs["Brazilian Fury"] == "brazilian-fury"


async def test_the_two_named_players_get_their_specified_slugs(migrated_url: str) -> None:
    """Neither of these is derivable by a single rule - one takes the leading
    name, the other the parenthetical - so the migration lists them explicitly."""
    rows = await _fetch(migrated_url, "SELECT username, slug FROM players")
    slugs = {row["username"]: row["slug"] for row in rows}

    assert slugs["Spectre (Nizhinsky)"] == "spectre"
    assert slugs["AEL (Cheeburbur)"] == "cheeburbur"


async def test_colliding_names_are_resolved_by_seniority(migrated_url: str) -> None:
    rows = await _fetch(migrated_url, "SELECT username, slug FROM players")
    slugs = {row["username"]: row["slug"] for row in rows}

    # The earlier join_date keeps the plain slug; the later one is suffixed.
    assert slugs["Caps Lock"] == "caps-lock"
    assert slugs["caps-lock"] == "caps-lock-2"


async def test_a_name_with_no_ascii_gets_a_usable_fallback_slug(migrated_url: str) -> None:
    rows = await _fetch(migrated_url, "SELECT username, slug FROM players")
    slugs = {row["username"]: row["slug"] for row in rows}

    slug = slugs["限界突破"]
    assert slug.startswith("player-")
    assert slug != "player-"


async def test_season_slugs_drop_the_season_prefix(migrated_url: str) -> None:
    rows = await _fetch(migrated_url, "SELECT name, slug FROM seasons")
    slugs = {row["name"]: row["slug"] for row in rows}

    assert slugs["Season 1"] == "1"
    assert slugs["Season 4"] == "4"
    assert slugs["Season 7"] == "7"
    # No number in the name, and none invented.
    assert slugs["Summer Invitational 2027"] == "summer-invitational-2027"


async def test_every_slug_is_unique_and_lowercase(migrated_url: str) -> None:
    for table in ("players", "seasons"):
        rows = await _fetch(migrated_url, f"SELECT slug FROM {table}")
        slugs = [row["slug"] for row in rows]
        assert len(slugs) == len(set(slugs)), f"{table} slugs collided"
        assert all(slug == slug.lower() and slug for slug in slugs)


async def test_existing_data_survives_the_migration(migrated_url: str) -> None:
    """The point of the whole exercise: nothing already recorded is lost."""
    players = await _fetch(migrated_url, "SELECT username FROM players")
    assert {row["username"] for row in players} == {name for _, name, _ in LEGACY_PLAYERS}

    seasons = await _fetch(migrated_url, "SELECT name, overview FROM seasons")
    assert {row["name"] for row in seasons} == {name for _, name, _ in LEGACY_SEASONS}
    assert all(row["overview"] == f"{row['name']} overview" for row in seasons)

    matches = await _fetch(
        migrated_url, "SELECT featured_on_homepage, homepage_feature_order FROM matches"
    )
    assert len(matches) == 1
    # New columns default to "not featured" rather than surfacing every existing
    # match on the homepage.
    assert matches[0]["featured_on_homepage"] is False
    assert matches[0]["homepage_feature_order"] is None


async def test_new_columns_start_empty(migrated_url: str) -> None:
    players = await _fetch(migrated_url, "SELECT biography FROM players")
    assert all(row["biography"] is None for row in players)

    seasons = await _fetch(migrated_url, "SELECT hall_of_fame_description FROM seasons")
    assert all(row["hall_of_fame_description"] is None for row in seasons)


async def test_downgrade_then_reupgrade_reassigns_the_same_slugs(migrated_url: str) -> None:
    before = {
        row["username"]: row["slug"]
        for row in await _fetch(migrated_url, "SELECT username, slug FROM players")
    }

    down = _alembic(["downgrade", LEGACY_REVISION], migrated_url)
    assert down.returncode == 0, down.stderr
    up = _alembic(["upgrade", SLUG_REVISION], migrated_url)
    assert up.returncode == 0, up.stderr

    after = {
        row["username"]: row["slug"]
        for row in await _fetch(migrated_url, "SELECT username, slug FROM players")
    }
    # Deterministic: the same input data produces the same slugs, so a
    # downgrade/upgrade cycle does not silently rewrite everyone's URL.
    assert after == before
