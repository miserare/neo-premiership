"""Seed the development database with sample players, seasons, matches, and
announcements so every public page has data to render.

Run with: python -m seeds.seed_dev (from the backend/ directory, with the
virtualenv active and DATABASE_URL pointing at a running Postgres instance).

Idempotent: players/seasons/announcements are looked up by their unique
username/name/title first, and left untouched if already present - so running
this against an already-seeded database adds nothing new and is safe.
"""
import asyncio
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.announcement import Announcement
from app.models.match import Match, MatchStage, MatchStatus
from app.models.match_game import MatchGame
from app.models.player import Player
from app.models.pokemon import SeasonRosterPokemon
from app.models.season import Season
from app.models.season_entry import SeasonEntry


async def _get_or_create_player(db: AsyncSession, username: str, **kwargs) -> tuple[Player, bool]:
    existing = (await db.execute(select(Player).where(Player.username == username))).scalar_one_or_none()
    if existing is not None:
        return existing, False
    player = Player(username=username, **kwargs)
    db.add(player)
    await db.flush()
    return player, True


async def _get_or_create_season(db: AsyncSession, name: str, **kwargs) -> tuple[Season, bool]:
    existing = (await db.execute(select(Season).where(Season.name == name))).scalar_one_or_none()
    if existing is not None:
        return existing, False
    season = Season(name=name, **kwargs)
    db.add(season)
    await db.flush()
    return season, True


async def _ensure_announcement(db: AsyncSession, title: str, **kwargs) -> None:
    existing = (await db.execute(select(Announcement).where(Announcement.title == title))).scalar_one_or_none()
    if existing is None:
        db.add(Announcement(title=title, **kwargs))


def _match(
    season: Season,
    home: Player,
    away: Player,
    *,
    stage: MatchStage,
    status: MatchStatus = MatchStatus.SCHEDULED,
    round_label: str | None = None,
    round_order: int | None = None,
    bracket_order: int | None = None,
    scheduled_at: datetime | None = None,
    completed_at: datetime | None = None,
    home_score: int | None = None,
    away_score: int | None = None,
    winner: Player | None = None,
    replay_url: str | None = None,
    youtube_url: str | None = None,
) -> Match:
    return Match(
        season_id=season.id,
        home_player_id=home.id,
        away_player_id=away.id,
        winner_id=winner.id if winner else None,
        status=status,
        stage=stage,
        round_label=round_label,
        round_order=round_order,
        bracket_order=bracket_order,
        scheduled_at=scheduled_at,
        completed_at=completed_at,
        home_score=home_score,
        away_score=away_score,
        replay_url=replay_url,
        youtube_url=youtube_url,
    )


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)

        ash, _ = await _get_or_create_player(
            db, "AshKetchum", discord_id="ash#0001", join_date=now - timedelta(days=400), elo_rating=1120
        )
        misty, _ = await _get_or_create_player(
            db, "MistyWaterflower", discord_id="misty#0002", join_date=now - timedelta(days=390), elo_rating=1010
        )
        brock, _ = await _get_or_create_player(
            db, "BrockRock", join_date=now - timedelta(days=380), is_active=False, elo_rating=950
        )
        gary, _ = await _get_or_create_player(
            db, "GaryOak", discord_id="gary#0003", join_date=now - timedelta(days=370), elo_rating=1085
        )
        may, _ = await _get_or_create_player(
            db, "MayMaple", discord_id="may#0004", join_date=now - timedelta(days=200), elo_rating=990
        )
        dawn, _ = await _get_or_create_player(
            db, "DawnBerlitz", discord_id="dawn#0005", join_date=now - timedelta(days=190), elo_rating=970
        )
        paul, _ = await _get_or_create_player(db, "PaulShinji", join_date=now - timedelta(days=60), elo_rating=1030)
        cynthia, _ = await _get_or_create_player(
            db, "CynthiaAurora", discord_id="cynthia#0006", join_date=now - timedelta(days=50), elo_rating=1150
        )

        season1, season1_created = await _get_or_create_season(
            db,
            "Season 1",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 4, 21),
            champion_id=ash.id,
            overview=(
                "The league's inaugural season: two groups of three played a single "
                "round-robin before the top four advanced to a two-round playoff bracket."
            ),
            sheet_url="https://docs.google.com/spreadsheets/d/1Season1StandingsAndSchedule/edit",
        )
        if season1_created:
            db.add_all(
                [
                    SeasonEntry(season_id=season1.id, player_id=ash.id, group_label="Group A"),
                    SeasonEntry(season_id=season1.id, player_id=misty.id, group_label="Group A"),
                    SeasonEntry(season_id=season1.id, player_id=brock.id, group_label="Group A"),
                    SeasonEntry(season_id=season1.id, player_id=gary.id, group_label="Group B", tiebreaker_value=3),
                    SeasonEntry(season_id=season1.id, player_id=may.id, group_label="Group B", tiebreaker_value=1),
                    SeasonEntry(season_id=season1.id, player_id=dawn.id, group_label="Group B", tiebreaker_value=-2),
                ]
            )

            group_start = datetime(2025, 1, 13, tzinfo=timezone.utc)
            db.add_all(
                [
                    _match(
                        season1, ash, misty, stage=MatchStage.GROUP, status=MatchStatus.COMPLETED,
                        round_label="Group A", completed_at=group_start, home_score=2, away_score=1, winner=ash,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-1000000001",
                        youtube_url="https://www.youtube.com/watch?v=neo-s1-ash-misty",
                    ),
                    _match(
                        season1, ash, brock, stage=MatchStage.GROUP, status=MatchStatus.COMPLETED,
                        round_label="Group A", completed_at=group_start + timedelta(days=2),
                        home_score=2, away_score=0, winner=ash,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-1000000002",
                    ),
                    _match(
                        season1, misty, brock, stage=MatchStage.GROUP, status=MatchStatus.COMPLETED,
                        round_label="Group A", completed_at=group_start + timedelta(days=4),
                        home_score=2, away_score=1, winner=misty,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-1000000003",
                    ),
                    _match(
                        season1, gary, may, stage=MatchStage.GROUP, status=MatchStatus.COMPLETED,
                        round_label="Group B", completed_at=group_start + timedelta(days=1),
                        home_score=2, away_score=0, winner=gary,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-1000000004",
                        youtube_url="https://www.youtube.com/watch?v=neo-s1-gary-may",
                    ),
                    _match(
                        season1, gary, dawn, stage=MatchStage.GROUP, status=MatchStatus.COMPLETED,
                        round_label="Group B", completed_at=group_start + timedelta(days=3),
                        home_score=2, away_score=1, winner=gary,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-1000000005",
                    ),
                    _match(
                        season1, may, dawn, stage=MatchStage.GROUP, status=MatchStatus.COMPLETED,
                        round_label="Group B", completed_at=group_start + timedelta(days=5),
                        home_score=2, away_score=0, winner=may,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-1000000006",
                    ),
                ]
            )

            playoffs_start = datetime(2025, 3, 1, tzinfo=timezone.utc)
            db.add_all(
                [
                    _match(
                        season1, ash, may, stage=MatchStage.PLAYOFFS, status=MatchStatus.COMPLETED,
                        round_label="Semifinal", round_order=1, bracket_order=1,
                        completed_at=playoffs_start, home_score=2, away_score=1, winner=ash,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-1000000007",
                        youtube_url="https://www.youtube.com/watch?v=neo-s1-semi-ash-may",
                    ),
                    _match(
                        season1, gary, misty, stage=MatchStage.PLAYOFFS, status=MatchStatus.COMPLETED,
                        round_label="Semifinal", round_order=1, bracket_order=2,
                        completed_at=playoffs_start + timedelta(days=1), home_score=2, away_score=0, winner=gary,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-1000000008",
                    ),
                    _match(
                        season1, ash, gary, stage=MatchStage.PLAYOFFS, status=MatchStatus.COMPLETED,
                        round_label="Final", round_order=2, bracket_order=1,
                        completed_at=datetime(2025, 4, 21, tzinfo=timezone.utc), home_score=2, away_score=1,
                        winner=ash,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-1000000009",
                        youtube_url="https://www.youtube.com/watch?v=neo-s1-final-ash-gary",
                    ),
                ]
            )

        season2, season2_created = await _get_or_create_season(
            db,
            "Season 2",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 9, 30),
            overview=(
                "The current season: a single round-robin group stage is underway, "
                "with playoffs to follow once every group match has been played."
            ),
            sheet_url="https://docs.google.com/spreadsheets/d/1Season2StandingsAndSchedule/edit",
        )
        if season2_created:
            db.add_all(
                [
                    SeasonEntry(season_id=season2.id, player_id=ash.id, tiebreaker_value=1),
                    SeasonEntry(season_id=season2.id, player_id=misty.id, tiebreaker_value=0),
                    SeasonEntry(season_id=season2.id, player_id=gary.id),
                    SeasonEntry(season_id=season2.id, player_id=may.id),
                    SeasonEntry(season_id=season2.id, player_id=dawn.id),
                    SeasonEntry(season_id=season2.id, player_id=paul.id),
                    SeasonEntry(season_id=season2.id, player_id=cynthia.id),
                ]
            )

            db.add_all(
                [
                    _match(
                        season2, ash, paul, stage=MatchStage.GROUP, status=MatchStatus.COMPLETED,
                        completed_at=datetime(2026, 7, 5, tzinfo=timezone.utc), home_score=2, away_score=0,
                        winner=ash,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-2000000001",
                        youtube_url="https://www.youtube.com/watch?v=neo-s2-ash-paul",
                    ),
                    _match(
                        season2, misty, cynthia, stage=MatchStage.GROUP, status=MatchStatus.COMPLETED,
                        completed_at=datetime(2026, 7, 12, tzinfo=timezone.utc), home_score=1, away_score=2,
                        winner=cynthia,
                        replay_url="https://replay.pokemonshowdown.com/gen9nationaldex-2000000002",
                    ),
                    _match(
                        season2, gary, may, stage=MatchStage.GROUP, status=MatchStatus.SCHEDULED,
                        scheduled_at=datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc),
                    ),
                    _match(
                        season2, dawn, paul, stage=MatchStage.GROUP, status=MatchStatus.SCHEDULED,
                        scheduled_at=datetime(2026, 8, 5, 19, 0, tzinfo=timezone.utc),
                    ),
                    _match(
                        season2, ash, cynthia, stage=MatchStage.GROUP, status=MatchStatus.SCHEDULED,
                        scheduled_at=datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc),
                    ),
                    _match(
                        season2, gary, dawn, stage=MatchStage.GROUP, status=MatchStatus.CANCELLED,
                        scheduled_at=datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc),
                    ),
                ]
            )

        await _seed_draft_pools(db)
        await _seed_playoff_series(db)

        await _ensure_announcement(
            db,
            "Season 2 group stage is underway!",
            body="Group matches are being played through September - check the schedule sheet for your upcoming games.",
            published_at=now - timedelta(days=20),
            link_url="https://docs.google.com/spreadsheets/d/1Season2StandingsAndSchedule/edit",
        )
        await _ensure_announcement(
            db,
            "Season 1 recap and Season 2 signups",
            body="Congratulations to AshKetchum on winning Season 1! Signups for Season 2 are now closed - see you next season.",
            published_at=now - timedelta(days=95),
        )
        await _ensure_announcement(
            db,
            "New rule: Sleep Clause enforced league-wide",
            body="Starting immediately, all matches follow the standard Sleep Clause. Report violations to a moderator.",
            published_at=now - timedelta(days=150),
        )

        await db.commit()
        print("Seed complete.")


async def _seed_draft_pools(db: AsyncSession) -> None:
    """Give each Season 1 roster entry a drafted pool so the sprite rosters on
    the season and player pages have something to render. Skipped entirely once
    any pool exists, keeping the seeder idempotent."""
    existing = (await db.execute(select(SeasonRosterPokemon).limit(1))).scalars().first()
    if existing is not None:
        return

    season1 = (await db.execute(select(Season).where(Season.name == "Season 1"))).scalar_one_or_none()
    if season1 is None:
        return

    pools = {
        "AshKetchum": [(6, "Charizard"), (25, "Pikachu"), (448, "Lucario"), (149, "Dragonite")],
        "MistyWaterflower": [(9, "Blastoise"), (130, "Gyarados"), (131, "Lapras"), (121, "Starmie")],
        "BrockRock": [(95, "Onix"), (208, "Steelix"), (112, "Rhydon"), (76, "Golem")],
        "GaryOak": [(3, "Venusaur"), (94, "Gengar"), (248, "Tyranitar"), (373, "Salamence")],
        "MayMaple": [(257, "Blaziken"), (282, "Gardevoir"), (260, "Swampert"), (306, "Aggron")],
        "DawnBerlitz": [(392, "Infernape"), (445, "Garchomp"), (462, "Magnezone"), (395, "Empoleon")],
    }
    entries = (
        (await db.execute(select(SeasonEntry).where(SeasonEntry.season_id == season1.id))).scalars().all()
    )
    players = {p.id: p.username for p in (await db.execute(select(Player))).scalars().all()}

    for entry in entries:
        pool = pools.get(players.get(entry.player_id, ""))
        if not pool:
            continue
        for slot, (pokeapi_id, species_name) in enumerate(pool):
            db.add(
                SeasonRosterPokemon(
                    season_entry_id=entry.id,
                    pokeapi_id=pokeapi_id,
                    species_name=species_name,
                    slot=slot,
                )
            )
    await db.flush()


async def _seed_playoff_series(db: AsyncSession) -> None:
    """Turn Season 1's Final into a best-of-three so the per-game replay links
    have a real example to render."""
    final = (
        await db.execute(
            select(Match).where(Match.round_label == "Final", Match.stage == MatchStage.PLAYOFFS)
        )
    ).scalars().first()
    if final is None:
        return

    # Scoped to this match: the migration backfills a game row for every match
    # that had a replay_url, so "any game exists" would always be true here.
    already = (
        await db.execute(select(MatchGame).where(MatchGame.match_id == final.id).limit(2))
    ).scalars().all()
    if len(already) > 1:
        return
    # Replace the single backfilled game with the three-game series.
    await db.execute(sa_delete(MatchGame).where(MatchGame.match_id == final.id))

    winner_id, loser_id = final.winner_id, final.away_player_id
    if winner_id == final.away_player_id:
        loser_id = final.home_player_id

    for game_number, game_winner in ((1, winner_id), (2, loser_id), (3, winner_id)):
        db.add(
            MatchGame(
                match_id=final.id,
                game_number=game_number,
                winner_id=game_winner,
                replay_url=f"https://replay.pokemonshowdown.com/gen9nationaldex-final-g{game_number}",
            )
        )
    await db.flush()


if __name__ == "__main__":
    asyncio.run(seed())
