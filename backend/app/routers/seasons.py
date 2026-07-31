import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.crud import players as player_crud
from app.crud import pokemon as pokemon_crud
from app.crud import season_entries as entry_crud
from app.crud import seasons as crud
from app.database import get_db
from app.schemas.pokemon import RosterPokemonSet
from app.schemas.season import (
    SeasonCreate,
    SeasonDetail,
    SeasonEntryCreate,
    SeasonEntryRead,
    SeasonEntryUpdate,
    SeasonSummary,
    SeasonUpdate,
)
from app.services.seasons import build_season_detail

router = APIRouter(prefix="/seasons", tags=["seasons"])


async def _validate_champion(db: AsyncSession, champion_id: uuid.UUID | None) -> None:
    if champion_id is None:
        return
    player = await player_crud.get_player_by_id(db, champion_id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="champion_id does not reference an existing player"
        )


@router.get("", response_model=list[SeasonSummary])
async def list_seasons(
    skip: int = 0, limit: int = 100, q: str | None = None, db: AsyncSession = Depends(get_db)
) -> list[SeasonSummary]:
    return await crud.get_seasons(db, skip=skip, limit=limit, q=q)


@router.post(
    "", response_model=SeasonSummary, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)]
)
async def create_season(season_in: SeasonCreate, db: AsyncSession = Depends(get_db)) -> SeasonSummary:
    await _validate_champion(db, season_in.champion_id)
    try:
        return await crud.create_season(db, season_in)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A season with that name already exists"
        ) from None


@router.get("/{season_id}", response_model=SeasonDetail)
async def get_season(season_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> SeasonDetail:
    season = await crud.get_season_by_id(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return await build_season_detail(db, season)


@router.patch("/{season_id}", response_model=SeasonSummary, dependencies=[Depends(require_admin)])
async def update_season(
    season_id: uuid.UUID, season_in: SeasonUpdate, db: AsyncSession = Depends(get_db)
) -> SeasonSummary:
    season = await crud.get_season_by_id(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    if "champion_id" in season_in.model_fields_set:
        await _validate_champion(db, season_in.champion_id)
    try:
        return await crud.update_season(db, season, season_in)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A season with that name already exists"
        ) from None


@router.delete("/{season_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_season(season_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    season = await crud.get_season_by_id(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    await crud.delete_season(db, season)


@router.get("/{season_id}/roster", response_model=list[SeasonEntryRead])
async def list_roster(season_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[SeasonEntryRead]:
    season = await crud.get_season_by_id(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return await entry_crud.get_roster(db, season_id)


@router.post(
    "/{season_id}/roster",
    response_model=SeasonEntryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def add_roster_entry(
    season_id: uuid.UUID, entry_in: SeasonEntryCreate, db: AsyncSession = Depends(get_db)
) -> SeasonEntryRead:
    season = await crud.get_season_by_id(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    player = await player_crud.get_player_by_id(db, entry_in.player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    try:
        return await entry_crud.create_entry(db, season_id, entry_in)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That player is already on this season's roster"
        ) from None


@router.patch(
    "/{season_id}/roster/{entry_id}", response_model=SeasonEntryRead, dependencies=[Depends(require_admin)]
)
async def update_roster_entry(
    season_id: uuid.UUID, entry_id: uuid.UUID, entry_in: SeasonEntryUpdate, db: AsyncSession = Depends(get_db)
) -> SeasonEntryRead:
    entry = await entry_crud.get_entry_by_id(db, entry_id)
    if entry is None or entry.season_id != season_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster entry not found")
    return await entry_crud.update_entry(db, entry, entry_in)


@router.delete(
    "/{season_id}/roster/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)]
)
async def remove_roster_entry(
    season_id: uuid.UUID, entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    entry = await entry_crud.get_entry_by_id(db, entry_id)
    if entry is None or entry.season_id != season_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster entry not found")
    await entry_crud.delete_entry(db, entry)


@router.put(
    "/{season_id}/roster/{entry_id}/pokemon",
    response_model=SeasonEntryRead,
    dependencies=[Depends(require_admin)],
)
async def set_draft_pool(
    season_id: uuid.UUID,
    entry_id: uuid.UUID,
    pokemon_in: RosterPokemonSet,
    db: AsyncSession = Depends(get_db),
) -> SeasonEntryRead:
    """Update current ownership while retaining released Pokémon as history."""
    entry = await entry_crud.get_entry_by_id(db, entry_id)
    if entry is None or entry.season_id != season_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster entry not found")

    seen = {p.pokeapi_id for p in pokemon_in.pokemon}
    if len(seen) != len(pokemon_in.pokemon):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="the same Pokémon cannot be drafted twice by one player",
        )

    try:
        await pokemon_crud.replace_draft_pool(db, entry_id, pokemon_in)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    refreshed = await entry_crud.get_entry_by_id(db, entry_id, refresh=True)
    assert refreshed is not None
    return refreshed
