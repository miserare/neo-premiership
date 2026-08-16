import uuid

from app.models.elo import EloRatingEvent
from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.season import Season
from app.models.season_entry import SeasonEntry
from app.schemas.player import (
    ChampionshipRead,
    EloRatingHistoryEntry,
    PlayerDetail,
    PlayerRecord,
    PlayerSeasonRecord,
)
from app.schemas.pokemon import SeasonRosterPokemonRead
from app.services.matches import MAX_DT, match_recency, to_match_read


def _record_from_matches(player_id: uuid.UUID, matches: list[Match]) -> PlayerRecord:
    wins = sum(1 for m in matches if m.winner_id == player_id)
    losses = sum(1 for m in matches if m.winner_id is not None and m.winner_id != player_id)
    return PlayerRecord(wins=wins, losses=losses)


def championships_for(player: Player, champion_seasons: list[Season]) -> list[ChampionshipRead]:
    """The seasons this player is recorded as champion of, newest first.

    Derived from `seasons.champion_id` on every read - there is no stored
    `is_champion` flag that could drift out of step with it.

    The placeholder player is excluded outright. Deleting a player transfers
    their championships onto the tombstone so the bracket still shows a winner,
    but "Deleted Player" is not a champion anyone should see decorated.
    """
    if player.is_placeholder:
        return []
    return [
        ChampionshipRead(
            season_id=season.id,
            season_slug=season.slug,
            season_name=season.name,
            start_date=season.start_date,
            end_date=season.end_date,
        )
        for season in champion_seasons
        if season.champion_id == player.id
    ]


def build_player_detail(
    player: Player,
    matches: list[Match],
    season_entries: list[SeasonEntry],
    elo_history: list[EloRatingEvent],
    champion_seasons: list[Season],
) -> PlayerDetail:
    # A completed match only counts toward a record once it has a valid winner.
    completed = [m for m in matches if m.status == MatchStatus.COMPLETED and m.winner_id is not None]
    backlog = [m for m in matches if m.status == MatchStatus.SCHEDULED]

    backlog.sort(key=lambda m: m.scheduled_at or MAX_DT)
    # Newest first, and the page's "Recent Matches" section is simply the head
    # of this list - so both views are guaranteed to agree.
    completed.sort(key=match_recency, reverse=True)

    matches_by_season: dict[uuid.UUID, list[Match]] = {}
    for match in completed:
        matches_by_season.setdefault(match.season_id, []).append(match)

    # season_entries is already ordered newest season first.
    season_records = [
        PlayerSeasonRecord(
            season_id=entry.season_id,
            season_slug=entry.season.slug,
            season_name=entry.season.name,
            pokemon=[SeasonRosterPokemonRead.model_validate(p) for p in entry.pokemon],
            former_pokemon=[
                SeasonRosterPokemonRead.model_validate(p) for p in entry.former_pokemon
            ],
            **_record_from_matches(player.id, matches_by_season.get(entry.season_id, [])).model_dump(),
        )
        for entry in season_entries
    ]

    return PlayerDetail(
        id=player.id,
        slug=player.slug,
        username=player.username,
        biography=player.biography,
        join_date=player.join_date,
        is_active=player.is_active,
        elo_rating=player.elo_rating,
        championships=championships_for(player, champion_seasons),
        elo_history=[
            EloRatingHistoryEntry(
                match_id=event.match_id,
                opponent_id=event.opponent_id,
                opponent_slug=event.opponent.slug,
                opponent_username=event.opponent.username,
                occurred_at=event.occurred_at,
                result=event.result,
                expected_score=float(event.expected_score),
                rating_before=event.rating_before,
                rating_after=event.rating_after,
                rating_change=event.rating_change,
            )
            for event in elo_history
        ],
        most_recent_season_record=season_records[0] if season_records else None,
        historical_record=_record_from_matches(player.id, completed),
        season_records=season_records,
        backlog=[to_match_read(m) for m in backlog],
        completed_matches=[to_match_read(m) for m in completed],
    )
