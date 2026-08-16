"""The Hall of Fame: champions, ordering, and championship runs."""

from datetime import date, datetime, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStage, MatchStatus
from app.models.match_game import MatchGame
from app.models.playoff_round import PlayoffRound
from tests.conftest import make_player, make_season


async def _season_with_bracket(
    db_session: AsyncSession,
    *,
    name: str,
    start: date,
    champion_username: str,
    round_labels: tuple[str, ...] = ("Quarterfinal", "Semifinal", "Final"),
) -> dict:
    """A season whose champion won one match in each round, plus one playoff
    match they were not involved in."""
    champion = make_player(username=champion_username)
    rival = make_player(username=f"{champion_username} Rival")
    bystander_a = make_player(username=f"{champion_username} Bystander A")
    bystander_b = make_player(username=f"{champion_username} Bystander B")
    season = make_season(name=name, start_date=start, end_date=start)
    db_session.add_all([champion, rival, bystander_a, bystander_b, season])
    await db_session.flush()

    season.champion_id = champion.id

    rounds = []
    for position, label in enumerate(round_labels, start=1):
        playoff_round = PlayoffRound(season_id=season.id, label=label, display_order=position)
        rounds.append(playoff_round)
    db_session.add_all(rounds)
    await db_session.flush()

    matches = []
    for index, playoff_round in enumerate(rounds):
        matches.append(
            Match(
                season_id=season.id,
                home_player_id=champion.id,
                away_player_id=rival.id,
                winner_id=champion.id,
                status=MatchStatus.COMPLETED,
                stage=MatchStage.PLAYOFFS,
                playoff_round_id=playoff_round.id,
                bracket_order=1,
                completed_at=datetime(2025, 1, index + 1, tzinfo=timezone.utc),
            )
        )
    # Someone else's match in the first round: not part of the champion's run.
    matches.append(
        Match(
            season_id=season.id,
            home_player_id=bystander_a.id,
            away_player_id=bystander_b.id,
            winner_id=bystander_a.id,
            status=MatchStatus.COMPLETED,
            stage=MatchStage.PLAYOFFS,
            playoff_round_id=rounds[0].id,
            bracket_order=2,
            completed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    )
    db_session.add_all(matches)
    await db_session.commit()
    return {"season": season, "champion": champion, "rounds": rounds}


async def test_an_empty_hall_of_fame_is_an_empty_list(client: AsyncClient) -> None:
    response = await client.get("/api/hall-of-fame")
    assert response.status_code == 200
    assert response.json() == {"entries": []}


async def test_a_season_without_a_champion_is_not_listed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add(make_season(name="Season 7", start_date=date(2026, 8, 13)))
    await db_session.commit()

    assert (await client.get("/api/hall-of-fame")).json()["entries"] == []


async def test_champions_are_listed_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _season_with_bracket(
        db_session, name="Season 1", start=date(2024, 5, 31), champion_username="Doodle"
    )
    await _season_with_bracket(
        db_session, name="Season 3", start=date(2025, 2, 22), champion_username="Renk"
    )

    entries = (await client.get("/api/hall-of-fame")).json()["entries"]

    assert [entry["season_name"] for entry in entries] == ["Season 3", "Season 1"]
    assert [entry["champion"]["username"] for entry in entries] == ["Renk", "Doodle"]
    assert [entry["season_slug"] for entry in entries] == ["3", "1"]


async def test_a_repeat_champion_is_counted_across_seasons(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await _season_with_bracket(
        db_session, name="Season 3", start=date(2025, 2, 22), champion_username="Renk"
    )
    second = make_season(name="Season 4", start_date=date(2025, 6, 14))
    db_session.add(second)
    await db_session.flush()
    second.champion_id = first["champion"].id
    await db_session.commit()

    entries = (await client.get("/api/hall-of-fame")).json()["entries"]

    # Both of their entries say "2", so the page can render "2x Champion"
    # without counting the list itself.
    assert [entry["championship_count"] for entry in entries] == [2, 2]


async def test_the_run_is_only_the_champions_own_playoff_matches(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_bracket(
        db_session, name="Season 4", start=date(2025, 6, 14), champion_username="Renk"
    )
    champion_id = str(built["champion"].id)

    entry = (await client.get("/api/hall-of-fame")).json()["entries"][0]

    run = entry["championship_run"]
    assert len(run) == 3
    for match in run:
        assert champion_id in (match["home_player"]["id"], match["away_player"]["id"])


async def test_the_run_follows_explicit_round_order_not_labels_or_dates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Alphabetically "Final" sorts before "Quarterfinal" and "Semifinal"; by
    date the matches here are already in order, so only display_order can be
    producing the right answer."""
    await _season_with_bracket(
        db_session,
        name="Season 2",
        start=date(2024, 10, 25),
        champion_username="Cheeburbur",
        round_labels=("First Round", "Semifinal", "Final"),
    )

    entry = (await client.get("/api/hall-of-fame")).json()["entries"][0]

    assert [match["round_label"] for match in entry["championship_run"]] == [
        "First Round",
        "Semifinal",
        "Final",
    ]
    assert [match["round_order"] for match in entry["championship_run"]] == [1, 2, 3]


async def test_a_ten_round_bracket_stays_in_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    labels = tuple(f"Round {index}" for index in range(1, 11))
    await _season_with_bracket(
        db_session,
        name="Season 9",
        start=date(2027, 1, 1),
        champion_username="Marathoner",
        round_labels=labels,
    )

    entry = (await client.get("/api/hall-of-fame")).json()["entries"][0]

    assert [match["round_order"] for match in entry["championship_run"]] == list(range(1, 11))


async def test_matches_within_a_round_follow_bracket_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    champion = make_player(username="Bracketed")
    rival_one = make_player(username="Bracketed Rival One")
    rival_two = make_player(username="Bracketed Rival Two")
    season = make_season(name="Season 8", start_date=date(2026, 1, 1))
    db_session.add_all([champion, rival_one, rival_two, season])
    await db_session.flush()
    season.champion_id = champion.id
    playoff_round = PlayoffRound(season_id=season.id, label="Group Playoff", display_order=1)
    db_session.add(playoff_round)
    await db_session.flush()
    # Added in reverse bracket order, and the later slot completed first, so
    # neither insertion order nor date can be what produces the result.
    db_session.add_all(
        [
            Match(
                season_id=season.id,
                home_player_id=champion.id,
                away_player_id=rival_two.id,
                winner_id=champion.id,
                status=MatchStatus.COMPLETED,
                stage=MatchStage.PLAYOFFS,
                playoff_round_id=playoff_round.id,
                bracket_order=2,
                completed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            ),
            Match(
                season_id=season.id,
                home_player_id=champion.id,
                away_player_id=rival_one.id,
                winner_id=champion.id,
                status=MatchStatus.COMPLETED,
                stage=MatchStage.PLAYOFFS,
                playoff_round_id=playoff_round.id,
                bracket_order=1,
                completed_at=datetime(2026, 2, 5, tzinfo=timezone.utc),
            ),
        ]
    )
    await db_session.commit()

    entry = (await client.get("/api/hall-of-fame")).json()["entries"][0]

    assert [match["bracket_order"] for match in entry["championship_run"]] == [1, 2]


async def test_group_stage_matches_are_never_part_of_a_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_bracket(
        db_session, name="Season 5", start=date(2025, 9, 1), champion_username="Grouped"
    )
    season = built["season"]
    opponent = make_player(username="Group Opponent")
    db_session.add(opponent)
    await db_session.flush()
    db_session.add(
        Match(
            season_id=season.id,
            home_player_id=built["champion"].id,
            away_player_id=opponent.id,
            winner_id=built["champion"].id,
            status=MatchStatus.COMPLETED,
            stage=MatchStage.GROUP,
            round_label="Group A",
            completed_at=datetime(2025, 9, 5, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()

    entry = (await client.get("/api/hall-of-fame")).json()["entries"][0]

    assert all(match["stage"] == "playoffs" for match in entry["championship_run"])
    assert len(entry["championship_run"]) == 3


async def test_replays_and_streams_come_through_on_the_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_bracket(
        db_session, name="Season 6", start=date(2025, 11, 1), champion_username="Replayed"
    )
    final = (
        await db_session.execute(
            select(Match).where(Match.playoff_round_id == built["rounds"][-1].id)
        )
    ).scalars().first()
    assert final is not None
    final.youtube_url = "https://example.invalid/vod"
    db_session.add_all(
        [
            MatchGame(
                match_id=final.id,
                game_number=1,
                winner_id=built["champion"].id,
                replay_url="https://example.invalid/g1",
            ),
            MatchGame(
                match_id=final.id,
                game_number=2,
                winner_id=built["champion"].id,
                replay_url="https://example.invalid/g2",
            ),
        ]
    )
    await db_session.commit()

    entry = (await client.get("/api/hall-of-fame")).json()["entries"][0]
    last = entry["championship_run"][-1]

    assert last["youtube_url"] == "https://example.invalid/vod"
    assert [game["replay_url"] for game in last["games"]] == [
        "https://example.invalid/g1",
        "https://example.invalid/g2",
    ]
    assert last["series"]["home_series_wins"] == 2
    assert last["series"]["away_series_wins"] == 0


async def test_the_description_falls_back_to_the_overview_and_says_so(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_bracket(
        db_session, name="Season 1", start=date(2024, 5, 31), champion_username="Described"
    )
    built["season"].overview = "The first season of the league."
    await db_session.commit()

    entry = (await client.get("/api/hall-of-fame")).json()["entries"][0]
    assert entry["description"] == "The first season of the league."
    assert entry["description_is_fallback"] is True

    built["season"].hall_of_fame_description = "A wire-to-wire run."
    await db_session.commit()

    entry = (await client.get("/api/hall-of-fame")).json()["entries"][0]
    assert entry["description"] == "A wire-to-wire run."
    assert entry["description_is_fallback"] is False


async def test_a_season_with_neither_description_reports_none(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _season_with_bracket(
        db_session, name="Season 1", start=date(2024, 5, 31), champion_username="Silent"
    )

    entry = (await client.get("/api/hall-of-fame")).json()["entries"][0]
    assert entry["description"] is None
    assert entry["description_is_fallback"] is False


async def test_the_hall_of_fame_exposes_no_private_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_bracket(
        db_session, name="Season 1", start=date(2024, 5, 31), champion_username="Guarded"
    )
    built["champion"].discord_id = "secret#0001"
    await db_session.commit()

    body = (await client.get("/api/hall-of-fame")).text

    assert "secret#0001" not in body
    assert "discord_id" not in body


async def test_the_hall_of_fame_does_not_scale_its_queries_with_seasons(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Guards the N+1 the per-season shape invites: every relationship on Match
    is lazy="raise", so a missing eager load would raise rather than fall back
    to per-row queries."""
    for index, name in enumerate(("Season 1", "Season 2", "Season 3", "Season 4"), start=1):
        await _season_with_bracket(
            db_session, name=name, start=date(2024, index, 1), champion_username=f"Champ{index}"
        )

    response = await client.get("/api/hall-of-fame")

    assert response.status_code == 200
    assert len(response.json()["entries"]) == 4
    assert all(len(entry["championship_run"]) == 3 for entry in response.json()["entries"])
