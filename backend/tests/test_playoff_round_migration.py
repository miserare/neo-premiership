"""The legacy-data conversion in revision e4a7c2b8d5f1, against real PostgreSQL.

These run against a live PostgreSQL because that is where the migration runs.
The rest of the suite uses in-memory SQLite via Base.metadata.create_all, which
never executes a migration at all and could not prove anything here.

Set MIGRATION_TEST_DATABASE_URL to a PostgreSQL database that may be dropped and
recreated, e.g.

    MIGRATION_TEST_DATABASE_URL=postgresql+asyncpg://ci:ci@localhost:5432/ci

Without it these tests skip, so the SQLite-only suite still runs anywhere.
"""
import os
import subprocess
import sys
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
LEGACY_REVISION = "f3d9e2a4c711"
ROUND_REVISION = "e4a7c2b8d5f1"


def _alembic(command: list[str], url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "ENVIRONMENT": "development", "DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *command],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


async def _reset_to_legacy_schema(url: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()
    result = _alembic(["upgrade", LEGACY_REVISION], url)
    assert result.returncode == 0, result.stderr


async def _seed_legacy_season_two(url: str) -> None:
    """Season 2 exactly as the old schema stored it: labelled playoff matches
    with no round_order and no bracket_order anywhere."""
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO players (id, username, join_date, is_active, is_placeholder,
                                     elo_rating, initial_elo_rating)
                VALUES
                  ('11111111-1111-4111-8111-111111111111', 'Steve', now(), true, false, 1000, 1000),
                  ('22222222-2222-4222-8222-222222222222', 'Doodle', now(), true, false, 1000, 1000),
                  ('33333333-3333-4333-8333-333333333333', 'AEL (Cheeburbur)', now(), true, false, 1000, 1000),
                  ('44444444-4444-4444-8444-444444444444', 'Matts', now(), true, false, 1000, 1000),
                  ('55555555-5555-4555-8555-555555555555', 'Renk', now(), true, false, 1000, 1000),
                  ('66666666-6666-4666-8666-666666666666', 'Seb Ball', now(), true, false, 1000, 1000)
                """
            )
        )
        await conn.execute(
            text(
                "INSERT INTO seasons (id, name, start_date, end_date) VALUES "
                "('99999999-9999-4999-8999-999999999999', 'Season 2', DATE '2024-10-25', DATE '2025-01-05')"
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO matches (id, season_id, home_player_id, away_player_id, winner_id,
                                     status, stage, round_label, round_order, bracket_order,
                                     scheduled_at, completed_at, replay_url, youtube_url)
                VALUES
                  ('aaaaaaaa-0000-4000-8000-000000000001',
                   '99999999-9999-4999-8999-999999999999',
                   '44444444-4444-4444-8444-444444444444', '55555555-5555-4555-8555-555555555555',
                   '55555555-5555-4555-8555-555555555555', 'completed', 'group',
                   'Group - Matchday 1', NULL, NULL,
                   TIMESTAMPTZ '2024-11-01 04:00+00', TIMESTAMPTZ '2024-11-01 04:01+00',
                   NULL, 'https://example.invalid/group'),

                  ('aaaaaaaa-0000-4000-8000-000000000002',
                   '99999999-9999-4999-8999-999999999999',
                   '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222',
                   '22222222-2222-4222-8222-222222222222', 'completed', 'playoffs',
                   'First Round', NULL, NULL,
                   TIMESTAMPTZ '2024-12-20 05:00+00', TIMESTAMPTZ '2024-12-20 05:00+00',
                   'https://example.invalid/r1a', 'https://example.invalid/v1'),

                  ('aaaaaaaa-0000-4000-8000-000000000003',
                   '99999999-9999-4999-8999-999999999999',
                   '33333333-3333-4333-8333-333333333333', '44444444-4444-4444-8444-444444444444',
                   '33333333-3333-4333-8333-333333333333', 'completed', 'playoffs',
                   'First Round', NULL, NULL,
                   TIMESTAMPTZ '2024-12-20 05:00+00', TIMESTAMPTZ '2024-12-20 05:00+00',
                   'https://example.invalid/r1b', 'https://example.invalid/v2'),

                  ('aaaaaaaa-0000-4000-8000-000000000004',
                   '99999999-9999-4999-8999-999999999999',
                   '55555555-5555-4555-8555-555555555555', '22222222-2222-4222-8222-222222222222',
                   '22222222-2222-4222-8222-222222222222', 'completed', 'playoffs',
                   'Semifinal', NULL, NULL,
                   TIMESTAMPTZ '2024-12-23 05:00+00', TIMESTAMPTZ '2024-12-23 05:00+00', NULL, NULL),

                  ('aaaaaaaa-0000-4000-8000-000000000005',
                   '99999999-9999-4999-8999-999999999999',
                   '66666666-6666-4666-8666-666666666666', '33333333-3333-4333-8333-333333333333',
                   '33333333-3333-4333-8333-333333333333', 'completed', 'playoffs',
                   'Semifinal', NULL, NULL,
                   TIMESTAMPTZ '2024-12-24 05:00+00', TIMESTAMPTZ '2024-12-24 05:00+00', NULL, NULL),

                  ('aaaaaaaa-0000-4000-8000-000000000006',
                   '99999999-9999-4999-8999-999999999999',
                   '33333333-3333-4333-8333-333333333333', '22222222-2222-4222-8222-222222222222',
                   '33333333-3333-4333-8333-333333333333', 'completed', 'playoffs',
                   'Final', NULL, NULL,
                   TIMESTAMPTZ '2025-01-05 05:00+00', TIMESTAMPTZ '2025-01-05 05:00+00', NULL, NULL)
                """
            )
        )
    await engine.dispose()


async def _fetch(url: str, sql: str) -> list[tuple]:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql))).all()
    await engine.dispose()
    return [tuple(row) for row in rows]


async def test_legacy_season_two_becomes_first_round_semifinal_final() -> None:
    """Requirement: existing Season 2-style data converts to the reviewed
    bracket, with the positions the season was actually played in."""
    await _reset_to_legacy_schema(MIGRATION_DB_URL)
    await _seed_legacy_season_two(MIGRATION_DB_URL)

    result = _alembic(["upgrade", ROUND_REVISION], MIGRATION_DB_URL)
    assert result.returncode == 0, result.stderr

    rounds = await _fetch(
        MIGRATION_DB_URL,
        "SELECT display_order, label FROM playoff_rounds ORDER BY display_order",
    )
    assert rounds == [(1, "First Round"), (2, "Semifinal"), (3, "Final")]

    bracket = await _fetch(
        MIGRATION_DB_URL,
        """
        SELECT r.display_order, m.bracket_order, hp.username, ap.username
        FROM matches m
        JOIN playoff_rounds r ON r.id = m.playoff_round_id
        JOIN players hp ON hp.id = m.home_player_id
        JOIN players ap ON ap.id = m.away_player_id
        ORDER BY r.display_order, m.bracket_order
        """,
    )
    assert bracket == [
        (1, 1, "Steve", "Doodle"),
        (1, 2, "AEL (Cheeburbur)", "Matts"),
        (2, 1, "Renk", "Doodle"),
        (2, 2, "Seb Ball", "AEL (Cheeburbur)"),
        (3, 1, "AEL (Cheeburbur)", "Doodle"),
    ]


async def test_migration_preserves_everything_it_does_not_own() -> None:
    """Results, replays, videos, dates and the group stage survive untouched,
    and the legacy columns are left consistent so a rollback still sorts."""
    await _reset_to_legacy_schema(MIGRATION_DB_URL)
    await _seed_legacy_season_two(MIGRATION_DB_URL)

    result = _alembic(["upgrade", ROUND_REVISION], MIGRATION_DB_URL)
    assert result.returncode == 0, result.stderr

    counts = await _fetch(
        MIGRATION_DB_URL,
        """
        SELECT (SELECT count(*) FROM matches),
               (SELECT count(*) FROM matches WHERE stage = 'playoffs' AND playoff_round_id IS NULL),
               (SELECT count(*) FROM matches WHERE stage = 'group' AND playoff_round_id IS NOT NULL),
               (SELECT count(*) FROM matches WHERE winner_id IS NOT NULL),
               (SELECT count(*) FROM matches WHERE replay_url IS NOT NULL),
               (SELECT count(*) FROM matches WHERE youtube_url IS NOT NULL),
               (SELECT count(*) FROM matches WHERE completed_at IS NOT NULL)
        """,
    )
    assert counts == [(6, 0, 0, 6, 2, 3, 6)]

    # The group match keeps its own label and gains no round.
    group = await _fetch(
        MIGRATION_DB_URL,
        "SELECT round_label, playoff_round_id FROM matches WHERE stage = 'group'",
    )
    assert group == [("Group - Matchday 1", None)]

    # Legacy mirrors are consistent with the new rounds, so the previous
    # release would render the same order if this were rolled back.
    legacy = await _fetch(
        MIGRATION_DB_URL,
        """
        SELECT DISTINCT m.round_label, m.round_order, r.label, r.display_order
        FROM matches m JOIN playoff_rounds r ON r.id = m.playoff_round_id
        ORDER BY m.round_order
        """,
    )
    assert legacy == [
        ("First Round", 1, "First Round", 1),
        ("Semifinal", 2, "Semifinal", 2),
        ("Final", 3, "Final", 3),
    ]


async def test_migration_refuses_to_guess_and_changes_nothing() -> None:
    """A label the reviewed mapping does not cover, with no stored order, is a
    human decision. The migration must stop rather than invent an order - and
    must leave the database exactly as it found it."""
    await _reset_to_legacy_schema(MIGRATION_DB_URL)
    await _seed_legacy_season_two(MIGRATION_DB_URL)
    engine = create_async_engine(MIGRATION_DB_URL)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE matches SET round_label = 'Ronda Uno' WHERE round_label = 'First Round'")
        )
    await engine.dispose()

    result = _alembic(["upgrade", ROUND_REVISION], MIGRATION_DB_URL)

    assert result.returncode != 0
    assert "Ronda Uno" in result.stderr
    assert "will not guess" in result.stderr

    still_legacy = await _fetch(MIGRATION_DB_URL, "SELECT version_num FROM alembic_version")
    assert still_legacy == [(LEGACY_REVISION,)]
    absent = await _fetch(MIGRATION_DB_URL, "SELECT to_regclass('public.playoff_rounds') IS NULL")
    assert absent == [(True,)]
    intact = await _fetch(MIGRATION_DB_URL, "SELECT count(*) FROM matches")
    assert intact == [(6,)]


async def test_migration_keeps_an_order_that_is_already_stored() -> None:
    """A season that already carries agreeing round_order values needs no
    reviewed mapping - the data already says where its rounds go."""
    await _reset_to_legacy_schema(MIGRATION_DB_URL)
    await _seed_legacy_season_two(MIGRATION_DB_URL)
    engine = create_async_engine(MIGRATION_DB_URL)
    async with engine.begin() as conn:
        # Deliberately unrelated to the alphabet, and deliberately not the
        # order the reviewed mapping would produce.
        await conn.execute(text("UPDATE seasons SET name = 'Unreviewed Season'"))
        await conn.execute(
            text("UPDATE matches SET round_label='Zulu', round_order=1, bracket_order=1 "
                 "WHERE id='aaaaaaaa-0000-4000-8000-000000000002'")
        )
        await conn.execute(
            text("UPDATE matches SET round_label='Zulu', round_order=1, bracket_order=2 "
                 "WHERE id='aaaaaaaa-0000-4000-8000-000000000003'")
        )
        await conn.execute(
            text("UPDATE matches SET round_label='Alpha', round_order=2, bracket_order=1 "
                 "WHERE id='aaaaaaaa-0000-4000-8000-000000000004'")
        )
        await conn.execute(
            text("UPDATE matches SET round_label='Alpha', round_order=2, bracket_order=2 "
                 "WHERE id='aaaaaaaa-0000-4000-8000-000000000005'")
        )
        await conn.execute(
            text("UPDATE matches SET round_label='Mike', round_order=3, bracket_order=1 "
                 "WHERE id='aaaaaaaa-0000-4000-8000-000000000006'")
        )
    await engine.dispose()

    result = _alembic(["upgrade", ROUND_REVISION], MIGRATION_DB_URL)
    assert result.returncode == 0, result.stderr

    rounds = await _fetch(
        MIGRATION_DB_URL, "SELECT display_order, label FROM playoff_rounds ORDER BY display_order"
    )
    # Alphabetically this would be Alpha, Mike, Zulu. It is not.
    assert rounds == [(1, "Zulu"), (2, "Alpha"), (3, "Mike")]
