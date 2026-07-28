from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStage, MatchStatus
from app.models.player import Player
from app.models.season import Season
from app.models.season_entry import SeasonEntry
from tests.conftest import ADMIN_HEADERS


async def test_update_season_champion_reflected_in_response(client: AsyncClient, db_session: AsyncSession) -> None:
    """Regression test: PATCHing champion_id on a season already loaded in this
    request (the router fetches it before updating) must return the new
    champion, not whatever `champion` was at load time."""
    season = Season(name="Champion Update Season", start_date=date(2024, 1, 1))
    player = Player(username="NewChampionTrainer")
    db_session.add_all([season, player])
    await db_session.commit()

    response = await client.patch(
        f"/api/seasons/{season.id}", json={"champion_id": str(player.id)}, headers=ADMIN_HEADERS
    )

    assert response.status_code == 200
    data = response.json()
    assert data["champion"] is not None
    assert data["champion"]["id"] == str(player.id)


async def test_search_seasons_case_insensitive(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Season(name="Alpha Cup", start_date=date(2024, 1, 1)),
            Season(name="Beta League", start_date=date(2023, 1, 1)),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/seasons", params={"q": "alpha"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Alpha Cup"


async def test_list_seasons_orders_newest_first(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Season(name="Older Season", start_date=date(2023, 1, 1)),
            Season(name="Newer Season", start_date=date(2024, 1, 1)),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/seasons")

    assert response.status_code == 200
    data = response.json()
    assert [s["name"] for s in data] == ["Newer Season", "Older Season"]


async def test_get_season_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/seasons/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_list_roster_includes_entry_ids_and_tiebreaker(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = Season(name="Roster Listing Season", start_date=date(2024, 1, 1))
    player = Player(username="RosterListingTrainer")
    db_session.add_all([season, player])
    await db_session.flush()
    entry = SeasonEntry(season_id=season.id, player_id=player.id, group_label="A", tiebreaker_value=1.5)
    db_session.add(entry)
    await db_session.commit()

    response = await client.get(f"/api/seasons/{season.id}/roster")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(entry.id)
    assert data[0]["player"]["username"] == "RosterListingTrainer"
    assert data[0]["group_label"] == "A"
    assert data[0]["tiebreaker_value"] == 1.5


async def test_list_roster_season_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/seasons/00000000-0000-0000-0000-000000000000/roster")
    assert response.status_code == 404


async def test_season_standings_use_only_completed_group_matches(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = Season(name="Standings Season", start_date=date(2024, 1, 1))
    alice = Player(username="AliceStandings")
    bob = Player(username="BobStandings")
    carol = Player(username="CarolStandings")
    db_session.add_all([season, alice, bob, carol])
    await db_session.flush()

    db_session.add_all(
        [
            SeasonEntry(season_id=season.id, player_id=alice.id),
            SeasonEntry(season_id=season.id, player_id=bob.id),
            SeasonEntry(season_id=season.id, player_id=carol.id),
            Match(
                season_id=season.id, home_player_id=alice.id, away_player_id=bob.id,
                winner_id=alice.id, status=MatchStatus.COMPLETED, stage=MatchStage.GROUP,
                home_score=2, away_score=0,
            ),
            # scheduled - should not count toward standings
            Match(
                season_id=season.id, home_player_id=bob.id, away_player_id=carol.id,
                status=MatchStatus.SCHEDULED, stage=MatchStage.GROUP,
            ),
            # playoff match - should not count toward group standings
            Match(
                season_id=season.id, home_player_id=alice.id, away_player_id=carol.id,
                winner_id=carol.id, status=MatchStatus.COMPLETED, stage=MatchStage.PLAYOFFS,
                home_score=0, away_score=2,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/seasons/{season.id}")

    assert response.status_code == 200
    standings = response.json()["standings"][0]["standings"]
    by_username = {entry["player"]["username"]: entry for entry in standings}
    assert by_username["AliceStandings"]["wins"] == 1
    assert by_username["AliceStandings"]["losses"] == 0
    assert by_username["BobStandings"]["wins"] == 0
    assert by_username["BobStandings"]["losses"] == 1
    assert by_username["CarolStandings"]["wins"] == 0
    assert by_username["CarolStandings"]["losses"] == 0


async def test_playoff_bracket_ordering(client: AsyncClient, db_session: AsyncSession) -> None:
    season = Season(name="Bracket Season", start_date=date(2024, 1, 1))
    p1 = Player(username="BracketP1")
    p2 = Player(username="BracketP2")
    p3 = Player(username="BracketP3")
    p4 = Player(username="BracketP4")
    db_session.add_all([season, p1, p2, p3, p4])
    await db_session.flush()

    db_session.add_all(
        [
            Match(
                season_id=season.id, home_player_id=p1.id, away_player_id=p2.id, winner_id=p1.id,
                status=MatchStatus.COMPLETED, stage=MatchStage.PLAYOFFS,
                round_label="Final", round_order=2, bracket_order=1,
            ),
            Match(
                season_id=season.id, home_player_id=p3.id, away_player_id=p4.id, winner_id=p4.id,
                status=MatchStatus.COMPLETED, stage=MatchStage.PLAYOFFS,
                round_label="Semifinal", round_order=1, bracket_order=2,
            ),
            Match(
                season_id=season.id, home_player_id=p1.id, away_player_id=p3.id, winner_id=p1.id,
                status=MatchStatus.COMPLETED, stage=MatchStage.PLAYOFFS,
                round_label="Semifinal", round_order=1, bracket_order=1,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/seasons/{season.id}")

    assert response.status_code == 200
    bracket = response.json()["bracket"]
    assert [r["round_label"] for r in bracket] == ["Semifinal", "Final"]
    semifinal_matches = bracket[0]["matches"]
    assert [m["home_player"]["username"] for m in semifinal_matches] == ["BracketP1", "BracketP3"]


async def test_set_draft_pool_accepts_alternate_forms(client: AsyncClient, db_session: AsyncSession) -> None:
    """Alternate forms are stored by PokeAPI id, which runs to 10000+ for megas,
    regional variants and Gigantamax - nothing may cap pokeapi_id to the 1-1025
    national dex range."""
    season = Season(name="Draft Forms Season", start_date=date(2024, 1, 1))
    player = Player(username="DraftFormsTrainer")
    db_session.add_all([season, player])
    await db_session.flush()
    entry = SeasonEntry(season_id=season.id, player_id=player.id)
    db_session.add(entry)
    await db_session.commit()

    response = await client.put(
        f"/api/seasons/{season.id}/roster/{entry.id}/pokemon",
        json={
            "pokemon": [
                {"pokeapi_id": 6, "species_name": "Charizard"},
                {"pokeapi_id": 10034, "species_name": "Charizard (Mega X)"},
                {"pokeapi_id": 10100, "species_name": "Raichu (Alolan)"},
                {"pokeapi_id": 10229, "species_name": "Growlithe (Hisuian)"},
            ]
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    pool = response.json()["pokemon"]
    assert [p["pokeapi_id"] for p in pool] == [6, 10034, 10100, 10229]
    # Slots follow list order, so the pool keeps the draft order it was sent in.
    assert [p["slot"] for p in pool] == [0, 1, 2, 3]
    assert pool[1]["species_name"] == "Charizard (Mega X)"


async def test_a_form_is_distinct_from_its_base_species(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Charizard and Mega Charizard X are different ids, so drafting both is not
    a duplicate."""
    season = Season(name="Distinct Forms Season", start_date=date(2024, 1, 1))
    player = Player(username="DistinctFormsTrainer")
    db_session.add_all([season, player])
    await db_session.flush()
    entry = SeasonEntry(season_id=season.id, player_id=player.id)
    db_session.add(entry)
    await db_session.commit()

    response = await client.put(
        f"/api/seasons/{season.id}/roster/{entry.id}/pokemon",
        json={
            "pokemon": [
                {"pokeapi_id": 6, "species_name": "Charizard"},
                {"pokeapi_id": 10034, "species_name": "Charizard (Mega X)"},
            ]
        },
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200

    # The same id twice is still rejected.
    duplicate = await client.put(
        f"/api/seasons/{season.id}/roster/{entry.id}/pokemon",
        json={
            "pokemon": [
                {"pokeapi_id": 10034, "species_name": "Charizard (Mega X)"},
                {"pokeapi_id": 10034, "species_name": "Charizard (Mega X)"},
            ]
        },
        headers=ADMIN_HEADERS,
    )
    assert duplicate.status_code == 422
