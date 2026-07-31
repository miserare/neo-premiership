from datetime import date, datetime, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStage, MatchStatus
from app.models.player import Player
from app.models.season import Season
from app.models.season_entry import SeasonEntry
from tests.conftest import ADMIN_HEADERS


async def _league(
    db_session: AsyncSession,
) -> tuple[Season, Player, Player, SeasonEntry, SeasonEntry]:
    season = Season(name="Ownership History Season", start_date=date(2024, 1, 1))
    home = Player(username="OwnershipHome")
    away = Player(username="OwnershipAway")
    db_session.add_all([season, home, away])
    await db_session.flush()
    home_entry = SeasonEntry(season_id=season.id, player_id=home.id)
    away_entry = SeasonEntry(season_id=season.id, player_id=away.id)
    db_session.add_all([home_entry, away_entry])
    await db_session.commit()
    return season, home, away, home_entry, away_entry


async def test_roster_change_archives_ownership_without_changing_match_snapshot(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, away, home_entry, _ = await _league(db_session)
    drafted_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    dropped_at = datetime(2024, 3, 1, tzinfo=timezone.utc)

    drafted = await client.put(
        f"/api/seasons/{season.id}/roster/{home_entry.id}/pokemon",
        json={
            "effective_at": drafted_at.isoformat(),
            "change_type": "draft",
            "pokemon": [
                {"pokeapi_id": 6, "species_name": "Charizard"},
                {"pokeapi_id": 25, "species_name": "Pikachu"},
            ],
        },
        headers=ADMIN_HEADERS,
    )
    assert drafted.status_code == 200

    match = Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        winner_id=home.id,
        status=MatchStatus.COMPLETED,
        stage=MatchStage.GROUP,
        completed_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
    )
    db_session.add(match)
    await db_session.commit()
    team = await client.put(
        f"/api/matches/{match.id}/teams/{home.id}",
        json={"pokemon": [{"pokeapi_id": 6, "species_name": "Charizard"}]},
        headers=ADMIN_HEADERS,
    )
    assert team.status_code == 200

    changed = await client.put(
        f"/api/seasons/{season.id}/roster/{home_entry.id}/pokemon",
        json={
            "effective_at": dropped_at.isoformat(),
            "change_type": "free_agency",
            "pokemon": [
                {"pokeapi_id": 25, "species_name": "Pikachu"},
                {"pokeapi_id": 9, "species_name": "Blastoise"},
            ],
        },
        headers=ADMIN_HEADERS,
    )

    assert changed.status_code == 200
    roster = changed.json()
    assert [pokemon["species_name"] for pokemon in roster["pokemon"]] == ["Pikachu", "Blastoise"]
    assert roster["pokemon"][0]["acquisition_type"] == "draft"
    assert roster["pokemon"][1]["acquisition_type"] == "free_agency"
    assert [pokemon["species_name"] for pokemon in roster["former_pokemon"]] == ["Charizard"]
    assert roster["former_pokemon"][0]["release_type"] == "free_agency"
    released_at = datetime.fromisoformat(roster["former_pokemon"][0]["released_at"])
    if released_at.tzinfo is None:  # SQLite drops timezone information in tests.
        released_at = released_at.replace(tzinfo=timezone.utc)
    assert released_at == dropped_at

    historical_match = await client.get(f"/api/matches/{match.id}")
    assert historical_match.status_code == 200
    assert [pokemon["species_name"] for pokemon in historical_match.json()["home_team"]] == [
        "Charizard"
    ]


async def test_dropped_pokemon_can_be_backfilled_only_for_a_match_during_its_tenure(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, away, home_entry, _ = await _league(db_session)
    await client.put(
        f"/api/seasons/{season.id}/roster/{home_entry.id}/pokemon",
        json={
            "effective_at": "2024-01-01T00:00:00Z",
            "change_type": "draft",
            "pokemon": [{"pokeapi_id": 6, "species_name": "Charizard"}],
        },
        headers=ADMIN_HEADERS,
    )
    await client.put(
        f"/api/seasons/{season.id}/roster/{home_entry.id}/pokemon",
        json={
            "effective_at": "2024-03-01T00:00:00Z",
            "change_type": "trade",
            "pokemon": [],
        },
        headers=ADMIN_HEADERS,
    )

    before_drop = Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        winner_id=home.id,
        status=MatchStatus.COMPLETED,
        stage=MatchStage.GROUP,
        completed_at=datetime(2024, 2, 15, tzinfo=timezone.utc),
    )
    after_drop = Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        winner_id=away.id,
        status=MatchStatus.COMPLETED,
        stage=MatchStage.GROUP,
        completed_at=datetime(2024, 3, 15, tzinfo=timezone.utc),
    )
    db_session.add_all([before_drop, after_drop])
    await db_session.commit()

    historical = await client.put(
        f"/api/matches/{before_drop.id}/teams/{home.id}",
        json={"pokemon": [{"pokeapi_id": 6, "species_name": "Charizard"}]},
        headers=ADMIN_HEADERS,
    )
    assert historical.status_code == 200

    impossible = await client.put(
        f"/api/matches/{after_drop.id}/teams/{home.id}",
        json={"pokemon": [{"pokeapi_id": 6, "species_name": "Charizard"}]},
        headers=ADMIN_HEADERS,
    )
    assert impossible.status_code == 422
    assert "not owned by this player at the match time" in impossible.json()["detail"]


async def test_trade_records_release_and_acquisition_on_opposite_rosters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season, home, _, home_entry, away_entry = await _league(db_session)
    await client.put(
        f"/api/seasons/{season.id}/roster/{home_entry.id}/pokemon",
        json={
            "effective_at": "2024-01-01T00:00:00Z",
            "change_type": "draft",
            "pokemon": [{"pokeapi_id": 6, "species_name": "Charizard"}],
        },
        headers=ADMIN_HEADERS,
    )

    trade_time = "2024-03-01T12:00:00Z"
    released = await client.put(
        f"/api/seasons/{season.id}/roster/{home_entry.id}/pokemon",
        json={"effective_at": trade_time, "change_type": "trade", "pokemon": []},
        headers=ADMIN_HEADERS,
    )
    acquired = await client.put(
        f"/api/seasons/{season.id}/roster/{away_entry.id}/pokemon",
        json={
            "effective_at": trade_time,
            "change_type": "trade",
            "pokemon": [{"pokeapi_id": 6, "species_name": "Charizard"}],
        },
        headers=ADMIN_HEADERS,
    )

    assert released.status_code == 200
    assert released.json()["former_pokemon"][0]["release_type"] == "trade"
    assert acquired.status_code == 200
    assert acquired.json()["pokemon"][0]["acquisition_type"] == "trade"
