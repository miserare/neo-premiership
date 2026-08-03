from datetime import datetime, timezone

from app.models.match import Match, MatchStage
from app.schemas.match import MatchGameRead, MatchRead, MatchSeries
from app.schemas.player import PlayerSummary
from app.schemas.pokemon import MatchPokemonRead

# Sentinels so matches with a missing scheduled_at/completed_at sort to the
# tail of ascending/descending orderings without comparing None to None.
MIN_DT = datetime.min.replace(tzinfo=timezone.utc)
MAX_DT = datetime.max.replace(tzinfo=timezone.utc)


def _games_for(match: Match) -> list[MatchGameRead]:
    """A match's games, oldest first.

    Matches predating the series model (or created with only the legacy
    single replay_url) have no game rows, so one is synthesized - that way
    every consumer can render `games` and never has to special-case the
    old shape.
    """
    if match.games:
        return [MatchGameRead.model_validate(game) for game in match.games]
    if match.replay_url is not None:
        return [
            MatchGameRead(id=None, game_number=1, winner_id=match.winner_id, replay_url=match.replay_url)
        ]
    return []


def round_name(match: Match) -> str | None:
    """What to call a match's round in prose (stream labels and the like)."""
    return _round_fields(match)[0]


def _round_fields(match: Match) -> tuple[str | None, int | None]:
    """The label and position to report for a match.

    A playoff match takes both from the round it references. If it references
    none - it has been unassigned, or was never placed - it has no round name,
    and the legacy column is deliberately NOT consulted: falling back to it is
    the stale-copy behaviour this release exists to remove.

    A group-stage match has no round entity at all; its round_label is its own
    group/matchday label, which is current, not a copy of anything.
    """
    if match.playoff_round is not None:
        return match.playoff_round.label, match.playoff_round.display_order
    if match.stage == MatchStage.PLAYOFFS:
        return None, None
    return match.round_label, None


def to_match_read(match: Match) -> MatchRead:
    games = _games_for(match)
    round_label, round_order = _round_fields(match)
    home_wins = sum(1 for game in games if game.winner_id == match.home_player_id)
    away_wins = sum(1 for game in games if game.winner_id == match.away_player_id)

    return MatchRead(
        id=match.id,
        season_id=match.season_id,
        home_player=PlayerSummary.model_validate(match.home_player),
        away_player=PlayerSummary.model_validate(match.away_player),
        winner_id=match.winner_id,
        status=match.status,
        stage=match.stage,
        playoff_round_id=match.playoff_round_id,
        bracket_order=match.bracket_order,
        round_label=round_label,
        round_order=round_order,
        scheduled_at=match.scheduled_at,
        completed_at=match.completed_at,
        home_score=match.home_score,
        away_score=match.away_score,
        replay_url=match.replay_url,
        youtube_url=match.youtube_url,
        games=games,
        series=MatchSeries(home_wins=home_wins, away_wins=away_wins, game_count=len(games)),
        home_team=[
            MatchPokemonRead.model_validate(p) for p in match.pokemon if p.player_id == match.home_player_id
        ],
        away_team=[
            MatchPokemonRead.model_validate(p) for p in match.pokemon if p.player_id == match.away_player_id
        ],
    )


def match_recency(match: Match) -> datetime:
    """Best-effort timestamp for sorting - prefers completion time, falls back
    to when it was scheduled."""
    return match.completed_at or match.scheduled_at or MIN_DT
