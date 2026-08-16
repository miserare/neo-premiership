import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.crud import matches as match_crud
from app.crud import players as crud
from app.crud import season_entries as season_entry_crud
from app.crud import seasons as season_crud
from app.database import get_db
from app.models.player import Player
from app.schemas.player import (
    PlayerAdmin,
    PlayerCreate,
    PlayerDetail,
    PlayerPublic,
    PlayerUpdate,
)
from app.services.records import build_player_detail
from app.services.elo import get_player_elo_history
from app.utils.slugs import RESERVED_PLAYER_SLUGS, slugify

router = APIRouter(prefix="/players", tags=["players"])


def _reject_reserved_username(username: str) -> None:
    """The placeholder player is looked up by its is_placeholder flag, but letting
    a real player take its display name would make deleted-player attribution
    unreadable in match lists."""
    if username.strip().casefold() == crud.PLACEHOLDER_USERNAME.casefold():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'"{crud.PLACEHOLDER_USERNAME}" is reserved for deleted players',
        )


async def _resolve_slug(
    db: AsyncSession,
    requested: str | None,
    *,
    derive_from: str,
    exclude_id: uuid.UUID | None = None,
) -> str:
    """The slug to store, or an administrator-facing error explaining why not.

    An omitted slug is derived from the username. Deriving can legitimately
    fail - a username with no ASCII characters slugifies to nothing - and a
    derived slug can collide, so both cases ask for an explicit one rather than
    inventing `psykick-2` behind the administrator's back.
    """
    slug = requested or slugify(derive_from)
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'No URL slug could be derived from "{derive_from}". Enter one explicitly.',
        )
    if slug in RESERVED_PLAYER_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f'"{slug}" is reserved and cannot be used as a slug'
        )
    if await crud.slug_is_taken(db, slug, exclude_id=exclude_id):
        detail = (
            f'The slug "{slug}" is already used by another player.'
            if requested
            else f'The slug "{slug}" derived from that username is already taken. Enter a different one.'
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    return slug


async def _player_by_reference(db: AsyncSession, reference: str) -> Player | None:
    """Resolve a canonical slug, or a legacy UUID.

    Both forms are supported permanently on the API: the frontend redirects
    /players/<uuid> to the canonical slug route, and it can only do that by
    first resolving the UUID.
    """
    try:
        player_id = uuid.UUID(reference)
    except ValueError:
        return await crud.get_player_by_slug(db, reference)
    return await crud.get_player_by_id(db, player_id)


# ------------------------------------------------------------------- public


@router.get("", response_model=list[PlayerPublic])
async def list_players(
    skip: int = 0, limit: int = 100, q: str | None = None, db: AsyncSession = Depends(get_db)
) -> list[PlayerPublic]:
    """Public roster. PlayerPublic has no discord_id field, so contact details
    cannot leak here even though the ORM objects carry them."""
    return await crud.get_players(db, skip=skip, limit=limit, q=q)


@router.get("/admin/list", response_model=list[PlayerAdmin], dependencies=[Depends(require_admin)])
async def list_players_admin(
    skip: int = 0, limit: int = 500, q: str | None = None, db: AsyncSession = Depends(get_db)
) -> list[PlayerAdmin]:
    """Administrative roster, including private fields such as discord_id."""
    return await crud.get_players(db, skip=skip, limit=limit, q=q)


@router.get("/{player_ref}", response_model=PlayerDetail)
async def get_player(player_ref: str, db: AsyncSession = Depends(get_db)) -> PlayerDetail:
    """Public profile, by canonical slug or by legacy UUID.

    PlayerDetail declares no discord_id, so a slug lookup exposes exactly what
    a UUID lookup always has - no more.
    """
    player = await _player_by_reference(db, player_ref)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    matches = await match_crud.get_matches_for_player(db, player.id)
    season_entries = await season_entry_crud.get_player_season_entries(db, player.id)
    elo_history = await get_player_elo_history(db, player.id)
    # One query for every championship rather than one per season.
    championships = await season_crud.get_champion_seasons(db)
    return build_player_detail(player, matches, season_entries, elo_history, championships)


# ------------------------------------------------------------ administrator


@router.post(
    "", response_model=PlayerAdmin, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)]
)
async def create_player(player_in: PlayerCreate, db: AsyncSession = Depends(get_db)) -> PlayerAdmin:
    _reject_reserved_username(player_in.username)
    existing = await crud.get_player_by_username(db, player_in.username)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    slug = await _resolve_slug(db, player_in.slug, derive_from=player_in.username)
    try:
        return await crud.create_player(db, player_in, slug)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That username or slug is already taken"
        ) from None


@router.patch("/{player_id}", response_model=PlayerAdmin, dependencies=[Depends(require_admin)])
async def update_player(
    player_id: uuid.UUID, player_in: PlayerUpdate, db: AsyncSession = Depends(get_db)
) -> PlayerAdmin:
    player = await crud.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    if player_in.username is not None and player_in.username != player.username:
        _reject_reserved_username(player_in.username)
        existing = await crud.get_player_by_username(db, player_in.username)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    # Only a slug that was actually sent is validated. Renaming a player leaves
    # their slug - and every link to it - untouched.
    if "slug" in player_in.model_fields_set and player_in.slug is not None:
        await _resolve_slug(db, player_in.slug, derive_from=player.username, exclude_id=player.id)
    try:
        return await crud.update_player(db, player, player_in)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That username or slug is already taken"
        ) from None


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_player(player_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a player, reassigning their matches to the placeholder player so
    the league's match history stays intact."""
    player = await crud.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    if player.is_placeholder:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The placeholder player holds deleted players' match history and cannot be removed",
        )
    await crud.delete_player(db, player)
