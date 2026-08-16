"""Homepage fixtures: the league week, and administrator highlighting."""

from datetime import date, datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStage, MatchStatus
from app.services.league_week import current_league_week
from tests.conftest import ADMIN_HEADERS, make_player, make_season

# A Wednesday, mid-afternoon in the league's zone.
WEDNESDAY = datetime(2026, 8, 12, 18, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------- week bounds


def test_a_league_week_runs_monday_to_monday() -> None:
    start, end = current_league_week(WEDNESDAY)

    # 04:00Z is Monday 00:00 in America/New_York during daylight saving time.
    assert start == datetime(2026, 8, 10, 4, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 17, 4, 0, tzinfo=timezone.utc)


def test_the_window_is_half_open_at_both_ends() -> None:
    """A match at exactly Monday midnight belongs to the week starting then,
    and to exactly one week."""
    start, end = current_league_week(WEDNESDAY)

    assert current_league_week(start) == (start, end)
    # One microsecond before the boundary is still the same week.
    assert current_league_week(end - timedelta(microseconds=1)) == (start, end)
    # The boundary itself opens the next one.
    assert current_league_week(end)[0] == end


def test_the_week_does_not_depend_on_the_servers_own_clock_zone() -> None:
    """The same instant expressed in three zones gives the same league week."""
    reference = current_league_week(WEDNESDAY)

    for offset in (-11, 0, 14):
        same_instant = WEDNESDAY.astimezone(timezone(timedelta(hours=offset)))
        assert current_league_week(same_instant) == reference


def test_a_week_containing_a_dst_change_still_starts_at_local_midnight() -> None:
    """US DST ends on 2026-11-01, so that week is 169 hours long. The boundary
    has to stay at real local midnight rather than drift by an hour."""
    start, end = current_league_week(datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc))

    # Monday 2026-11-02 00:00 EST is 05:00Z, and so is the following Monday.
    assert start == datetime(2026, 11, 2, 5, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 11, 9, 5, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------ weekly fixtures


async def _season_with_matches(db_session: AsyncSession) -> dict:
    today = date.today()
    season = make_season(
        name="Season 7", start_date=today - timedelta(days=2), end_date=today + timedelta(days=60)
    )
    home = make_player(username="Fixture Home")
    away = make_player(username="Fixture Away")
    db_session.add_all([season, home, away])
    await db_session.flush()
    return {"season": season, "home": home, "away": away}


def _match(built: dict, **kwargs) -> Match:
    kwargs.setdefault("stage", MatchStage.GROUP)
    kwargs.setdefault("status", MatchStatus.SCHEDULED)
    return Match(
        season_id=built["season"].id,
        home_player_id=built["home"].id,
        away_player_id=built["away"].id,
        **kwargs,
    )


async def test_matches_in_the_current_week_appear(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    start, _ = current_league_week()
    db_session.add(
        _match(built, scheduled_at=start + timedelta(days=2), round_label="Group A - Matchday 1")
    )
    await db_session.commit()

    fixtures = (await client.get("/api/home")).json()["fixtures"]

    assert len(fixtures["this_week"]) == 1
    assert fixtures["this_week"][0]["round_label"] == "Group A - Matchday 1"
    # Both participants arrive with the slug the page links to.
    assert fixtures["this_week"][0]["home_player"]["slug"] == "fixture-home"


async def test_matches_outside_the_current_week_do_not(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    start, end = current_league_week()
    db_session.add_all(
        [
            _match(built, scheduled_at=start - timedelta(days=1)),
            _match(built, scheduled_at=end + timedelta(days=1)),
        ]
    )
    await db_session.commit()

    fixtures = (await client.get("/api/home")).json()["fixtures"]

    assert fixtures["this_week"] == []


async def test_an_empty_week_still_reports_its_bounds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The empty state is a real answer, not a missing section."""
    await _season_with_matches(db_session)
    await db_session.commit()

    fixtures = (await client.get("/api/home")).json()["fixtures"]

    assert fixtures["this_week"] == []
    assert fixtures["featured"] == []
    assert fixtures["timezone"] == "America/New_York"
    assert fixtures["week_start"] < fixtures["week_end"]


async def test_a_completed_match_this_week_keeps_its_result(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    start, _ = current_league_week()
    db_session.add(
        _match(
            built,
            scheduled_at=start + timedelta(days=1),
            status=MatchStatus.COMPLETED,
            winner_id=built["home"].id,
            completed_at=start + timedelta(days=1, hours=2),
        )
    )
    await db_session.commit()

    fixtures = (await client.get("/api/home")).json()["fixtures"]

    assert fixtures["this_week"][0]["status"] == "completed"
    assert fixtures["this_week"][0]["winner_id"] == str(built["home"].id)


async def test_cancelled_matches_are_left_out_of_the_weekly_list(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    start, _ = current_league_week()
    db_session.add(
        _match(built, scheduled_at=start + timedelta(days=1), status=MatchStatus.CANCELLED)
    )
    await db_session.commit()

    assert (await client.get("/api/home")).json()["fixtures"]["this_week"] == []


async def test_a_cancelled_match_can_still_be_featured_deliberately(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    start, _ = current_league_week()
    db_session.add(
        _match(
            built,
            scheduled_at=start + timedelta(days=1),
            status=MatchStatus.CANCELLED,
            featured_on_homepage=True,
        )
    )
    await db_session.commit()

    fixtures = (await client.get("/api/home")).json()["fixtures"]

    assert len(fixtures["featured"]) == 1
    assert fixtures["featured"][0]["status"] == "cancelled"


# ------------------------------------------------------------------ featuring


async def test_a_featured_match_appears_whatever_week_it_is_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    db_session.add(
        _match(
            built,
            scheduled_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            status=MatchStatus.COMPLETED,
            winner_id=built["home"].id,
            completed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            featured_on_homepage=True,
        )
    )
    await db_session.commit()

    fixtures = (await client.get("/api/home")).json()["fixtures"]

    assert len(fixtures["featured"]) == 1
    assert fixtures["featured"][0]["featured_on_homepage"] is True


async def test_a_featured_match_in_this_week_is_not_listed_twice(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    start, _ = current_league_week()
    db_session.add(
        _match(built, scheduled_at=start + timedelta(days=2), featured_on_homepage=True)
    )
    await db_session.commit()

    fixtures = (await client.get("/api/home")).json()["fixtures"]

    assert len(fixtures["featured"]) == 1
    assert fixtures["this_week"] == []


async def test_featured_matches_follow_the_administrators_order(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    third = _match(built, scheduled_at=datetime(2024, 1, 1, tzinfo=timezone.utc), featured_on_homepage=True)
    first = _match(
        built,
        scheduled_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        featured_on_homepage=True,
        homepage_feature_order=1,
    )
    second = _match(
        built,
        scheduled_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        featured_on_homepage=True,
        homepage_feature_order=2,
    )
    db_session.add_all([third, first, second])
    await db_session.commit()

    fixtures = (await client.get("/api/home")).json()["fixtures"]

    # Explicit order first; the one without a position falls to the end rather
    # than jumping the queue, and ties break deterministically.
    assert [m["id"] for m in fixtures["featured"]] == [str(first.id), str(second.id), str(third.id)]


async def test_featuring_is_set_through_match_administration(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    match = _match(built, scheduled_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    db_session.add(match)
    await db_session.commit()

    response = await client.patch(
        f"/api/matches/{match.id}",
        json={"featured_on_homepage": True, "homepage_feature_order": 3},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["featured_on_homepage"] is True
    assert response.json()["homepage_feature_order"] == 3
    assert len((await client.get("/api/home")).json()["fixtures"]["featured"]) == 1


async def test_unfeaturing_removes_it_again(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    match = _match(
        built, scheduled_at=datetime(2024, 1, 1, tzinfo=timezone.utc), featured_on_homepage=True
    )
    db_session.add(match)
    await db_session.commit()

    await client.patch(
        f"/api/matches/{match.id}",
        json={"featured_on_homepage": False, "homepage_feature_order": None},
        headers=ADMIN_HEADERS,
    )

    assert (await client.get("/api/home")).json()["fixtures"]["featured"] == []


async def test_a_non_positive_feature_order_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    match = _match(built, scheduled_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    db_session.add(match)
    await db_session.commit()

    response = await client.patch(
        f"/api/matches/{match.id}",
        json={"featured_on_homepage": True, "homepage_feature_order": 0},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 422


async def test_featuring_requires_an_administrator(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    match = _match(built, scheduled_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    db_session.add(match)
    await db_session.commit()

    response = await client.patch(
        f"/api/matches/{match.id}", json={"featured_on_homepage": True}
    )
    assert response.status_code == 401


async def test_fixtures_expose_no_private_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    built = await _season_with_matches(db_session)
    built["home"].discord_id = "secret#0001"
    start, _ = current_league_week()
    db_session.add(_match(built, scheduled_at=start + timedelta(days=1)))
    await db_session.commit()

    body = (await client.get("/api/home")).text

    assert "secret#0001" not in body
    assert "discord_id" not in body
