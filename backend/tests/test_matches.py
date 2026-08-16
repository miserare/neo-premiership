from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStage, MatchStatus
from app.models.player import Player
from app.models.season import Season
from tests.conftest import ADMIN_HEADERS, make_player, make_season


async def _make_match(db_session: AsyncSession, **match_kwargs) -> tuple[Season, Player, Player, Match]:
    suffix = str(abs(hash(str(match_kwargs))) % 100000)
    season = make_season(name=f"Series Season {suffix}", start_date=date(2024, 1, 1))
    home = make_player(username=f"HomeTrainer{suffix}")
    away = make_player(username=f"AwayTrainer{suffix}")
    db_session.add_all([season, home, away])
    await db_session.flush()

    match_kwargs.setdefault("stage", MatchStage.PLAYOFFS)
    match_kwargs.setdefault("status", MatchStatus.SCHEDULED)
    match = Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        **match_kwargs,
    )
    db_session.add(match)
    await db_session.commit()
    return season, home, away, match


async def test_list_matches_for_season(client: AsyncClient, db_session: AsyncSession) -> None:
    season, _, _, match = await _make_match(db_session)

    response = await client.get("/api/matches", params={"season_id": str(season.id)})

    assert response.status_code == 200
    data = response.json()
    assert [m["id"] for m in data] == [str(match.id)]


async def test_list_matches_unknown_season(client: AsyncClient) -> None:
    response = await client.get(
        "/api/matches", params={"season_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert response.status_code == 404


async def test_set_games_derives_series_score(client: AsyncClient, db_session: AsyncSession) -> None:
    _, home, away, match = await _make_match(db_session)

    response = await client.put(
        f"/api/matches/{match.id}/games",
        json={
            "games": [
                {"game_number": 1, "winner_id": str(home.id), "replay_url": "https://replay.test/g1"},
                {"game_number": 2, "winner_id": str(away.id), "replay_url": "https://replay.test/g2"},
                {"game_number": 3, "winner_id": str(home.id), "replay_url": "https://replay.test/g3"},
            ]
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["series"] == {"home_series_wins": 2, "away_series_wins": 1, "game_count": 3, "wins_required": 1}
    assert [g["game_number"] for g in data["games"]] == [1, 2, 3]
    assert data["games"][0]["replay_url"] == "https://replay.test/g1"


async def test_set_games_replaces_previous_series(client: AsyncClient, db_session: AsyncSession) -> None:
    """A second PUT must not leave the first PUT's games behind - the response
    is re-read with populate_existing for exactly this reason."""
    _, home, _, match = await _make_match(db_session)

    await client.put(
        f"/api/matches/{match.id}/games",
        json={"games": [{"game_number": i, "winner_id": str(home.id)} for i in (1, 2, 3)]},
        headers=ADMIN_HEADERS,
    )
    response = await client.put(
        f"/api/matches/{match.id}/games",
        json={"games": [{"game_number": 1, "winner_id": str(home.id)}]},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["series"]["game_count"] == 1
    assert len(data["games"]) == 1


async def test_set_games_rejects_non_participant_winner(client: AsyncClient, db_session: AsyncSession) -> None:
    _, _, _, match = await _make_match(db_session)
    outsider = make_player(username="OutsiderTrainer")
    db_session.add(outsider)
    await db_session.commit()

    response = await client.put(
        f"/api/matches/{match.id}/games",
        json={"games": [{"game_number": 1, "winner_id": str(outsider.id)}]},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422


async def test_set_games_rejects_duplicate_game_numbers(client: AsyncClient, db_session: AsyncSession) -> None:
    _, home, _, match = await _make_match(db_session)

    response = await client.put(
        f"/api/matches/{match.id}/games",
        json={
            "games": [
                {"game_number": 1, "winner_id": str(home.id)},
                {"game_number": 1, "winner_id": str(home.id)},
            ]
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422


async def test_set_games_requires_admin(client: AsyncClient, db_session: AsyncSession) -> None:
    _, home, _, match = await _make_match(db_session)

    response = await client.put(
        f"/api/matches/{match.id}/games",
        json={"games": [{"game_number": 1, "winner_id": str(home.id)}]},
    )

    assert response.status_code == 401


async def test_legacy_replay_url_surfaces_as_a_single_game(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Matches recorded before the series model still render as one game, so
    consumers never have to special-case the old single-replay shape."""
    _, home, _, match = await _make_match(db_session, replay_url="https://replay.test/legacy")
    match.winner_id = home.id
    db_session.add(match)
    await db_session.commit()

    response = await client.get(f"/api/matches/{match.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["games"]) == 1
    assert data["games"][0]["id"] is None  # synthesized, not a stored row
    assert data["games"][0]["replay_url"] == "https://replay.test/legacy"
    assert data["series"] == {"home_series_wins": 1, "away_series_wins": 0, "game_count": 1, "wins_required": 1}


async def test_set_match_team(client: AsyncClient, db_session: AsyncSession) -> None:
    _, home, away, match = await _make_match(db_session)

    response = await client.put(
        f"/api/matches/{match.id}/teams/{home.id}",
        json={"pokemon": [{"pokeapi_id": 6, "species_name": "Charizard"}]},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert [p["species_name"] for p in data["home_team"]] == ["Charizard"]
    assert data["away_team"] == []

    # Setting the away team must leave the home team alone.
    response = await client.put(
        f"/api/matches/{match.id}/teams/{away.id}",
        json={"pokemon": [{"pokeapi_id": 9, "species_name": "Blastoise"}]},
        headers=ADMIN_HEADERS,
    )
    data = response.json()
    assert [p["species_name"] for p in data["home_team"]] == ["Charizard"]
    assert [p["species_name"] for p in data["away_team"]] == ["Blastoise"]


async def test_set_match_team_rejects_non_participant(client: AsyncClient, db_session: AsyncSession) -> None:
    _, _, _, match = await _make_match(db_session)
    outsider = make_player(username="BenchTrainer")
    db_session.add(outsider)
    await db_session.commit()

    response = await client.put(
        f"/api/matches/{match.id}/teams/{outsider.id}",
        json={"pokemon": [{"pokeapi_id": 25, "species_name": "Pikachu"}]},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422
