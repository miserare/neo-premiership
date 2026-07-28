import uuid

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.match_game import MatchGame
from app.models.player import Player
from app.models.pokemon import MatchPokemon
from app.models.season import Season
from app.schemas.player import PlayerCreate, PlayerUpdate

# Reserved for the tombstone player that inherits a deleted player's matches.
PLACEHOLDER_USERNAME = "Deleted Player"


async def create_player(db: AsyncSession, player_in: PlayerCreate) -> Player:
    data = player_in.model_dump()
    # elo_rating is optional on input; omit rather than pass None so the
    # model's own NOT NULL default (1000) applies.
    if data.get("elo_rating") is None:
        data.pop("elo_rating", None)
    player = Player(**data)
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


async def get_players(db: AsyncSession, skip: int = 0, limit: int = 100, q: str | None = None) -> list[Player]:
    # The tombstone player is an implementation detail of deletion - it must
    # never appear in the public roster or in any admin picker, all of which
    # source their options from here.
    stmt = select(Player).where(Player.is_placeholder.is_(False)).order_by(Player.join_date)
    if q:
        stmt = stmt.where(Player.username.ilike(f"%{q}%"))
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_player_by_id(db: AsyncSession, player_id: uuid.UUID) -> Player | None:
    result = await db.execute(select(Player).where(Player.id == player_id))
    return result.scalar_one_or_none()


async def get_player_by_username(db: AsyncSession, username: str) -> Player | None:
    result = await db.execute(select(Player).where(Player.username == username))
    return result.scalar_one_or_none()


async def update_player(db: AsyncSession, player: Player, player_in: PlayerUpdate) -> Player:
    data = player_in.model_dump(exclude_unset=True)
    if data.get("elo_rating") is None:
        data.pop("elo_rating", None)
    for field, value in data.items():
        setattr(player, field, value)
    await db.commit()
    await db.refresh(player)
    return player


async def get_placeholder_player(db: AsyncSession) -> Player | None:
    result = await db.execute(select(Player).where(Player.is_placeholder.is_(True)))
    return result.scalars().first()


async def get_or_create_placeholder_player(db: AsyncSession) -> Player:
    """The single tombstone player deleted players' matches are reassigned to.

    Created lazily on the first deletion so a league that never deletes anyone
    never grows a phantom roster entry.
    """
    existing = await get_placeholder_player(db)
    if existing is not None:
        return existing
    placeholder = Player(username=PLACEHOLDER_USERNAME, is_placeholder=True, is_active=False)
    db.add(placeholder)
    await db.commit()
    await db.refresh(placeholder)
    return placeholder


async def delete_player(db: AsyncSession, player: Player) -> None:
    """Delete a player while preserving their match history.

    Every match reference is moved onto the placeholder player *and committed*
    before the row is deleted. That ordering is load-bearing: matches.home/away
    are ON DELETE CASCADE, so deleting in the same transaction as the reassign
    would take the matches with it.
    """
    placeholder = await get_or_create_placeholder_player(db)

    # A match between this player and the placeholder would end up with the same
    # player on both sides, violating ck_matches_distinct_players. There's no
    # meaningful record left in that case, so drop those matches.
    await db.execute(
        delete(Match).where(
            or_(
                and_(Match.home_player_id == player.id, Match.away_player_id == placeholder.id),
                and_(Match.away_player_id == player.id, Match.home_player_id == placeholder.id),
            )
        )
    )

    await db.execute(
        update(Match).where(Match.home_player_id == player.id).values(home_player_id=placeholder.id)
    )
    await db.execute(
        update(Match).where(Match.away_player_id == player.id).values(away_player_id=placeholder.id)
    )
    await db.execute(update(Match).where(Match.winner_id == player.id).values(winner_id=placeholder.id))
    await db.execute(
        update(MatchGame).where(MatchGame.winner_id == player.id).values(winner_id=placeholder.id)
    )
    await db.execute(
        update(MatchPokemon).where(MatchPokemon.player_id == player.id).values(player_id=placeholder.id)
    )
    # Championships transfer to the placeholder too. Leaving them to the FK's
    # ON DELETE SET NULL would blank the champion while the bracket still shows
    # them winning the final, and it also means no season row still references
    # the player when db.delete() runs below.
    await db.execute(
        update(Season).where(Season.champion_id == player.id).values(champion_id=placeholder.id)
    )
    await db.commit()

    # Their season roster entries (and drafted pools) still cascade away - the
    # roster is a record of who played that season, which they no longer did.
    await db.delete(player)
    await db.commit()
