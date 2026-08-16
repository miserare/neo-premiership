"""The unified PUT /api/matches/{id}/result endpoint."""

from datetime import date, datetime, timezone

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elo import EloRatingEvent
from app.models.match import Match, MatchStage, MatchStatus
from app.models.match_game import MatchGame
from app.models.pokemon import MatchPokemon
from tests.conftest import ADMIN_HEADERS, make_player, make_season

COMPLETED_AT = "2025-03-01T20:00:00Z"


async def _match(db_session: AsyncSession, suffix: str = "") -> dict:
    season = make_season(name=f"Result Season {suffix}", start_date=date(2025, 1, 1))
    home = make_player(username=f"Result Home {suffix}")
    away = make_player(username=f"Result Away {suffix}")
    db_session.add_all([season, home, away])
    await db_session.flush()
    match = Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        stage=MatchStage.GROUP,
        status=MatchStatus.SCHEDULED,
        scheduled_at=datetime(2025, 3, 1, 19, 0, tzinfo=timezone.utc),
    )
    db_session.add(match)
    await db_session.commit()
    return {"match": match, "home": home, "away": away, "season": season}


def _result_body(built: dict, **overrides) -> dict:
    body = {
        "status": "completed",
        "completed_at": COMPLETED_AT,
        "games": [
            {"game_number": 1, "winner_id": str(built["home"].id), "replay_url": "https://example.invalid/g1"},
            {"game_number": 2, "winner_id": str(built["away"].id), "replay_url": "https://example.invalid/g2"},
            {"game_number": 3, "winner_id": str(built["home"].id), "replay_url": "https://example.invalid/g3"},
        ],
        "home_team": [{"pokeapi_id": 6, "species_name": "charizard"}],
        "away_team": [{"pokeapi_id": 9, "species_name": "blastoise"}],
        "youtube_url": "https://example.invalid/vod",
    }
    body.update(overrides)
    return body


# ------------------------------------------------------------- happy path


async def test_one_request_saves_games_teams_and_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    response = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(built),
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert [game["game_number"] for game in body["games"]] == [1, 2, 3]
    assert [p["species_name"] for p in body["home_team"]] == ["charizard"]
    assert [p["species_name"] for p in body["away_team"]] == ["blastoise"]
    assert body["youtube_url"] == "https://example.invalid/vod"


async def test_the_series_score_and_winner_are_derived_not_supplied(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Nothing in the request says who won the match or what the score was."""
    built = await _match(db_session)

    body = (
        await client.put(
            f"/api/matches/{built['match'].id}/result",
            json=_result_body(built),
            headers=ADMIN_HEADERS,
        )
    ).json()

    assert body["series"] == {"home_wins": 2, "away_wins": 1, "game_count": 3}
    assert body["home_score"] == 2
    assert body["away_score"] == 1
    assert body["winner_id"] == str(built["home"].id)


async def test_an_away_series_win_derives_the_away_player(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)
    away = str(built["away"].id)

    body = (
        await client.put(
            f"/api/matches/{built['match'].id}/result",
            json=_result_body(
                built,
                games=[
                    {"game_number": 1, "winner_id": away},
                    {"game_number": 2, "winner_id": away},
                ],
            ),
            headers=ADMIN_HEADERS,
        )
    ).json()

    assert body["winner_id"] == away
    assert body["home_score"] == 0
    assert body["away_score"] == 2


async def test_saving_a_result_replaces_the_previous_one(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)
    await client.put(
        f"/api/matches/{built['match'].id}/result", json=_result_body(built), headers=ADMIN_HEADERS
    )

    corrected = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(
            built,
            games=[
                {"game_number": 1, "winner_id": str(built["away"].id)},
                {"game_number": 2, "winner_id": str(built["away"].id)},
            ],
            home_team=[{"pokeapi_id": 25, "species_name": "pikachu"}],
        ),
        headers=ADMIN_HEADERS,
    )

    assert corrected.json()["series"] == {"home_wins": 0, "away_wins": 2, "game_count": 2}
    assert corrected.json()["winner_id"] == str(built["away"].id)
    assert [p["species_name"] for p in corrected.json()["home_team"]] == ["pikachu"]
    # No orphaned rows from the previous save.
    assert (
        await db_session.scalar(
            select(func.count(MatchGame.id)).where(MatchGame.match_id == built["match"].id)
        )
    ) == 2


async def test_an_in_progress_series_can_be_saved_as_scheduled(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    body = (
        await client.put(
            f"/api/matches/{built['match'].id}/result",
            json=_result_body(
                built,
                status="scheduled",
                completed_at=None,
                games=[{"game_number": 1, "winner_id": str(built["home"].id)}],
            ),
            headers=ADMIN_HEADERS,
        )
    ).json()

    assert body["status"] == "scheduled"
    # The games are recorded, but a match still in progress has no winner.
    assert body["series"]["game_count"] == 1
    assert body["winner_id"] is None


async def test_recorded_teams_survive_an_unrelated_match_edit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Editing scheduling details must not wipe what the players brought."""
    built = await _match(db_session)
    await client.put(
        f"/api/matches/{built['match'].id}/result", json=_result_body(built), headers=ADMIN_HEADERS
    )

    edited = await client.patch(
        f"/api/matches/{built['match'].id}",
        json={"round_label": "Group B - Matchday 4"},
        headers=ADMIN_HEADERS,
    )

    assert edited.json()["round_label"] == "Group B - Matchday 4"
    assert [p["species_name"] for p in edited.json()["home_team"]] == ["charizard"]
    assert len(edited.json()["games"]) == 3


# ---------------------------------------------------------------- validation


async def test_a_level_series_cannot_be_marked_completed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    response = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(
            built,
            games=[
                {"game_number": 1, "winner_id": str(built["home"].id)},
                {"game_number": 2, "winner_id": str(built["away"].id)},
            ],
        ),
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422
    assert "level at 1-1" in response.json()["detail"]


async def test_a_completed_match_needs_at_least_one_game(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    response = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(built, games=[]),
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422


async def test_a_completed_match_needs_a_timezone_aware_timestamp(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    missing = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(built, completed_at=None),
        headers=ADMIN_HEADERS,
    )
    assert missing.status_code == 422

    naive = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(built, completed_at="2025-03-01T20:00:00"),
        headers=ADMIN_HEADERS,
    )
    assert naive.status_code == 422


async def test_duplicate_game_numbers_are_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    response = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(
            built,
            games=[
                {"game_number": 1, "winner_id": str(built["home"].id)},
                {"game_number": 1, "winner_id": str(built["home"].id)},
            ],
        ),
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422


async def test_a_game_winner_must_be_a_participant(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)
    outsider = make_player(username="Result Outsider")
    db_session.add(outsider)
    await db_session.commit()

    response = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(built, games=[{"game_number": 1, "winner_id": str(outsider.id)}]),
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422
    assert "home or away player" in response.json()["detail"]


async def test_the_same_pokemon_cannot_appear_twice_on_one_team(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    response = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(
            built,
            home_team=[
                {"pokeapi_id": 6, "species_name": "charizard"},
                {"pokeapi_id": 6, "species_name": "charizard"},
            ],
        ),
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422


async def test_cancelling_still_goes_through_match_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    refused = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(built, status="cancelled"),
        headers=ADMIN_HEADERS,
    )
    assert refused.status_code == 422

    cancelled = await client.patch(
        f"/api/matches/{built['match'].id}", json={"status": "cancelled"}, headers=ADMIN_HEADERS
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


async def test_saving_a_result_requires_an_administrator(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    response = await client.put(f"/api/matches/{built['match'].id}/result", json=_result_body(built))
    assert response.status_code == 401


async def test_an_unknown_match_is_a_404(client: AsyncClient) -> None:
    response = await client.put(
        "/api/matches/00000000-0000-4000-8000-000000000000/result",
        json={"status": "scheduled", "games": []},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 404


# --------------------------------------------------------------- transaction


async def test_a_rejected_result_changes_nothing_at_all(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The whole point of doing this in one transaction: a save that fails
    part-way must not leave the old games deleted or the teams half-written."""
    built = await _match(db_session)
    await client.put(
        f"/api/matches/{built['match'].id}/result", json=_result_body(built), headers=ADMIN_HEADERS
    )

    outsider = make_player(username="Rollback Outsider")
    db_session.add(outsider)
    await db_session.commit()

    rejected = await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(
            built,
            games=[
                {"game_number": 1, "winner_id": str(built["home"].id)},
                # Invalid: rejected after the payload has otherwise validated.
                {"game_number": 2, "winner_id": str(outsider.id)},
            ],
            home_team=[{"pokeapi_id": 1, "species_name": "bulbasaur"}],
        ),
        headers=ADMIN_HEADERS,
    )
    assert rejected.status_code == 422

    after = (await client.get(f"/api/matches/{built['match'].id}")).json()
    assert len(after["games"]) == 3
    assert after["series"] == {"home_wins": 2, "away_wins": 1, "game_count": 3}
    assert [p["species_name"] for p in after["home_team"]] == ["charizard"]
    assert after["status"] == "completed"


async def test_a_level_series_leaves_the_previous_result_intact(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)
    await client.put(
        f"/api/matches/{built['match'].id}/result", json=_result_body(built), headers=ADMIN_HEADERS
    )

    await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(
            built,
            games=[
                {"game_number": 1, "winner_id": str(built["home"].id)},
                {"game_number": 2, "winner_id": str(built["away"].id)},
            ],
        ),
        headers=ADMIN_HEADERS,
    )

    after = (await client.get(f"/api/matches/{built['match'].id}")).json()
    assert after["winner_id"] == str(built["home"].id)
    assert len(after["games"]) == 3


async def test_teams_are_not_left_behind_by_a_failed_save(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)
    await client.put(
        f"/api/matches/{built['match'].id}/result", json=_result_body(built), headers=ADMIN_HEADERS
    )

    outsider = make_player(username="Team Rollback Outsider")
    db_session.add(outsider)
    await db_session.commit()

    await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(
            built,
            games=[{"game_number": 1, "winner_id": str(outsider.id)}],
            home_team=[{"pokeapi_id": 1, "species_name": "bulbasaur"}],
            away_team=[{"pokeapi_id": 4, "species_name": "charmander"}],
        ),
        headers=ADMIN_HEADERS,
    )

    count = await db_session.scalar(
        select(func.count(MatchPokemon.id)).where(MatchPokemon.match_id == built["match"].id)
    )
    assert count == 2


# ---------------------------------------------------------------------- elo


async def test_elo_is_written_once_the_result_lands(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)

    await client.put(
        f"/api/matches/{built['match'].id}/result", json=_result_body(built), headers=ADMIN_HEADERS
    )

    home = (await client.get(f"/api/players/{built['home'].id}")).json()
    assert home["elo_rating"] == 1032
    assert len(home["elo_history"]) == 1
    assert home["elo_history"][0]["rating_change"] == 32


async def test_correcting_a_result_rebuilds_elo(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The reason Elo is recalculated once after the whole transaction: the
    corrected match has to replace the old one, not stack on top of it."""
    built = await _match(db_session)
    await client.put(
        f"/api/matches/{built['match'].id}/result", json=_result_body(built), headers=ADMIN_HEADERS
    )

    await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(
            built,
            games=[
                {"game_number": 1, "winner_id": str(built["away"].id)},
                {"game_number": 2, "winner_id": str(built["away"].id)},
            ],
        ),
        headers=ADMIN_HEADERS,
    )

    home = (await client.get(f"/api/players/{built['home'].id}")).json()
    away = (await client.get(f"/api/players/{built['away'].id}")).json()

    # The result flipped, so the ratings flip with it - not 1032 minus something.
    assert home["elo_rating"] == 968
    assert away["elo_rating"] == 1032
    assert len(home["elo_history"]) == 1
    assert home["elo_history"][0]["rating_change"] == -32


async def test_correcting_an_earlier_result_replays_every_later_match(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = make_season(name="Chronology Season", start_date=date(2025, 1, 1))
    alice = make_player(username="Chrono Alice")
    bob = make_player(username="Chrono Bob")
    db_session.add_all([season, alice, bob])
    await db_session.flush()
    first = Match(
        season_id=season.id,
        home_player_id=alice.id,
        away_player_id=bob.id,
        stage=MatchStage.GROUP,
        status=MatchStatus.SCHEDULED,
    )
    second = Match(
        season_id=season.id,
        home_player_id=alice.id,
        away_player_id=bob.id,
        stage=MatchStage.GROUP,
        status=MatchStatus.SCHEDULED,
    )
    db_session.add_all([first, second])
    await db_session.commit()

    for match, when in ((first, "2025-01-10T20:00:00Z"), (second, "2025-02-10T20:00:00Z")):
        await client.put(
            f"/api/matches/{match.id}/result",
            json={
                "status": "completed",
                "completed_at": when,
                "games": [{"game_number": 1, "winner_id": str(alice.id)}],
                "home_team": [],
                "away_team": [],
            },
            headers=ADMIN_HEADERS,
        )

    before = (await client.get(f"/api/players/{alice.id}")).json()
    assert [event["rating_change"] for event in before["elo_history"]] == [26, 32]

    # Flip the *earlier* match. The later one must be recomputed from the new
    # ratings, not left with the numbers it was first given.
    await client.put(
        f"/api/matches/{first.id}/result",
        json={
            "status": "completed",
            "completed_at": "2025-01-10T20:00:00Z",
            "games": [{"game_number": 1, "winner_id": str(bob.id)}],
            "home_team": [],
            "away_team": [],
        },
        headers=ADMIN_HEADERS,
    )

    after = (await client.get(f"/api/players/{alice.id}")).json()
    # Newest first: the February win now starts from 968, not 1032.
    assert [event["rating_before"] for event in after["elo_history"]] == [968, 1000]
    assert after["elo_rating"] == 968 + after["elo_history"][0]["rating_change"]


async def test_a_scheduled_result_removes_the_match_from_elo(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _match(db_session)
    await client.put(
        f"/api/matches/{built['match'].id}/result", json=_result_body(built), headers=ADMIN_HEADERS
    )

    await client.put(
        f"/api/matches/{built['match'].id}/result",
        json=_result_body(built, status="scheduled", completed_at=None),
        headers=ADMIN_HEADERS,
    )

    home = (await client.get(f"/api/players/{built['home'].id}")).json()
    assert home["elo_rating"] == 1000
    assert home["elo_history"] == []
    assert (await db_session.scalar(select(func.count(EloRatingEvent.id)))) == 0
