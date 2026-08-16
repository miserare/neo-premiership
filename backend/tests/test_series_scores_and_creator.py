from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStage, MatchStatus
from app.models.season_entry import SeasonEntry
from tests.conftest import ADMIN_HEADERS, make_player, make_season


async def _fixture(db: AsyncSession, suffix: str = ""):
    season = make_season(name=f"Score Season {suffix}", start_date=date(2026, 1, 1))
    home = make_player(username=f"Score Home {suffix}")
    away = make_player(username=f"Score Away {suffix}")
    db.add_all([season, home, away])
    await db.flush()
    match = Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        stage=MatchStage.GROUP,
        status=MatchStatus.SCHEDULED,
        best_of=1,
    )
    db.add(match)
    await db.commit()
    return match, home, away


def _body(_home, _away, home_score: int, away_score: int, winner_id=None):
    return {
        "status": "completed",
        "best_of": 1,
        "completed_at": "2026-01-02T20:00:00Z",
        "games": [
            {
                "game_number": 1,
                "completed_at": "2026-01-02T20:00:00Z",
                "winner_id": str(winner_id) if winner_id else None,
                "home_pokemon_score": home_score,
                "away_pokemon_score": away_score,
            }
        ],
        "home_team": [],
        "away_team": [],
    }


@pytest.mark.parametrize("score", range(1, 7))
async def test_every_valid_home_pokemon_score_is_accepted(
    score: int, client: AsyncClient, db_session: AsyncSession
) -> None:
    match, home, away = await _fixture(db_session, f"home {score}")
    response = await client.put(
        f"/api/matches/{match.id}/result",
        json=_body(home, away, score, 0, home.id),
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["games"][0]["home_pokemon_score"] == score
    assert response.json()["series"]["home_series_wins"] == 1


@pytest.mark.parametrize("score", range(1, 7))
async def test_every_valid_away_pokemon_score_is_accepted(
    score: int, client: AsyncClient, db_session: AsyncSession
) -> None:
    match, home, away = await _fixture(db_session, f"away {score}")
    response = await client.put(
        f"/api/matches/{match.id}/result",
        json=_body(home, away, 0, score, away.id),
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["games"][0]["away_pokemon_score"] == score


@pytest.mark.parametrize("home_score,away_score", [(0, 0), (2, 1), (6, 3), (7, 0), (-1, 0)])
async def test_invalid_pokemon_scores_are_rejected(
    home_score: int, away_score: int, client: AsyncClient, db_session: AsyncSession
) -> None:
    match, home, away = await _fixture(db_session, f"bad {home_score} {away_score}")
    response = await client.put(
        f"/api/matches/{match.id}/result",
        json=_body(home, away, home_score, away_score),
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422


async def test_winner_must_agree_with_pokemon_score(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    match, home, away = await _fixture(db_session, "winner mismatch")
    response = await client.put(
        f"/api/matches/{match.id}/result",
        json=_body(home, away, 6, 0, away.id),
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422
    assert "inconsistent" in response.json()["detail"]


async def test_six_zero_zero_one_zero_one_is_series_one_two_and_diff_plus_four(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    match, home, away = await _fixture(db_session, "example")
    match.best_of = 3
    db_session.add_all(
        [
            SeasonEntry(season_id=match.season_id, player_id=home.id, group_label="A"),
            SeasonEntry(season_id=match.season_id, player_id=away.id, group_label="A"),
        ]
    )
    await db_session.commit()
    games = [
        (1, home.id, 6, 0),
        (2, away.id, 0, 1),
        (3, away.id, 0, 1),
    ]
    body = {
        "status": "completed", "best_of": 3, "completed_at": "2026-01-02T20:30:00Z",
        "games": [
            {
                "game_number": number,
                "completed_at": f"2026-01-02T20:{number * 10:02d}:00Z",
                "winner_id": str(winner),
                "home_pokemon_score": home_score,
                "away_pokemon_score": away_score,
            }
            for number, winner, home_score, away_score in games
        ],
        "home_team": [], "away_team": [],
    }
    result = await client.put(f"/api/matches/{match.id}/result", json=body, headers=ADMIN_HEADERS)
    assert result.status_code == 200
    assert result.json()["series"]["home_series_wins"] == 1
    assert result.json()["series"]["away_series_wins"] == 2
    assert result.json()["winner_id"] == str(away.id)
    assert sum(g[2] - g[3] for g in games) == 4
    home_detail = (await client.get(f"/api/players/{home.id}")).json()
    assert len(home_detail["elo_history"]) == 3
    season_detail = (await client.get(f"/api/seasons/{match.season_id}")).json()
    standings = {
        entry["player"]["id"]: entry for entry in season_detail["standings"][0]["standings"]
    }
    assert standings[str(home.id)]["wins"] == 0
    assert standings[str(home.id)]["losses"] == 1
    assert standings[str(home.id)]["pokemon_differential"] == 4
    assert standings[str(away.id)]["wins"] == 1
    assert standings[str(away.id)]["pokemon_differential"] == -4


async def test_elo_ignores_pokemon_margin(client: AsyncClient, db_session: AsyncSession) -> None:
    narrow_match, narrow_home, narrow_away = await _fixture(db_session, "narrow margin")
    wide_match, wide_home, wide_away = await _fixture(db_session, "wide margin")

    narrow = await client.put(
        f"/api/matches/{narrow_match.id}/result",
        json=_body(narrow_home, narrow_away, 1, 0, narrow_home.id),
        headers=ADMIN_HEADERS,
    )
    wide = await client.put(
        f"/api/matches/{wide_match.id}/result",
        json=_body(wide_home, wide_away, 6, 0, wide_home.id),
        headers=ADMIN_HEADERS,
    )

    assert narrow.status_code == 200
    assert wide.status_code == 200
    narrow_detail = (await client.get(f"/api/players/{narrow_home.id}")).json()
    wide_detail = (await client.get(f"/api/players/{wide_home.id}")).json()
    assert narrow_detail["elo_history"][0]["rating_change"] == 32
    assert wide_detail["elo_history"][0]["rating_change"] == 32


async def test_a_game_after_the_clinch_is_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    match, home, away = await _fixture(db_session, "post clinch")
    body = {
        "status": "completed", "best_of": 3, "completed_at": "2026-01-02T20:30:00Z",
        "games": [
            {"game_number": number, "completed_at": f"2026-01-02T20:{number * 10:02d}:00Z", "winner_id": str(home.id), "home_pokemon_score": 1, "away_pokemon_score": 0}
            for number in (1, 2, 3)
        ],
        "home_team": [], "away_team": [],
    }
    response = await client.put(f"/api/matches/{match.id}/result", json=body, headers=ADMIN_HEADERS)
    assert response.status_code == 422
    assert "already decided" in response.json()["detail"]


async def test_site_creator_is_public_detail_only_and_unique(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await client.post(
        "/api/players",
        json={"username": "Creator One", "is_site_creator": True},
        headers=ADMIN_HEADERS,
    )
    assert first.status_code == 201
    detail = (await client.get(f"/api/players/{first.json()['id']}")).json()
    assert detail["is_site_creator"] is True
    listing = (await client.get("/api/players")).json()
    assert "is_site_creator" not in listing[0]

    second = await client.post(
        "/api/players",
        json={"username": "Creator Two", "is_site_creator": True},
        headers=ADMIN_HEADERS,
    )
    assert second.status_code == 409


async def test_placeholder_cannot_be_site_creator(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    placeholder = make_player(username="Deleted player", is_placeholder=True, is_active=False)
    db_session.add(placeholder)
    await db_session.commit()

    response = await client.patch(
        f"/api/players/{placeholder.id}",
        json={"is_site_creator": True},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422
    assert "placeholder" in response.json()["detail"].lower()
