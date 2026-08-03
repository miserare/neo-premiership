import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.crud import matches as match_crud
from app.crud import players as crud
from app.crud import season_entries as season_entry_crud
from app.database import get_db
from app.schemas.player import (
    PlayerAdmin,
    PlayerCreate,
    PlayerDetail,
    PlayerPublic,
    PlayerUpdate,
)
from app.services.records import build_player_detail
from app.services.elo import get_player_elo_history

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


@router.get("/{player_id}", response_model=PlayerDetail)
async def get_player(player_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PlayerDetail:
    player = await crud.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    matches = await match_crud.get_matches_for_player(db, player_id)
    season_entries = await season_entry_crud.get_player_season_entries(db, player_id)
    elo_history = await get_player_elo_history(db, player_id)
    return build_player_detail(player, matches, season_entries, elo_history)


# ------------------------------------------------------------ administrator


@router.post(
    "", response_model=PlayerAdmin, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)]
)
async def create_player(player_in: PlayerCreate, db: AsyncSession = Depends(get_db)) -> PlayerAdmin:
    _reject_reserved_username(player_in.username)
    existing = await crud.get_player_by_username(db, player_in.username)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    return await crud.create_player(db, player_in)


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
    return await crud.update_player(db, player, player_in)


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
