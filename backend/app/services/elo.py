import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.elo import EloRatingEvent
from app.models.match import Match, MatchStatus
from app.models.match_game import MatchGame
from app.models.player import Player

ELO_K_FACTOR = 64
_ONE_POINT = Decimal("1")


def expected_score(player_rating: int, opponent_rating: int) -> float:
    """Return Q_player / (Q_player + Q_opponent) from the league formula."""

    # Algebraically identical to Q_player / (Q_player + Q_opponent), but this
    # branch avoids overflowing 10**x if an administrator enters an extreme
    # starting rating.
    difference = (opponent_rating - player_rating) / 400
    if difference >= 0:
        inverse_ratio = 10 ** (-difference)
        return inverse_ratio / (1 + inverse_ratio)
    ratio = 10**difference
    return 1 / (1 + ratio)


def _round_rating_change(value: float) -> int:
    """Round half away from zero so whole-point ratings are deterministic."""

    return int(Decimal(str(value)).quantize(_ONE_POINT, rounding=ROUND_HALF_UP))


async def recalculate_elo_ratings(db: AsyncSession) -> None:
    """Rebuild all current ratings and history in completion-time order.

    Rebuilding is intentionally global. A corrected result from January can
    alter the inputs for every later match, and the league's data set is small
    enough that replaying it is both safer and simpler than a partial repair.
    The row locks serialize concurrent administrative result changes on
    PostgreSQL; SQLite harmlessly ignores ``FOR UPDATE`` in tests.
    """

    await db.flush()

    player_result = await db.execute(select(Player).order_by(Player.id).with_for_update())
    players = list(player_result.scalars().all())
    players_by_id = {player.id: player for player in players}
    ratings = {player.id: player.initial_elo_rating for player in players}

    await db.execute(delete(EloRatingEvent))

    game_result = await db.execute(
        select(MatchGame)
        .join(Match, Match.id == MatchGame.match_id)
        .where(
            Match.status == MatchStatus.COMPLETED,
            MatchGame.winner_id.is_not(None),
        )
        .options(joinedload(MatchGame.match))
        .order_by(
            func.coalesce(MatchGame.completed_at, Match.completed_at).asc().nullslast(),
            Match.id,
            MatchGame.game_number,
            MatchGame.id,
        )
        .with_for_update()
    )

    for game in game_result.scalars().all():
        match = game.match
        home_id = match.home_player_id
        away_id = match.away_player_id
        if home_id not in ratings or away_id not in ratings:
            continue
        if game.winner_id not in (home_id, away_id):
            continue
        occurred_at = game.completed_at or match.completed_at
        if occurred_at is None:
            continue

        home_before = ratings[home_id]
        away_before = ratings[away_id]
        home_expected = expected_score(home_before, away_before)

        if game.winner_id == home_id:
            home_result = 1
            winner_change = _round_rating_change(ELO_K_FACTOR * (1 - home_expected))
            home_change = winner_change
        else:
            home_result = 0
            winner_change = _round_rating_change(ELO_K_FACTOR * home_expected)
            home_change = -winner_change

        away_change = -home_change
        home_after = home_before + home_change
        away_after = away_before + away_change
        ratings[home_id] = home_after
        ratings[away_id] = away_after

        db.add_all(
            [
                EloRatingEvent(
                    match_id=match.id,
                    match_game_id=game.id,
                    player_id=home_id,
                    opponent_id=away_id,
                    occurred_at=occurred_at,
                    rating_before=home_before,
                    rating_after=home_after,
                    rating_change=home_change,
                    result=home_result,
                    expected_score=Decimal(f"{home_expected:.7f}"),
                ),
                EloRatingEvent(
                    match_id=match.id,
                    match_game_id=game.id,
                    player_id=away_id,
                    opponent_id=home_id,
                    occurred_at=occurred_at,
                    rating_before=away_before,
                    rating_after=away_after,
                    rating_change=away_change,
                    result=1 - home_result,
                    expected_score=Decimal(f"{1 - home_expected:.7f}"),
                ),
            ]
        )

    for player_id, rating in ratings.items():
        players_by_id[player_id].elo_rating = rating

    await db.flush()


async def get_player_elo_history(db: AsyncSession, player_id: uuid.UUID) -> list[EloRatingEvent]:
    result = await db.execute(
        select(EloRatingEvent)
        .join(MatchGame, EloRatingEvent.match_game_id == MatchGame.id)
        .where(EloRatingEvent.player_id == player_id)
        .options(
            joinedload(EloRatingEvent.opponent),
            joinedload(EloRatingEvent.match_game).joinedload(MatchGame.match),
        )
        .order_by(
            EloRatingEvent.occurred_at.desc(),
            EloRatingEvent.match_id.desc(),
            MatchGame.game_number.desc(),
            EloRatingEvent.match_game_id.desc(),
        )
    )
    return list(result.scalars().all())
