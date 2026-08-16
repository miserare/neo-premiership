"""Revision 7d2e9c4a1b6f against populated PostgreSQL.

Set MIGRATION_TEST_DATABASE_URL to a PostgreSQL database that may be dropped
and recreated. SQLite cannot exercise PostgreSQL constraints or transactional
migration rollback.
"""

import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_DB_URL = os.environ.get("MIGRATION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not MIGRATION_DB_URL,
    reason="MIGRATION_TEST_DATABASE_URL is not set; needs a real PostgreSQL database",
)

LEGACY_REVISION = "b8e1d3a67c25"


def _alembic(command: list[str], url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "ENVIRONMENT": "development", "DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *command],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


async def _reset(url: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    await engine.dispose()
    result = _alembic(["upgrade", LEGACY_REVISION], url)
    assert result.returncode == 0, result.stderr


async def _seed(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO players
                    (id, username, slug, join_date, is_active, is_placeholder,
                     elo_rating, initial_elo_rating)
                VALUES
                  ('11111111-1111-4111-8111-111111111111', 'Home', 'home', now(),
                   true, false, 1000, 1000),
                  ('22222222-2222-4222-8222-222222222222', 'Away', 'away', now(),
                   true, false, 1000, 1000),
                  ('33333333-3333-4333-8333-333333333333', 'Spectre (Nizhinsky)',
                   'spectre', now(), true, false, 1000, 1000)
                """
            )
        )
        await connection.execute(
            text(
                """
                INSERT INTO seasons (id, name, slug, start_date)
                VALUES ('99999999-9999-4999-8999-999999999999',
                        'Migration Season', 'migration-season', DATE '2026-01-01')
                """
            )
        )
        await connection.execute(
            text(
                """
                INSERT INTO matches
                    (id, season_id, home_player_id, away_player_id, winner_id,
                     status, stage, completed_at, home_score, away_score, replay_url)
                VALUES
                  ('aaaaaaaa-0000-4000-8000-000000000001',
                   '99999999-9999-4999-8999-999999999999',
                   '11111111-1111-4111-8111-111111111111',
                   '22222222-2222-4222-8222-222222222222',
                   '11111111-1111-4111-8111-111111111111',
                   'completed', 'group', TIMESTAMPTZ '2026-01-01 20:00+00',
                   6, 0, 'https://example.invalid/group'),
                  ('aaaaaaaa-0000-4000-8000-000000000002',
                   '99999999-9999-4999-8999-999999999999',
                   '11111111-1111-4111-8111-111111111111',
                   '22222222-2222-4222-8222-222222222222',
                   '22222222-2222-4222-8222-222222222222',
                   'completed', 'playoffs', TIMESTAMPTZ '2026-01-02 20:00+00',
                   NULL, NULL, NULL)
                """
            )
        )
        await connection.execute(
            text(
                """
                INSERT INTO match_games (id, match_id, game_number, winner_id, replay_url)
                VALUES
                  ('bbbbbbbb-0000-4000-8000-000000000001',
                   'aaaaaaaa-0000-4000-8000-000000000002', 1,
                   '11111111-1111-4111-8111-111111111111', 'https://example.invalid/g1'),
                  ('bbbbbbbb-0000-4000-8000-000000000002',
                   'aaaaaaaa-0000-4000-8000-000000000002', 2,
                   '22222222-2222-4222-8222-222222222222', 'https://example.invalid/g2'),
                  ('bbbbbbbb-0000-4000-8000-000000000003',
                   'aaaaaaaa-0000-4000-8000-000000000002', 3,
                   '22222222-2222-4222-8222-222222222222', 'https://example.invalid/g3')
                """
            )
        )
        # The obsolete ledger has one event per parent series. The migration
        # must derive its replacement from all four individual games.
        await connection.execute(
            text(
                """
                INSERT INTO elo_rating_events
                    (id, match_id, player_id, opponent_id, occurred_at,
                     rating_before, rating_after, rating_change, result, expected_score)
                VALUES
                  ('cccccccc-0000-4000-8000-000000000001',
                   'aaaaaaaa-0000-4000-8000-000000000001',
                   '11111111-1111-4111-8111-111111111111',
                   '22222222-2222-4222-8222-222222222222',
                   TIMESTAMPTZ '2026-01-01 20:00+00', 1000, 1032, 32, 1, 0.5),
                  ('cccccccc-0000-4000-8000-000000000002',
                   'aaaaaaaa-0000-4000-8000-000000000001',
                   '22222222-2222-4222-8222-222222222222',
                   '11111111-1111-4111-8111-111111111111',
                   TIMESTAMPTZ '2026-01-01 20:00+00', 1000, 968, -32, 0, 0.5),
                  ('cccccccc-0000-4000-8000-000000000003',
                   'aaaaaaaa-0000-4000-8000-000000000002',
                   '11111111-1111-4111-8111-111111111111',
                   '22222222-2222-4222-8222-222222222222',
                   TIMESTAMPTZ '2026-01-02 20:00+00', 1032, 1000, -32, 0, 0.5),
                  ('cccccccc-0000-4000-8000-000000000004',
                   'aaaaaaaa-0000-4000-8000-000000000002',
                   '22222222-2222-4222-8222-222222222222',
                   '11111111-1111-4111-8111-111111111111',
                   TIMESTAMPTZ '2026-01-02 20:00+00', 968, 1000, 32, 1, 0.5)
                """
            )
        )
    await engine.dispose()


async def _rows(url: str, query: str) -> list[tuple]:
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        result = (await connection.execute(text(query))).all()
    await engine.dispose()
    return [tuple(row) for row in result]


async def test_populated_migration_backfills_scores_formats_creator_and_per_game_elo() -> None:
    assert MIGRATION_DB_URL is not None
    await _reset(MIGRATION_DB_URL)
    await _seed(MIGRATION_DB_URL)

    result = _alembic(["upgrade", "head"], MIGRATION_DB_URL)
    assert result.returncode == 0, result.stderr

    assert await _rows(
        MIGRATION_DB_URL,
        "SELECT stage, best_of FROM matches ORDER BY stage",
    ) == [("group", 1), ("playoffs", 3)]
    assert await _rows(
        MIGRATION_DB_URL,
        """
        SELECT m.stage, g.game_number, g.home_pokemon_score, g.away_pokemon_score,
               g.completed_at = m.completed_at
        FROM matches m JOIN match_games g ON g.match_id=m.id
        ORDER BY m.stage, g.game_number
        """,
    ) == [
        ("group", 1, 6, 0, True),
        ("playoffs", 1, None, None, True),
        ("playoffs", 2, None, None, True),
        ("playoffs", 3, None, None, True),
    ]
    assert await _rows(
        MIGRATION_DB_URL,
        "SELECT username, is_site_creator FROM players WHERE is_site_creator",
    ) == [("Spectre (Nizhinsky)", True)]
    assert await _rows(
        MIGRATION_DB_URL,
        "SELECT count(*), count(DISTINCT match_game_id) FROM elo_rating_events",
    ) == [(8, 4)]
    home_events = await _rows(
        MIGRATION_DB_URL,
        """
        SELECT rating_before, rating_after
        FROM elo_rating_events
        WHERE player_id='11111111-1111-4111-8111-111111111111'
        ORDER BY occurred_at, match_id, match_game_id
        """,
    )
    assert len(home_events) == 4
    assert all(home_events[index][1] == home_events[index + 1][0] for index in range(3))

    down = _alembic(["downgrade", LEGACY_REVISION], MIGRATION_DB_URL)
    assert down.returncode == 0, down.stderr
    assert await _rows(MIGRATION_DB_URL, "SELECT count(*) FROM elo_rating_events") == [(0,)]
    assert await _rows(
        MIGRATION_DB_URL,
        "SELECT bool_and(elo_rating=initial_elo_rating) FROM players",
    ) == [(True,)]
    up = _alembic(["upgrade", "head"], MIGRATION_DB_URL)
    assert up.returncode == 0, up.stderr
    assert await _rows(MIGRATION_DB_URL, "SELECT count(*) FROM elo_rating_events") == [(8,)]


async def test_migration_refuses_a_post_clinch_game_and_rolls_back() -> None:
    assert MIGRATION_DB_URL is not None
    await _reset(MIGRATION_DB_URL)
    await _seed(MIGRATION_DB_URL)
    engine = create_async_engine(MIGRATION_DB_URL)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO match_games (id, match_id, game_number, winner_id)
                VALUES ('bbbbbbbb-0000-4000-8000-000000000004',
                        'aaaaaaaa-0000-4000-8000-000000000002', 4,
                        '11111111-1111-4111-8111-111111111111')
                """
            )
        )
    await engine.dispose()

    result = _alembic(["upgrade", "head"], MIGRATION_DB_URL)
    assert result.returncode != 0
    assert "after the BO3 series was clinched" in result.stderr
    assert await _rows(MIGRATION_DB_URL, "SELECT version_num FROM alembic_version") == [
        (LEGACY_REVISION,)
    ]
    assert await _rows(
        MIGRATION_DB_URL,
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name='matches' AND column_name='best_of'",
    ) == [(0,)]


async def test_migration_refuses_an_unknown_group_pokemon_score() -> None:
    assert MIGRATION_DB_URL is not None
    await _reset(MIGRATION_DB_URL)
    await _seed(MIGRATION_DB_URL)
    engine = create_async_engine(MIGRATION_DB_URL)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE matches SET home_score=NULL, away_score=NULL "
                "WHERE id='aaaaaaaa-0000-4000-8000-000000000001'"
            )
        )
    await engine.dispose()

    result = _alembic(["upgrade", "head"], MIGRATION_DB_URL)
    assert result.returncode != 0
    assert "unknown or invalid Pokémon score" in result.stderr
    assert await _rows(MIGRATION_DB_URL, "SELECT version_num FROM alembic_version") == [
        (LEGACY_REVISION,)
    ]


async def test_migration_applies_the_reviewed_ael_two_zero_correction() -> None:
    assert MIGRATION_DB_URL is not None
    await _reset(MIGRATION_DB_URL)
    engine = create_async_engine(MIGRATION_DB_URL)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO players
                    (id, username, slug, join_date, is_active, is_placeholder,
                     elo_rating, initial_elo_rating)
                VALUES
                  ('11111111-1111-4111-8111-111111111111', 'AEL (Cheeburbur)',
                   'cheeburbur', now(), true, false, 1000, 1000),
                  ('22222222-2222-4222-8222-222222222222', 'Renk',
                   'renk', now(), true, false, 1000, 1000)
                """
            )
        )
        await connection.execute(
            text(
                """
                INSERT INTO seasons (id, name, slug, start_date)
                VALUES ('99999999-9999-4999-8999-999999999999',
                        'Reviewed Season', 'reviewed-season', DATE '2026-01-01')
                """
            )
        )
        await connection.execute(
            text(
                """
                INSERT INTO matches
                    (id, season_id, home_player_id, away_player_id, winner_id,
                     status, stage, completed_at, home_score, away_score)
                VALUES
                  ('c2dece82-561d-4664-be58-fa94c4d96e2a',
                   '99999999-9999-4999-8999-999999999999',
                   '11111111-1111-4111-8111-111111111111',
                   '22222222-2222-4222-8222-222222222222',
                   '11111111-1111-4111-8111-111111111111',
                   'completed', 'playoffs', TIMESTAMPTZ '2026-01-02 20:00+00',
                   NULL, NULL)
                """
            )
        )
        await connection.execute(
            text(
                """
                INSERT INTO match_games (id, match_id, game_number, winner_id)
                VALUES
                  ('bbbbbbbb-0000-4000-8000-000000000001',
                   'c2dece82-561d-4664-be58-fa94c4d96e2a', 1,
                   '11111111-1111-4111-8111-111111111111'),
                  ('bbbbbbbb-0000-4000-8000-000000000002',
                   'c2dece82-561d-4664-be58-fa94c4d96e2a', 2,
                   '11111111-1111-4111-8111-111111111111'),
                  ('bbbbbbbb-0000-4000-8000-000000000003',
                   'c2dece82-561d-4664-be58-fa94c4d96e2a', 3, NULL)
                """
            )
        )
    await engine.dispose()

    result = _alembic(["upgrade", "head"], MIGRATION_DB_URL)
    assert result.returncode == 0, result.stderr
    assert await _rows(
        MIGRATION_DB_URL,
        """
        SELECT m.best_of, g.game_number, g.winner_id
        FROM matches m JOIN match_games g ON g.match_id=m.id
        WHERE m.id='c2dece82-561d-4664-be58-fa94c4d96e2a'
        ORDER BY g.game_number
        """,
    ) == [
        (3, 1, UUID("11111111-1111-4111-8111-111111111111")),
        (3, 2, UUID("11111111-1111-4111-8111-111111111111")),
    ]
    assert await _rows(
        MIGRATION_DB_URL,
        "SELECT count(*) FROM elo_rating_events",
    ) == [(4,)]
