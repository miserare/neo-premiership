from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player
from app.models.season import Season
from tests.conftest import ADMIN_HEADERS


async def _league(db_session: AsyncSession, *, home_elo: int = 1000) -> tuple[Season, Player, Player]:
    season = Season(name="Elo Test Season", start_date=date(2024, 1, 1))
    home = Player(
        username="EloHome",
        initial_elo_rating=home_elo,
        elo_rating=home_elo,
    )
    away = Player(username="EloAway")
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
    assert detail["elo_history"] == [
        {
            "match_id": response.json()["id"],
            "opponent_id": str(away.id),
            "opponent_username": away.username,
            "occurred_at": "2024-01-01T12:00:00",
            "result": 1,
            "expected_score": 0.5,
            "rating_before": 1000,
            "rating_after": 1032,
            "rating_change": 32,
        }
    ]


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
