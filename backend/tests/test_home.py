from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.season_entry import SeasonEntry
from tests.conftest import make_player, make_season


async def test_home_empty_database(client: AsyncClient) -> None:
    response = await client.get("/api/home")

    assert response.status_code == 200
    assert response.json() == {
        "announcements": [],
        "latest_stream": None,
        "document": None,
        "table": None,
        "current_season": None,
    }


async def test_home_active_season_roster(client: AsyncClient, db_session: AsyncSession) -> None:
    today = date.today()
    season = make_season(
        name="Active Season", start_date=today - timedelta(days=30), end_date=today + timedelta(days=30)
    )
    player = make_player(username="ActiveRosterPlayer")
    db_session.add_all([season, player])
    await db_session.flush()
    db_session.add(SeasonEntry(season_id=season.id, player_id=player.id))
    await db_session.commit()

    response = await client.get("/api/home")

    assert response.status_code == 200
    data = response.json()
    assert data["current_season"]["name"] == "Active Season"
    assert data["current_season"]["is_active"] is True
    assert [p["username"] for p in data["current_season"]["roster"]] == ["ActiveRosterPlayer"]


async def test_home_off_season_uses_most_recently_started_season(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    today = date.today()
    older = make_season(
        name="Older Ended Season",
        start_date=today - timedelta(days=400),
        end_date=today - timedelta(days=300),
    )
    most_recent = make_season(
        name="Most Recent Ended Season",
        start_date=today - timedelta(days=100),
        end_date=today - timedelta(days=10),
    )
    player = make_player(username="OffSeasonPlayer")
    db_session.add_all([older, most_recent, player])
    await db_session.flush()
    db_session.add(SeasonEntry(season_id=most_recent.id, player_id=player.id))
    await db_session.commit()

    response = await client.get("/api/home")

    assert response.status_code == 200
    data = response.json()
    assert data["current_season"]["name"] == "Most Recent Ended Season"
    assert data["current_season"]["is_active"] is False
