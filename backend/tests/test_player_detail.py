from datetime import date, datetime, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStage, MatchStatus
from app.models.player import Player
from app.models.season import Season
from app.models.season_entry import SeasonEntry


async def test_player_records_and_backlog(client: AsyncClient, db_session: AsyncSession) -> None:
    season_old = Season(name="Old Record Season", start_date=date(2023, 1, 1), end_date=date(2023, 4, 1))
    season_new = Season(name="New Record Season", start_date=date(2024, 1, 1), end_date=date(2024, 4, 1))
    hero = Player(username="RecordHero")
    rival = Player(username="RecordRival")
    db_session.add_all([season_old, season_new, hero, rival])
    await db_session.flush()

    db_session.add_all(
        [
            SeasonEntry(season_id=season_old.id, player_id=hero.id),
            SeasonEntry(season_id=season_new.id, player_id=hero.id),
            # old season: one win
            Match(
                season_id=season_old.id, home_player_id=hero.id, away_player_id=rival.id, winner_id=hero.id,
                status=MatchStatus.COMPLETED, stage=MatchStage.GROUP,
                completed_at=datetime(2023, 2, 1, tzinfo=timezone.utc), home_score=2, away_score=0,
            ),
            # new season: one loss
            Match(
                season_id=season_new.id, home_player_id=rival.id, away_player_id=hero.id, winner_id=rival.id,
                status=MatchStatus.COMPLETED, stage=MatchStage.GROUP,
                completed_at=datetime(2024, 2, 1, tzinfo=timezone.utc), home_score=2, away_score=1,
            ),
            # new season: an upcoming scheduled match - belongs in the backlog
            Match(
                season_id=season_new.id, home_player_id=hero.id, away_player_id=rival.id,
                status=MatchStatus.SCHEDULED, stage=MatchStage.GROUP,
                scheduled_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
            ),
            # a cancelled match should appear in neither backlog nor records
            Match(
                season_id=season_new.id, home_player_id=hero.id, away_player_id=rival.id,
                status=MatchStatus.CANCELLED, stage=MatchStage.GROUP,
                scheduled_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/players/{hero.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["historical_record"] == {"wins": 1, "losses": 1}
    assert data["most_recent_season_record"] == {
        "season_id": str(season_new.id),
        "season_name": "New Record Season",
        "wins": 0,
        "losses": 1,
            # No draft was recorded for this season, so the sprite roster is empty.
            "pokemon": [],
            "former_pokemon": [],
        }
    assert [record["season_name"] for record in data["season_records"]] == [
        "New Record Season",
        "Old Record Season",
    ]
    assert len(data["backlog"]) == 1
    assert data["backlog"][0]["status"] == "scheduled"
    assert len(data["completed_matches"]) == 2
    assert all(match["status"] == "completed" for match in data["completed_matches"])


async def test_player_optional_links_returned_when_present(client: AsyncClient, db_session: AsyncSession) -> None:
    season = Season(name="Links Season", start_date=date(2024, 1, 1))
    hero = Player(username="LinkHero")
    rival = Player(username="LinkRival")
    db_session.add_all([season, hero, rival])
    await db_session.flush()
    db_session.add(
        Match(
            season_id=season.id, home_player_id=hero.id, away_player_id=rival.id, winner_id=hero.id,
            status=MatchStatus.COMPLETED, stage=MatchStage.GROUP,
            completed_at=datetime(2024, 2, 1, tzinfo=timezone.utc), home_score=2, away_score=0,
            replay_url="https://replay.pokemonshowdown.com/test-links",
            youtube_url="https://www.youtube.com/watch?v=test-links",
        )
    )
    await db_session.commit()

    response = await client.get(f"/api/players/{hero.id}")

    assert response.status_code == 200
    match = response.json()["completed_matches"][0]
    assert match["replay_url"] == "https://replay.pokemonshowdown.com/test-links"
    assert match["youtube_url"] == "https://www.youtube.com/watch?v=test-links"


async def test_player_links_absent_when_not_set(client: AsyncClient, db_session: AsyncSession) -> None:
    season = Season(name="No Links Season", start_date=date(2024, 1, 1))
    hero = Player(username="NoLinkHero")
    rival = Player(username="NoLinkRival")
    db_session.add_all([season, hero, rival])
    await db_session.flush()
    db_session.add(
        Match(
            season_id=season.id, home_player_id=hero.id, away_player_id=rival.id, winner_id=hero.id,
            status=MatchStatus.COMPLETED, stage=MatchStage.GROUP,
            completed_at=datetime(2024, 2, 1, tzinfo=timezone.utc), home_score=2, away_score=0,
        )
    )
    await db_session.commit()

    response = await client.get(f"/api/players/{hero.id}")

    assert response.status_code == 200
    match = response.json()["completed_matches"][0]
    assert match["replay_url"] is None
    assert match["youtube_url"] is None
