from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import matches as match_crud
from app.crud import playoff_rounds as playoff_round_crud
from app.crud import season_entries as season_entry_crud
from app.crud import seasons as season_crud
from app.models.match import MatchStage
from app.models.season import Season
from app.schemas.player import PlayerSummary
from app.schemas.pokemon import SeasonRosterPokemonRead
from app.schemas.season import RosterEntry, SeasonDetail, SeasonStream
from app.services.matches import match_recency, round_name
from app.services.standings import build_bracket, build_standings


def is_season_active(season: Season, today: date) -> bool:
    return season.start_date <= today and (season.end_date is None or season.end_date >= today)


async def get_current_season(db: AsyncSession, today: date | None = None) -> tuple[Season | None, bool]:
    """The season to show as "current": the active season if one exists,
    otherwise the most recently started season (off-season), or (None, False)
    if the league has no seasons at all."""
    today = today or datetime.now(timezone.utc).date()
    active = await season_crud.get_active_season(db, today)
    if active is not None:
        return active, True
    latest = await season_crud.get_most_recently_started_season(db)
    return latest, False


async def build_season_detail(db: AsyncSession, season: Season, today: date | None = None) -> SeasonDetail:
    today = today or datetime.now(timezone.utc).date()
    roster_entries = await season_entry_crud.get_roster(db, season.id)
    group_matches = await match_crud.get_matches_for_season(db, season.id, stage=MatchStage.GROUP)
    playoff_matches = await match_crud.get_matches_for_season(db, season.id, stage=MatchStage.PLAYOFFS)
    # Rounds are fetched in their own right, so a season can show a round that
    # has no matches yet. One extra query, not one per round.
    rounds = await playoff_round_crud.get_rounds_for_season(db, season.id)

    stream_matches = [m for m in (*group_matches, *playoff_matches) if m.youtube_url]
    stream_matches.sort(key=match_recency, reverse=True)
    streams = [
        SeasonStream(
            url=match.youtube_url,
            label=f"{match.home_player.username} vs {match.away_player.username} "
            f"({round_name(match) or match.stage.value.title()})",
        )
        for match in stream_matches
    ]

    return SeasonDetail(
        id=season.id,
        name=season.name,
        start_date=season.start_date,
        end_date=season.end_date,
        is_active=is_season_active(season, today),
        sheet_url=season.sheet_url,
        overview=season.overview,
        champion=PlayerSummary.model_validate(season.champion) if season.champion else None,
        roster=[
            RosterEntry(
                player=PlayerSummary.model_validate(entry.player),
                group_label=entry.group_label,
                pokemon=[SeasonRosterPokemonRead.model_validate(p) for p in entry.pokemon],
                former_pokemon=[
                    SeasonRosterPokemonRead.model_validate(p) for p in entry.former_pokemon
                ],
            )
            for entry in roster_entries
        ],
        standings=build_standings(roster_entries, group_matches),
        bracket=build_bracket(rounds, playoff_matches),
        streams=streams,
    )
