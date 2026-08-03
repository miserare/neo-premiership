"""Playoff rounds are structure, not text.

Every test here exists because the previous model let a label or a date decide
where a round appeared. The recurring shape is: give the rounds names whose
alphabetical order is deliberately wrong, then assert the API ignores them.
"""
from datetime import date, datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStage, MatchStatus
from app.models.player import Player
from app.models.playoff_round import PlayoffRound
from app.models.season import Season
from app.models.season_entry import SeasonEntry
from tests.conftest import ADMIN_HEADERS


async def _season(db: AsyncSession, name: str) -> Season:
    season = Season(name=name, start_date=date(2024, 1, 1))
    db.add(season)
    await db.flush()
    return season


async def _players(db: AsyncSession, *usernames: str) -> list[Player]:
    players = [Player(username=username) for username in usernames]
    db.add_all(players)
    await db.flush()
    return players


async def _round(db: AsyncSession, season: Season, label: str, display_order: int) -> PlayoffRound:
    playoff_round = PlayoffRound(season_id=season.id, label=label, display_order=display_order)
    db.add(playoff_round)
    await db.flush()
    return playoff_round


async def _playoff_match(
    db: AsyncSession,
    season: Season,
    playoff_round: PlayoffRound,
    home: Player,
    away: Player,
    *,
    bracket_order: int,
    completed_at: datetime | None = None,
) -> Match:
    match = Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        winner_id=home.id if completed_at else None,
        status=MatchStatus.COMPLETED if completed_at else MatchStatus.SCHEDULED,
        stage=MatchStage.PLAYOFFS,
        playoff_round_id=playoff_round.id,
        bracket_order=bracket_order,
        completed_at=completed_at,
    )
    db.add(match)
    await db.flush()
    return match


async def _bracket(client: AsyncClient, season: Season) -> list[dict]:
    response = await client.get(f"/api/seasons/{season.id}")
    assert response.status_code == 200
    return response.json()["bracket"]


# --------------------------------------------------------------------------
# Ordering comes from display_order, and from nothing else
# --------------------------------------------------------------------------


async def test_rounds_return_in_display_order_not_alphabetical_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The canonical four-round bracket. Alphabetically these labels sort
    Final, First Round, QF, SF - which is why the alphabet cannot be involved."""
    season = await _season(db_session, "Four Round Season")
    for label, order in (("First Round", 1), ("QF", 2), ("SF", 3), ("Final", 4)):
        await _round(db_session, season, label, order)
    await db_session.commit()

    bracket = await _bracket(client, season)

    assert [r["label"] for r in bracket] == ["First Round", "QF", "SF", "Final"]
    assert [r["display_order"] for r in bracket] == [1, 2, 3, 4]


async def test_ten_scrambled_labels_return_in_numeric_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Ten rounds whose labels are in reverse alphabetical order, so any
    label-based sort produces exactly the wrong answer."""
    season = await _season(db_session, "Ten Round Season")
    labels = [
        "Zeta Stage", "Yankee Cup", "Xi Bracket", "Whiskey Heat", "Victor Round",
        "Uniform Clash", "Tango Tier", "Sierra Split", "Romeo Rally", "Quebec Final",
    ]
    for order, label in enumerate(labels, start=1):
        await _round(db_session, season, label, order)
    await db_session.commit()

    bracket = await _bracket(client, season)

    assert [r["label"] for r in bracket] == labels
    assert [r["display_order"] for r in bracket] == list(range(1, 11))


async def test_a_season_may_have_a_single_round(client: AsyncClient, db_session: AsyncSession) -> None:
    season = await _season(db_session, "One Round Season")
    await _round(db_session, season, "Grand Final", 1)
    await db_session.commit()

    bracket = await _bracket(client, season)

    assert [r["label"] for r in bracket] == ["Grand Final"]


async def test_renaming_a_round_does_not_move_it(client: AsyncClient, db_session: AsyncSession) -> None:
    season = await _season(db_session, "Rename Season")
    first = await _round(db_session, season, "First Round", 1)
    await _round(db_session, season, "Final", 2)
    await db_session.commit()

    # Rename the first round to something that sorts last alphabetically.
    response = await client.patch(
        f"/api/seasons/{season.id}/playoff-rounds/{first.id}",
        json={"label": "Zzz Opening"},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["display_order"] == 1

    bracket = await _bracket(client, season)
    assert [r["label"] for r in bracket] == ["Zzz Opening", "Final"]


async def test_rescheduling_a_match_does_not_move_its_round(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A postponed final, or one entered late, stays the final."""
    season = await _season(db_session, "Reschedule Season")
    home, away = await _players(db_session, "RescheduleHome", "RescheduleAway")
    semi = await _round(db_session, season, "Semifinal", 1)
    final = await _round(db_session, season, "Final", 2)
    # The final was played BEFORE the semifinal, chronologically.
    await _playoff_match(
        db_session, season, semi, home, away, bracket_order=1,
        completed_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    final_match = await _playoff_match(
        db_session, season, final, away, home, bracket_order=1,
        completed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    await db_session.commit()

    bracket = await _bracket(client, season)
    assert [r["label"] for r in bracket] == ["Semifinal", "Final"]

    # Move it earlier still, and to a different scheduled date.
    response = await client.patch(
        f"/api/matches/{final_match.id}",
        json={
            "completed_at": "2023-01-01T00:00:00+00:00",
            "scheduled_at": "2023-01-01T00:00:00+00:00",
        },
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200

    bracket = await _bracket(client, season)
    assert [r["label"] for r in bracket] == ["Semifinal", "Final"]


async def test_an_empty_round_keeps_its_position(client: AsyncClient, db_session: AsyncSession) -> None:
    """A round planned but not yet drawn still occupies its column."""
    season = await _season(db_session, "Empty Round Season")
    home, away = await _players(db_session, "EmptyHome", "EmptyAway")
    await _round(db_session, season, "First Round", 1)
    semi = await _round(db_session, season, "Semifinal", 2)
    await _round(db_session, season, "Final", 3)
    await _playoff_match(db_session, season, semi, home, away, bracket_order=1)
    await db_session.commit()

    bracket = await _bracket(client, season)

    assert [r["label"] for r in bracket] == ["First Round", "Semifinal", "Final"]
    assert [len(r["matches"]) for r in bracket] == [0, 1, 0]


async def test_matches_are_ordered_by_bracket_position(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Inserted out of order, with dates that disagree with the positions."""
    season = await _season(db_session, "Slot Order Season")
    a, b, c, d = await _players(db_session, "SlotA", "SlotB", "SlotC", "SlotD")
    first = await _round(db_session, season, "First Round", 1)
    await _playoff_match(
        db_session, season, first, c, d, bracket_order=2,
        completed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    await _playoff_match(
        db_session, season, first, a, b, bracket_order=1,
        completed_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
    )
    await db_session.commit()

    bracket = await _bracket(client, season)

    assert [m["home_player"]["username"] for m in bracket[0]["matches"]] == ["SlotA", "SlotC"]
    assert [m["bracket_order"] for m in bracket[0]["matches"]] == [1, 2]


async def test_a_bye_leaves_a_gap_in_the_positions(client: AsyncClient, db_session: AsyncSession) -> None:
    """A round may hold positions 1 and 3 with nothing at 2."""
    season = await _season(db_session, "Bye Season")
    a, b, c, d = await _players(db_session, "ByeA", "ByeB", "ByeC", "ByeD")
    first = await _round(db_session, season, "First Round", 1)
    await _playoff_match(db_session, season, first, a, b, bracket_order=1)
    await _playoff_match(db_session, season, first, c, d, bracket_order=3)
    await db_session.commit()

    bracket = await _bracket(client, season)

    assert [m["bracket_order"] for m in bracket[0]["matches"]] == [1, 3]


# --------------------------------------------------------------------------
# Positions are unique where they must be, and reusable where they may be
# --------------------------------------------------------------------------


async def test_two_rounds_cannot_share_a_position(client: AsyncClient, db_session: AsyncSession) -> None:
    season = await _season(db_session, "Duplicate Position Season")
    await _round(db_session, season, "First Round", 1)
    await db_session.commit()

    response = await client.post(
        f"/api/seasons/{season.id}/playoff-rounds",
        json={"label": "Also First", "display_order": 1},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 409
    assert "position" in response.json()["detail"].lower()


async def test_two_matches_cannot_share_a_position_in_one_round(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Duplicate Slot Season")
    a, b, c, d = await _players(db_session, "DupA", "DupB", "DupC", "DupD")
    db_session.add_all(
        [
            SeasonEntry(season_id=season.id, player_id=player.id) for player in (a, b, c, d)
        ]
    )
    first = await _round(db_session, season, "First Round", 1)
    await _playoff_match(db_session, season, first, a, b, bracket_order=1)
    await db_session.commit()

    response = await client.post(
        "/api/matches",
        json={
            "season_id": str(season.id),
            "home_player_id": str(c.id),
            "away_player_id": str(d.id),
            "stage": "playoffs",
            "playoff_round_id": str(first.id),
            "bracket_order": 1,
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 409
    assert "position" in response.json()["detail"].lower()


async def test_the_same_position_may_be_used_in_different_rounds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Reused Slot Season")
    a, b, c, d = await _players(db_session, "ReuseA", "ReuseB", "ReuseC", "ReuseD")
    first = await _round(db_session, season, "First Round", 1)
    final = await _round(db_session, season, "Final", 2)
    await _playoff_match(db_session, season, first, a, b, bracket_order=1)
    await _playoff_match(db_session, season, final, c, d, bracket_order=1)
    await db_session.commit()

    bracket = await _bracket(client, season)

    assert [m["bracket_order"] for r in bracket for m in r["matches"]] == [1, 1]


async def test_a_zero_or_negative_position_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Zero Position Season")
    await db_session.commit()

    for bad in (0, -1):
        response = await client.post(
            f"/api/seasons/{season.id}/playoff-rounds",
            json={"label": "Nope", "display_order": bad},
            headers=ADMIN_HEADERS,
        )
        assert response.status_code == 422, bad


async def test_a_blank_label_is_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    season = await _season(db_session, "Blank Label Season")
    await db_session.commit()

    response = await client.post(
        f"/api/seasons/{season.id}/playoff-rounds",
        json={"label": "   "},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------
# A round belongs to one season, and to the playoff stage
# --------------------------------------------------------------------------


async def test_a_playoff_match_cannot_reference_another_seasons_round(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Own Season")
    other = await _season(db_session, "Other Season")
    a, b = await _players(db_session, "CrossA", "CrossB")
    db_session.add_all([SeasonEntry(season_id=season.id, player_id=p.id) for p in (a, b)])
    foreign_round = await _round(db_session, other, "Final", 1)
    await db_session.commit()

    response = await client.post(
        "/api/matches",
        json={
            "season_id": str(season.id),
            "home_player_id": str(a.id),
            "away_player_id": str(b.id),
            "stage": "playoffs",
            "playoff_round_id": str(foreign_round.id),
            "bracket_order": 1,
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422
    assert "own season" in response.json()["detail"]


async def test_a_group_match_cannot_reference_a_playoff_round(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Group Guard Season")
    a, b = await _players(db_session, "GroupGuardA", "GroupGuardB")
    playoff_round = await _round(db_session, season, "Final", 1)
    await db_session.commit()

    response = await client.post(
        "/api/matches",
        json={
            "season_id": str(season.id),
            "home_player_id": str(a.id),
            "away_player_id": str(b.id),
            "stage": "group",
            "playoff_round_id": str(playoff_round.id),
        },
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422
    assert "group-stage match must not reference a playoff round" in response.text


async def test_moving_a_match_between_rounds_is_validated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Move Match Season")
    other = await _season(db_session, "Move Match Other Season")
    a, b = await _players(db_session, "MoveA", "MoveB")
    first = await _round(db_session, season, "First Round", 1)
    final = await _round(db_session, season, "Final", 2)
    foreign = await _round(db_session, other, "Final", 1)
    match = await _playoff_match(db_session, season, first, a, b, bracket_order=1)
    await db_session.commit()

    # A move into another season's round is refused...
    rejected = await client.patch(
        f"/api/matches/{match.id}",
        json={"playoff_round_id": str(foreign.id)},
        headers=ADMIN_HEADERS,
    )
    assert rejected.status_code == 422

    # ...while a move within the season is allowed and takes effect.
    accepted = await client.patch(
        f"/api/matches/{match.id}",
        json={"playoff_round_id": str(final.id), "bracket_order": 1},
        headers=ADMIN_HEADERS,
    )
    assert accepted.status_code == 200
    assert accepted.json()["playoff_round_id"] == str(final.id)
    assert accepted.json()["round_label"] == "Final"

    bracket = await _bracket(client, season)
    assert [len(r["matches"]) for r in bracket] == [0, 1]


# --------------------------------------------------------------------------
# Reordering
# --------------------------------------------------------------------------


async def test_unassigning_a_round_leaves_no_stale_label_behind(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Taking a playoff match out of its round must not leave it reporting that
    round's name from the legacy column - that stale copy is the whole reason
    rounds became rows."""
    season = await _season(db_session, "Unassign Season")
    a, b = await _players(db_session, "UnassignA", "UnassignB")
    final = await _round(db_session, season, "Final", 1)
    match = await _playoff_match(
        db_session, season, final, a, b, bracket_order=1,
        completed_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    await db_session.commit()

    assert (await client.get(f"/api/matches/{match.id}")).json()["round_label"] == "Final"

    response = await client.patch(
        f"/api/matches/{match.id}", json={"playoff_round_id": None}, headers=ADMIN_HEADERS
    )

    assert response.status_code == 200
    assert response.json()["playoff_round_id"] is None
    assert response.json()["round_label"] is None
    assert response.json()["round_order"] is None

    fetched = (await client.get(f"/api/matches/{match.id}")).json()
    assert fetched["round_label"] is None

    # It drops out of the bracket rather than appearing under its old round,
    # and the stream label stops claiming a round too.
    detail = (await client.get(f"/api/seasons/{season.id}")).json()
    assert [len(r["matches"]) for r in detail["bracket"]] == [0]


async def test_reorder_rewrites_the_whole_sequence_atomically(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Reversing four rounds passes through positions that are all already
    taken, so a naive one-at-a-time rewrite would collide."""
    season = await _season(db_session, "Reorder Season")
    rounds = [
        await _round(db_session, season, label, order)
        for order, label in enumerate(["First Round", "QF", "SF", "Final"], start=1)
    ]
    await db_session.commit()

    response = await client.put(
        f"/api/seasons/{season.id}/playoff-rounds/reorder",
        json={"round_ids": [str(r.id) for r in reversed(rounds)]},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert [r["label"] for r in response.json()] == ["Final", "SF", "QF", "First Round"]
    assert [r["display_order"] for r in response.json()] == [1, 2, 3, 4]

    bracket = await _bracket(client, season)
    assert [r["label"] for r in bracket] == ["Final", "SF", "QF", "First Round"]


async def test_reorder_of_ten_rounds_stays_contiguous(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Reorder Ten Season")
    rounds = [await _round(db_session, season, f"Round {i}", i) for i in range(1, 11)]
    await db_session.commit()

    shuffled = [rounds[i] for i in (4, 9, 0, 7, 2, 6, 1, 8, 3, 5)]
    response = await client.put(
        f"/api/seasons/{season.id}/playoff-rounds/reorder",
        json={"round_ids": [str(r.id) for r in shuffled]},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert [r["display_order"] for r in response.json()] == list(range(1, 11))
    assert [r["label"] for r in response.json()] == [r.label for r in shuffled]


async def test_a_partial_reorder_list_is_refused_and_changes_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Half a list would silently drop rounds from the ordering, so the whole
    request is refused rather than half-applied."""
    season = await _season(db_session, "Partial Reorder Season")
    rounds = [
        await _round(db_session, season, label, order)
        for order, label in enumerate(["First Round", "SF", "Final"], start=1)
    ]
    await db_session.commit()

    response = await client.put(
        f"/api/seasons/{season.id}/playoff-rounds/reorder",
        json={"round_ids": [str(rounds[2].id), str(rounds[0].id)]},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422
    bracket = await _bracket(client, season)
    assert [r["label"] for r in bracket] == ["First Round", "SF", "Final"]


async def test_reorder_rejects_a_round_from_another_season(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Reorder Guard Season")
    other = await _season(db_session, "Reorder Guard Other")
    mine = await _round(db_session, season, "Final", 1)
    theirs = await _round(db_session, other, "Final", 1)
    await db_session.commit()

    response = await client.put(
        f"/api/seasons/{season.id}/playoff-rounds/reorder",
        json={"round_ids": [str(theirs.id), str(mine.id)]},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 422


async def test_reorder_requires_an_administrator(client: AsyncClient, db_session: AsyncSession) -> None:
    season = await _season(db_session, "Reorder Auth Season")
    playoff_round = await _round(db_session, season, "Final", 1)
    await db_session.commit()

    response = await client.put(
        f"/api/seasons/{season.id}/playoff-rounds/reorder",
        json={"round_ids": [str(playoff_round.id)]},
    )

    assert response.status_code == 401


# --------------------------------------------------------------------------
# Deletion
# --------------------------------------------------------------------------


async def test_deleting_a_round_that_holds_matches_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Delete Guard Season")
    a, b = await _players(db_session, "DeleteGuardA", "DeleteGuardB")
    playoff_round = await _round(db_session, season, "Final", 1)
    await _playoff_match(db_session, season, playoff_round, a, b, bracket_order=1)
    await db_session.commit()

    response = await client.delete(
        f"/api/seasons/{season.id}/playoff-rounds/{playoff_round.id}", headers=ADMIN_HEADERS
    )

    assert response.status_code == 409
    assert "still contains 1 match" in response.json()["detail"]

    bracket = await _bracket(client, season)
    assert [r["label"] for r in bracket] == ["Final"]
    assert len(bracket[0]["matches"]) == 1


async def test_an_empty_round_can_be_deleted(client: AsyncClient, db_session: AsyncSession) -> None:
    season = await _season(db_session, "Delete Empty Season")
    keep = await _round(db_session, season, "First Round", 1)
    drop = await _round(db_session, season, "Final", 2)
    await db_session.commit()

    response = await client.delete(
        f"/api/seasons/{season.id}/playoff-rounds/{drop.id}", headers=ADMIN_HEADERS
    )

    assert response.status_code == 204
    bracket = await _bracket(client, season)
    assert [r["id"] for r in bracket] == [str(keep.id)]


async def test_a_round_can_be_emptied_and_then_deleted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The documented escape hatch: move the matches out, then delete."""
    season = await _season(db_session, "Empty Then Delete Season")
    a, b = await _players(db_session, "EmptyThenA", "EmptyThenB")
    doomed = await _round(db_session, season, "Play-in", 1)
    keeper = await _round(db_session, season, "Final", 2)
    match = await _playoff_match(db_session, season, doomed, a, b, bracket_order=1)
    await db_session.commit()

    moved = await client.patch(
        f"/api/matches/{match.id}",
        json={"playoff_round_id": str(keeper.id), "bracket_order": 2},
        headers=ADMIN_HEADERS,
    )
    assert moved.status_code == 200

    deleted = await client.delete(
        f"/api/seasons/{season.id}/playoff-rounds/{doomed.id}", headers=ADMIN_HEADERS
    )
    assert deleted.status_code == 204

    bracket = await _bracket(client, season)
    assert [r["label"] for r in bracket] == ["Final"]


async def test_deleting_a_season_removes_its_rounds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Cascade Season")
    a, b = await _players(db_session, "CascadeA", "CascadeB")
    playoff_round = await _round(db_session, season, "Final", 1)
    await _playoff_match(db_session, season, playoff_round, a, b, bracket_order=1)
    await db_session.commit()

    response = await client.delete(f"/api/seasons/{season.id}", headers=ADMIN_HEADERS)

    assert response.status_code == 204
    assert (await client.get(f"/api/seasons/{season.id}")).status_code == 404


# --------------------------------------------------------------------------
# Round management, end to end
# --------------------------------------------------------------------------


async def test_rounds_can_be_created_listed_and_appended(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Creating without a position appends, so an administrator building a
    bracket front-to-back never types a number."""
    season = await _season(db_session, "Append Season")
    await db_session.commit()

    for label in ("First Round", "QF", "SF", "Final"):
        response = await client.post(
            f"/api/seasons/{season.id}/playoff-rounds", json={"label": label}, headers=ADMIN_HEADERS
        )
        assert response.status_code == 201

    listing = await client.get(f"/api/seasons/{season.id}/playoff-rounds")
    assert listing.status_code == 200
    assert [r["label"] for r in listing.json()] == ["First Round", "QF", "SF", "Final"]
    assert [r["display_order"] for r in listing.json()] == [1, 2, 3, 4]
    assert [r["match_count"] for r in listing.json()] == [0, 0, 0, 0]


async def test_round_management_requires_an_administrator(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Round Auth Season")
    playoff_round = await _round(db_session, season, "Final", 1)
    await db_session.commit()

    created = await client.post(f"/api/seasons/{season.id}/playoff-rounds", json={"label": "Nope"})
    renamed = await client.patch(
        f"/api/seasons/{season.id}/playoff-rounds/{playoff_round.id}", json={"label": "Nope"}
    )
    deleted = await client.delete(f"/api/seasons/{season.id}/playoff-rounds/{playoff_round.id}")

    assert [created.status_code, renamed.status_code, deleted.status_code] == [401, 401, 401]
    # Reading the bracket stays public.
    assert (await client.get(f"/api/seasons/{season.id}/playoff-rounds")).status_code == 200


# --------------------------------------------------------------------------
# Everything else keeps working
# --------------------------------------------------------------------------


async def test_standings_elo_streams_and_records_are_unaffected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A season with both stages: the group stage feeds standings, the playoff
    stage feeds the bracket, and Elo, streams, replays and player records read
    the same as before rounds became rows."""
    season = await _season(db_session, "Full Season")
    champ, runner = await _players(db_session, "FullChamp", "FullRunner")
    db_session.add_all(
        [
            SeasonEntry(season_id=season.id, player_id=champ.id, group_label="A"),
            SeasonEntry(season_id=season.id, player_id=runner.id, group_label="A"),
        ]
    )
    played = datetime(2024, 3, 1, tzinfo=timezone.utc)
    db_session.add(
        Match(
            season_id=season.id,
            home_player_id=champ.id,
            away_player_id=runner.id,
            winner_id=champ.id,
            status=MatchStatus.COMPLETED,
            stage=MatchStage.GROUP,
            round_label="Group A",
            completed_at=played,
            replay_url="https://example.invalid/group-replay",
            youtube_url="https://example.invalid/group-video",
        )
    )
    final = await _round(db_session, season, "Final", 1)
    final_match = Match(
        season_id=season.id,
        home_player_id=champ.id,
        away_player_id=runner.id,
        winner_id=champ.id,
        status=MatchStatus.COMPLETED,
        stage=MatchStage.PLAYOFFS,
        playoff_round_id=final.id,
        bracket_order=1,
        completed_at=played + timedelta(days=30),
        replay_url="https://example.invalid/final-replay",
        youtube_url="https://example.invalid/final-video",
    )
    db_session.add(final_match)
    await db_session.commit()

    # Ratings are rebuilt on every match write, so put one write through the
    # API - the same path a real result takes - before reading them back.
    nudged = await client.patch(
        f"/api/matches/{final_match.id}", json={"bracket_order": 1}, headers=ADMIN_HEADERS
    )
    assert nudged.status_code == 200

    detail = (await client.get(f"/api/seasons/{season.id}")).json()

    standings = detail["standings"][0]["standings"]
    assert [(s["player"]["username"], s["wins"], s["losses"]) for s in standings] == [
        ("FullChamp", 1, 0),
        ("FullRunner", 0, 1),
    ]

    # The group match keeps its own label; the playoff match takes the round's.
    stream_labels = sorted(s["label"] for s in detail["streams"])
    assert stream_labels == ["FullChamp vs FullRunner (Final)", "FullChamp vs FullRunner (Group A)"]

    final_match = detail["bracket"][0]["matches"][0]
    assert final_match["replay_url"] == "https://example.invalid/final-replay"
    assert final_match["youtube_url"] == "https://example.invalid/final-video"
    assert final_match["games"][0]["replay_url"] == "https://example.invalid/final-replay"

    player = (await client.get(f"/api/players/{champ.id}")).json()
    assert player["elo_rating"] > 1000
    assert player["historical_record"]["wins"] == 2

    # The admin match listing reads the round without a lazy-load explosion.
    listing = await client.get(f"/api/matches?season_id={season.id}", headers=ADMIN_HEADERS)
    assert listing.status_code == 200
    assert {m["round_label"] for m in listing.json()} == {"Group A", "Final"}


async def test_public_round_endpoints_expose_no_private_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    season = await _season(db_session, "Round Privacy Season")
    home = Player(username="RoundPrivacyHome", discord_id="secret#4242")
    away = Player(username="RoundPrivacyAway", discord_id="secret#4343")
    db_session.add_all([home, away])
    await db_session.flush()
    final = await _round(db_session, season, "Final", 1)
    await _playoff_match(db_session, season, final, home, away, bracket_order=1)
    await db_session.commit()

    for path in (f"/api/seasons/{season.id}", f"/api/seasons/{season.id}/playoff-rounds"):
        response = await client.get(path)
        assert response.status_code == 200
        assert "discord_id" not in response.text, path
        assert "secret#" not in response.text, path
