from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player
from app.models.season import Season
from app.models.match import Match, MatchStage, MatchStatus
from app.models.match_game import MatchGame
from app.services.elo import recalculate_elo_ratings
from tests.conftest import ADMIN_HEADERS, make_player, make_season


async def _league(db_session: AsyncSession, *, home_elo: int = 1000) -> tuple[Season, Player, Player]:
    season = make_season(name="Elo Test Season", start_date=date(2024, 1, 1))
    home = make_player(
        username="EloHome",
        initial_elo_rating=home_elo,
        elo_rating=home_elo,
    )
    away = make_player(username="EloAway")
    db_session.add_all([season, home, away])
    await db_session.commit()
    return season, home, away


async def _completed_match(
    client: AsyncClient,
    season: Season,
    home: Player,
    away: Player,
    *,
    winner: Player,
    completed_at: str,
):
    return await client.post(
        "/api/matches",
        json={
            "season_id": str(season.id),
            "home_player_id": str(home.id),
            "away_player_id": str(away.id),
            "stage": "group",
            "status": "completed",
            "winner_id": str(winner.id),
            "completed_at": completed_at,
        },
        headers=ADMIN_HEADERS,
    )


async def test_equal_ratings_move_by_32_points(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, away = await _league(db_session)

    response = await _completed_match(
        client,
        season,
        home,
        away,
        winner=home,
        completed_at="2024-01-01T12:00:00Z",
    )

    assert response.status_code == 201
    assert response.json()["home_player"]["elo_rating"] == 1032
    assert response.json()["away_player"]["elo_rating"] == 968

    detail = (await client.get(f"/api/players/{home.id}")).json()
    assert detail["elo_rating"] == 1032
    assert len(detail["elo_history"]) == 1
    event = detail["elo_history"][0]
    assert event["match_id"] == response.json()["id"]
    assert event["game_number"] == 1
    assert event["opponent_id"] == str(away.id)
    assert event["rating_before"] == 1000
    assert event["rating_after"] == 1032
    assert event["player_pokemon_score"] is None


async def test_formula_uses_each_players_rating_before_the_match(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, away = await _league(db_session, home_elo=1200)

    response = await _completed_match(
        client,
        season,
        home,
        away,
        winner=home,
        completed_at="2024-01-01T12:00:00+00:00",
    )

    assert response.status_code == 201
    assert response.json()["home_player"]["elo_rating"] == 1215
    assert response.json()["away_player"]["elo_rating"] == 985
    event = (await client.get(f"/api/players/{home.id}")).json()["elo_history"][0]
    assert event["expected_score"] == pytest.approx(0.7597469)


async def test_changing_starting_elo_recalculates_existing_history(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, away = await _league(db_session)
    match = await _completed_match(
        client,
        season,
        home,
        away,
        winner=home,
        completed_at="2024-01-01T12:00:00Z",
    )
    assert match.status_code == 201

    response = await client.patch(
        f"/api/players/{home.id}",
        json={"initial_elo_rating": 1200},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["initial_elo_rating"] == 1200
    assert response.json()["elo_rating"] == 1215
    detail = (await client.get(f"/api/players/{home.id}")).json()
    assert detail["elo_history"][0]["rating_before"] == 1200
    assert detail["elo_history"][0]["rating_after"] == 1215


async def test_backdated_result_recalculates_every_later_match(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, away = await _league(db_session)
    february = await _completed_match(
        client,
        season,
        home,
        away,
        winner=home,
        completed_at="2024-02-01T12:00:00Z",
    )
    january = await _completed_match(
        client,
        season,
        home,
        away,
        winner=home,
        completed_at="2024-01-01T12:00:00Z",
    )

    assert february.status_code == 201
    assert january.status_code == 201
    detail = (await client.get(f"/api/players/{home.id}")).json()
    assert detail["elo_rating"] == 1058
    assert [entry["rating_after"] for entry in reversed(detail["elo_history"])] == [1032, 1058]

    correction = await client.patch(
        f"/api/matches/{january.json()['id']}",
        json={"winner_id": str(away.id)},
        headers=ADMIN_HEADERS,
    )
    assert correction.status_code == 200
    detail = (await client.get(f"/api/players/{home.id}")).json()
    assert detail["elo_rating"] == 1006
    assert [entry["rating_after"] for entry in reversed(detail["elo_history"])] == [968, 1006]

    cancellation = await client.patch(
        f"/api/matches/{january.json()['id']}",
        json={"status": "cancelled"},
        headers=ADMIN_HEADERS,
    )
    assert cancellation.status_code == 200
    detail = (await client.get(f"/api/players/{home.id}")).json()
    assert detail["elo_rating"] == 1032
    assert len(detail["elo_history"]) == 1

    deletion = await client.delete(
        f"/api/matches/{february.json()['id']}",
        headers=ADMIN_HEADERS,
    )
    assert deletion.status_code == 204
    detail = (await client.get(f"/api/players/{home.id}")).json()
    assert detail["elo_rating"] == 1000
    assert detail["elo_history"] == []


async def test_completed_match_requires_a_timezone_aware_completion_time(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, away = await _league(db_session)
    base = {
        "season_id": str(season.id),
        "home_player_id": str(home.id),
        "away_player_id": str(away.id),
        "stage": "group",
        "status": "completed",
        "winner_id": str(home.id),
    }

    missing = await client.post("/api/matches", json=base, headers=ADMIN_HEADERS)
    naive = await client.post(
        "/api/matches",
        json={**base, "completed_at": "2024-01-01T12:00:00"},
        headers=ADMIN_HEADERS,
    )

    assert missing.status_code == 422
    assert naive.status_code == 422


async def test_legacy_game_timestamp_falls_back_to_parent_chronology(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, away = await _league(db_session)
    early = Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        winner_id=home.id,
        status=MatchStatus.COMPLETED,
        stage=MatchStage.GROUP,
        completed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    late = Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        winner_id=home.id,
        status=MatchStatus.COMPLETED,
        stage=MatchStage.GROUP,
        completed_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
    )
    db_session.add_all([early, late])
    await db_session.flush()
    db_session.add_all(
        [
            MatchGame(match_id=early.id, game_number=1, winner_id=home.id),
            MatchGame(
                match_id=late.id,
                game_number=1,
                winner_id=home.id,
                completed_at=late.completed_at,
            ),
        ]
    )
    await recalculate_elo_ratings(db_session)
    await db_session.commit()

    history = (await client.get(f"/api/players/{home.id}")).json()["elo_history"]
    by_match = {entry["match_id"]: entry for entry in history}
    assert by_match[str(early.id)]["rating_before"] == 1000
    assert by_match[str(late.id)]["rating_before"] == by_match[str(early.id)]["rating_after"]


async def test_same_time_games_use_stable_series_and_game_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, away = await _league(db_session)
    when = datetime(2024, 1, 1, tzinfo=timezone.utc)
    first = Match(
        id=UUID("aaaaaaaa-0000-4000-8000-000000000001"),
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        winner_id=home.id,
        status=MatchStatus.COMPLETED,
        stage=MatchStage.GROUP,
        completed_at=when,
    )
    second = Match(
        id=UUID("aaaaaaaa-0000-4000-8000-000000000002"),
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        winner_id=away.id,
        status=MatchStatus.COMPLETED,
        stage=MatchStage.GROUP,
        completed_at=when,
    )
    db_session.add_all([second, first])
    await db_session.flush()
    db_session.add_all(
        [
            MatchGame(
                id=UUID("bbbbbbbb-0000-4000-8000-000000000001"),
                match_id=first.id,
                game_number=1,
                winner_id=home.id,
                completed_at=when,
            ),
            MatchGame(
                id=UUID("bbbbbbbb-0000-4000-8000-000000000002"),
                match_id=second.id,
                game_number=1,
                winner_id=away.id,
                completed_at=when,
            ),
        ]
    )
    await recalculate_elo_ratings(db_session)
    await db_session.commit()

    first_history = (await client.get(f"/api/players/{home.id}")).json()["elo_history"]
    by_match = {entry["match_id"]: entry for entry in first_history}
    assert by_match[str(first.id)]["rating_before"] == 1000
    assert by_match[str(second.id)]["rating_before"] == by_match[str(first.id)]["rating_after"]

    await recalculate_elo_ratings(db_session)
    await db_session.commit()
    replayed = (await client.get(f"/api/players/{home.id}")).json()["elo_history"]
    assert [
        (event["match_id"], event["rating_before"], event["rating_after"])
        for event in replayed
    ] == [
        (event["match_id"], event["rating_before"], event["rating_after"])
        for event in first_history
    ]
