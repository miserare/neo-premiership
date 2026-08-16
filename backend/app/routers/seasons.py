import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.crud import players as player_crud
from app.crud import playoff_rounds as round_crud
from app.crud import pokemon as pokemon_crud
from app.crud import season_entries as entry_crud
from app.crud import seasons as crud
from app.database import get_db
from app.schemas.playoff_round import (
    PlayoffRoundCreate,
    PlayoffRoundRead,
    PlayoffRoundReorder,
    PlayoffRoundUpdate,
)
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
from app.models.season import Season
from app.services.seasons import build_season_detail, get_current_season
from app.utils.slugs import RESERVED_SEASON_SLUGS, slugify_season_name

router = APIRouter(prefix="/seasons", tags=["seasons"])


async def _validate_champion(db: AsyncSession, champion_id: uuid.UUID | None) -> None:
    if champion_id is None:
        return
    player = await player_crud.get_player_by_id(db, champion_id)
    if player is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="champion_id does not reference an existing player"
        )


async def _resolve_slug(
    db: AsyncSession,
    requested: str | None,
    *,
    derive_from: str,
    exclude_id: uuid.UUID | None = None,
) -> str:
    """The slug to store, or an administrator-facing error. See routers.players.

    An omitted slug is derived from the season name, dropping a leading
    "Season" so "Season 6" becomes "6" - the word is already in the URL path.
    """
    slug = requested or slugify_season_name(derive_from)
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'No URL slug could be derived from "{derive_from}". Enter one explicitly.',
        )
    if slug in RESERVED_SEASON_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f'"{slug}" is reserved and cannot be used as a slug'
        )
    if await crud.slug_is_taken(db, slug, exclude_id=exclude_id):
        detail = (
            f'The slug "{slug}" is already used by another season.'
            if requested
            else f'The slug "{slug}" derived from that name is already taken. Enter a different one.'
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    return slug


async def _season_by_reference(db: AsyncSession, reference: str) -> Season | None:
    """Resolve a canonical slug, or a legacy UUID - see routers.players."""
    try:
        season_id = uuid.UUID(reference)
    except ValueError:
        return await crud.get_season_by_slug(db, reference)
    return await crud.get_season_by_id(db, season_id)


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
    slug = await _resolve_slug(db, season_in.slug, derive_from=season_in.name)
    try:
        return await crud.create_season(db, season_in, slug)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A season with that name or slug already exists"
        ) from None


# Declared before /{season_ref} so the literal path wins the match. "current" is
# also a reserved slug, so no season can shadow it.
@router.get("/current", response_model=SeasonDetail)
async def get_current_season_detail(db: AsyncSession = Depends(get_db)) -> SeasonDetail:
    """The season the league is in right now, for the bare /standings route.

    Between seasons this is the most recently *started* season, and the
    response's `is_active` flag is false - the page uses that to say it is
    showing a finished season rather than implying play is under way.
    """
    season, _is_active = await get_current_season(db)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No seasons have been scheduled yet")
    return await build_season_detail(db, season)


@router.get("/{season_ref}", response_model=SeasonDetail)
async def get_season(season_ref: str, db: AsyncSession = Depends(get_db)) -> SeasonDetail:
    """A season by canonical slug, or by legacy UUID."""
    season = await _season_by_reference(db, season_ref)
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
    # Renaming a season leaves its slug, and every link to it, alone.
    if "slug" in season_in.model_fields_set and season_in.slug is not None:
        await _resolve_slug(db, season_in.slug, derive_from=season.name, exclude_id=season.id)
    try:
        return await crud.update_season(db, season, season_in)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A season with that name or slug already exists"
        ) from None


@router.delete("/{season_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_season(season_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    season = await crud.get_season_by_id(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    await crud.delete_season(db, season)


# --------------------------------------------------------- playoff rounds


async def _season_or_404(db: AsyncSession, season_id: uuid.UUID):
    season = await crud.get_season_by_id(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return season


async def _round_or_404(db: AsyncSession, season_id: uuid.UUID, round_id: uuid.UUID):
    playoff_round = await round_crud.get_round_by_id(db, round_id)
    if playoff_round is None or playoff_round.season_id != season_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playoff round not found")
    return playoff_round


@router.get("/{season_id}/playoff-rounds", response_model=list[PlayoffRoundRead])
async def list_playoff_rounds(season_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[PlayoffRoundRead]:
    await _season_or_404(db, season_id)
    rounds = await round_crud.get_rounds_for_season(db, season_id)
    counts = await round_crud.count_matches_by_round(db, season_id)
    return [
        PlayoffRoundRead(
            id=playoff_round.id,
            season_id=playoff_round.season_id,
            label=playoff_round.label,
            display_order=playoff_round.display_order,
            match_count=counts.get(playoff_round.id, 0),
        )
        for playoff_round in rounds
    ]


@router.post(
    "/{season_id}/playoff-rounds",
    response_model=PlayoffRoundRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_playoff_round(
    season_id: uuid.UUID, round_in: PlayoffRoundCreate, db: AsyncSession = Depends(get_db)
) -> PlayoffRoundRead:
    await _season_or_404(db, season_id)
    try:
        playoff_round = await round_crud.create_round(db, season_id, round_in)
    except round_crud.DuplicatePositionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="another round in this season is already at that position",
        ) from None
    return PlayoffRoundRead.model_validate(playoff_round)


@router.put(
    "/{season_id}/playoff-rounds/reorder",
    response_model=list[PlayoffRoundRead],
    dependencies=[Depends(require_admin)],
)
async def reorder_playoff_rounds(
    season_id: uuid.UUID, reorder_in: PlayoffRoundReorder, db: AsyncSession = Depends(get_db)
) -> list[PlayoffRoundRead]:
    """Rewrite the season's round order from a complete ordered list of ids.

    Whole-list and transactional, so the bracket is never observed with two
    rounds in one position or a reorder applied halfway.
    """
    await _season_or_404(db, season_id)
    try:
        rounds = await round_crud.reorder_rounds(db, season_id, reorder_in.round_ids)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    counts = await round_crud.count_matches_by_round(db, season_id)
    return [
        PlayoffRoundRead(
            id=playoff_round.id,
            season_id=playoff_round.season_id,
            label=playoff_round.label,
            display_order=playoff_round.display_order,
            match_count=counts.get(playoff_round.id, 0),
        )
        for playoff_round in rounds
    ]


@router.patch(
    "/{season_id}/playoff-rounds/{round_id}",
    response_model=PlayoffRoundRead,
    dependencies=[Depends(require_admin)],
)
async def rename_playoff_round(
    season_id: uuid.UUID,
    round_id: uuid.UUID,
    round_in: PlayoffRoundUpdate,
    db: AsyncSession = Depends(get_db),
) -> PlayoffRoundRead:
    """Rename only - the round keeps its position."""
    await _season_or_404(db, season_id)
    playoff_round = await _round_or_404(db, season_id, round_id)
    updated = await round_crud.update_round(db, playoff_round, round_in)
    return PlayoffRoundRead(
        id=updated.id,
        season_id=updated.season_id,
        label=updated.label,
        display_order=updated.display_order,
        match_count=await round_crud.count_matches_in_round(db, updated.id),
    )


@router.delete(
    "/{season_id}/playoff-rounds/{round_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_playoff_round(
    season_id: uuid.UUID, round_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    await _season_or_404(db, season_id)
    playoff_round = await _round_or_404(db, season_id, round_id)
    try:
        await round_crud.delete_round(db, playoff_round)
    except round_crud.RoundNotEmptyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This round still contains {exc.match_count} match(es). "
                "Move them to another round or delete them first."
            ),
        ) from exc


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
