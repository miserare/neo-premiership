import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match_game import MatchGame
from app.schemas.match import MatchGamesSet
from app.services.elo import recalculate_elo_ratings


async def replace_games(db: AsyncSession, match_id: uuid.UUID, games_in: MatchGamesSet) -> None:
    """Swap a match's whole series for the supplied one.

    Delete-then-insert rather than a diff: the unique (match_id, game_number)
    constraint makes in-place renumbering order-dependent, and a series is at
    most a handful of rows.
    """
    try:
        await db.execute(delete(MatchGame).where(MatchGame.match_id == match_id))
        await db.flush()
        for game in games_in.games:
            db.add(
                MatchGame(
                    match_id=match_id,
                    game_number=game.game_number,
                    winner_id=game.winner_id,
                    completed_at=game.completed_at,
                    home_pokemon_score=game.home_pokemon_score,
                    away_pokemon_score=game.away_pokemon_score,
                    replay_url=str(game.replay_url) if game.replay_url is not None else None,
                )
            )
        await db.flush()
        await recalculate_elo_ratings(db)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
