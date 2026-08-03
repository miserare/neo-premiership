import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.crud import match_games as game_crud
from app.crud import matches as crud
from app.crud import players as player_crud
from app.crud import pokemon as pokemon_crud
from app.crud import seasons as season_crud
from app.database import get_db
from app.models.match import MatchStatus
from app.schemas.match import MatchCreate, MatchGamesSet, MatchRead, MatchUpdate
from app.schemas.pokemon import MatchPokemonSet
from app.services.matches import to_match_read

router = APIRouter(prefix="/matches", tags=["matches"])


async def _get_match_or_404(db: AsyncSession, match_id: uuid.UUID, refresh: bool = False):
    match = await crud.get_match_by_id(db, match_id, refresh=refresh)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    return match


@router.get("", response_model=list[MatchRead])
async def list_matches(season_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[MatchRead]:
    """All matches in a season. season_id is required - the admin match list is
    always scoped to one season, and an unbounded league-wide listing has no
    caller and no pagination story."""
    season = await season_crud.get_season_by_id(db, season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    matches = await crud.get_matches_for_season(db, season_id)
    return [to_match_read(match) for match in matches]


@router.post(
    "", response_model=MatchRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)]
)
async def create_match(match_in: MatchCreate, db: AsyncSession = Depends(get_db)) -> MatchRead:
    season = await season_crud.get_season_by_id(db, match_in.season_id)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    home = await player_crud.get_player_by_id(db, match_in.home_player_id)
    if home is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="home_player_id does not reference an existing player"
        )
    away = await player_crud.get_player_by_id(db, match_in.away_player_id)
    if away is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="away_player_id does not reference an existing player"
        )
    match = await crud.create_match(db, match_in)
    return to_match_read(match)


@router.get("/{match_id}", response_model=MatchRead)
async def get_match(match_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> MatchRead:
    match = await _get_match_or_404(db, match_id)
    return to_match_read(match)


@router.patch("/{match_id}", response_model=MatchRead, dependencies=[Depends(require_admin)])
async def update_match(match_id: uuid.UUID, match_in: MatchUpdate, db: AsyncSession = Depends(get_db)) -> MatchRead:
    match = await _get_match_or_404(db, match_id)

    # Validate against the *merged* state (existing row + incoming patch), not
    # just the patch fields in isolation - a PATCH that only sets `status` to
    # completed must still see a winner_id that was set in an earlier request.
    winner_id = match_in.winner_id if "winner_id" in match_in.model_fields_set else match.winner_id
    new_status = match_in.status if "status" in match_in.model_fields_set else match.status
    completed_at = match_in.completed_at if "completed_at" in match_in.model_fields_set else match.completed_at

    if winner_id is not None and winner_id not in (match.home_player_id, match.away_player_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="winner_id must be the home or away player"
        )
    if new_status == MatchStatus.COMPLETED and winner_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="a completed match requires a winner_id"
        )
    if new_status == MatchStatus.COMPLETED and completed_at is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="a completed match requires completed_at for Elo ordering",
        )

    updated = await crud.update_match(db, match, match_in)
    return to_match_read(updated)


@router.put("/{match_id}/games", response_model=MatchRead, dependencies=[Depends(require_admin)])
async def set_match_games(
    match_id: uuid.UUID, games_in: MatchGamesSet, db: AsyncSession = Depends(get_db)
) -> MatchRead:
    """Replace a match's games - this is how a best-of-three gets its per-game
    winners and replay links."""
    match = await _get_match_or_404(db, match_id)

    participants = (match.home_player_id, match.away_player_id)
    for game in games_in.games:
        if game.winner_id is not None and game.winner_id not in participants:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"game {game.game_number}: winner_id must be the home or away player",
            )

    await game_crud.replace_games(db, match_id, games_in)
    refreshed = await _get_match_or_404(db, match_id, refresh=True)
    return to_match_read(refreshed)


@router.put("/{match_id}/teams/{player_id}", response_model=MatchRead, dependencies=[Depends(require_admin)])
async def set_match_team(
    match_id: uuid.UUID,
    player_id: uuid.UUID,
    pokemon_in: MatchPokemonSet,
    db: AsyncSession = Depends(get_db),
) -> MatchRead:
    """Replace one brought-team snapshot, validating ownership at match time."""
    match = await _get_match_or_404(db, match_id)
    if player_id not in (match.home_player_id, match.away_player_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="player_id must be the home or away player of this match",
        )

    requested_ids = [pokemon.pokeapi_id for pokemon in pokemon_in.pokemon]
    if len(requested_ids) != len(set(requested_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="the same Pokémon cannot appear twice on one match team",
        )

    played_at = match.completed_at or match.scheduled_at
    history = await pokemon_crud.get_eligible_roster_pokemon(
        db, match.season_id, player_id, played_at=None
    )
    if history:
        eligible = (
            history
            if played_at is None
            else await pokemon_crud.get_eligible_roster_pokemon(
                db, match.season_id, player_id, played_at=played_at
            )
        )
        # An already-recorded snapshot remains valid even if incomplete legacy
        # ownership data does not cover it. This prevents an unrelated edit
        # from erasing historical truth.
        existing_ids = await pokemon_crud.get_match_team_ids(db, match_id, player_id)
        allowed_ids = {pokemon.pokeapi_id for pokemon in eligible} | existing_ids
        invalid = [
            pokemon.species_name
            for pokemon in pokemon_in.pokemon
            if pokemon.pokeapi_id not in allowed_ids
        ]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "not owned by this player at the match time: "
                    + ", ".join(invalid)
                ),
            )

    await pokemon_crud.replace_match_team(db, match_id, player_id, pokemon_in)
    refreshed = await _get_match_or_404(db, match_id, refresh=True)
    return to_match_read(refreshed)


@router.delete("/{match_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_match(match_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    match = await _get_match_or_404(db, match_id)
    await crud.delete_match(db, match)
