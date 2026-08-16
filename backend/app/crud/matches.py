import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.match import Match, MatchStage, MatchStatus
from app.models.match_game import MatchGame
from app.models.playoff_round import PlayoffRound
from app.models.pokemon import MatchPokemon
from app.schemas.match import MatchCreate, MatchResultSet, MatchUpdate
from app.services.elo import recalculate_elo_ratings
from app.utils.serialization import stringify_urls

_URL_FIELDS = ("replay_url", "youtube_url")

# A match's round position, for ordering, without joining PlayoffRound into the
# statement itself (which would collide with the joinedload's own alias).
_ROUND_DISPLAY_ORDER = (
    select(PlayoffRound.display_order).where(PlayoffRound.id == Match.playoff_round_id).scalar_subquery()
)


def _with_participants(stmt: Select) -> Select:
    # games/pokemon are selectinload rather than joinedload: they're collections,
    # and joining two of them onto the same row would multiply it out.
    #
    # playoff_round is joined here rather than only in the season-detail path so
    # that every caller - match detail, player detail, the home page stream, the
    # admin list - can read the round without tripping lazy="raise".
    return stmt.options(
        joinedload(Match.home_player),
        joinedload(Match.away_player),
        joinedload(Match.season),
        joinedload(Match.playoff_round),
        selectinload(Match.games),
        selectinload(Match.pokemon),
    )


async def _sync_legacy_round_columns(db: AsyncSession, match: Match) -> None:
    """Mirror the round's name and position onto the match's legacy columns.

    Nothing in this release reads them. They are written so that rolling back
    to the previous release - which sorted the bracket from these columns -
    still renders the right order for matches created or moved in between.
    """
    if match.playoff_round_id is None:
        match.round_order = None
        if match.stage == MatchStage.PLAYOFFS:
            # Unassigned from its round: the copy of that round's name has to go
            # with it, or a rollback would file the match under a round it no
            # longer belongs to. A GROUP match keeps its round_label - that is
            # its own group/matchday label, not a copy of a round's.
            match.round_label = None
        return
    result = await db.execute(
        select(PlayoffRound.label, PlayoffRound.display_order).where(PlayoffRound.id == match.playoff_round_id)
    )
    row = result.first()
    if row is not None:
        match.round_label, match.round_order = row


async def get_matches_for_player(db: AsyncSession, player_id: uuid.UUID) -> list[Match]:
    stmt = _with_participants(select(Match)).where(
        or_(Match.home_player_id == player_id, Match.away_player_id == player_id)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_matches_for_season(db: AsyncSession, season_id: uuid.UUID, stage: MatchStage | None = None) -> list[Match]:
    stmt = _with_participants(select(Match)).where(Match.season_id == season_id)
    if stage is not None:
        stmt = stmt.where(Match.stage == stage)
    # Rounds order by their own display_order; matches inside a round by
    # bracket position, then by id so the result is always deterministic.
    # Dates only break ties between matches that have no bracket position -
    # they never decide which round comes first.
    stmt = stmt.order_by(
        Match.stage,
        _ROUND_DISPLAY_ORDER.nullsfirst(),
        Match.bracket_order.nullsfirst(),
        Match.scheduled_at.nullslast(),
        Match.id,
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_matches_for_seasons(
    db: AsyncSession, season_ids: Sequence[uuid.UUID], stage: MatchStage | None = None
) -> list[Match]:
    """Matches across several seasons in one query, for pages that render more
    than one season at a time (the Hall of Fame). Callers do their own ordering,
    so this only guarantees determinism, not presentation order."""
    if not season_ids:
        return []
    stmt = _with_participants(select(Match)).where(Match.season_id.in_(season_ids))
    if stage is not None:
        stmt = stmt.where(Match.stage == stage)
    result = await db.execute(stmt.order_by(Match.season_id, Match.id))
    return list(result.unique().scalars().all())


async def get_matches_scheduled_between(
    db: AsyncSession, season_id: uuid.UUID, start: datetime, end: datetime
) -> list[Match]:
    """A season's matches scheduled inside a half-open [start, end) window.

    Cancelled matches are excluded: a cancelled fixture is not something to put
    in front of visitors as this week's schedule. An administrator who wants one
    shown anyway can feature it explicitly.
    """
    stmt = (
        _with_participants(select(Match))
        .where(
            Match.season_id == season_id,
            Match.status != MatchStatus.CANCELLED,
            Match.scheduled_at.is_not(None),
            Match.scheduled_at >= start,
            Match.scheduled_at < end,
        )
        .order_by(Match.scheduled_at, Match.id)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_featured_matches(db: AsyncSession) -> list[Match]:
    """Matches an administrator has pinned to the homepage.

    Deliberately unfiltered by season, date or status - featuring a match is an
    explicit statement that it should appear whatever its dates say. Ordering is
    the administrator's own `homepage_feature_order`; matches without one sort
    after those that have one, then by schedule and id so the list never
    reshuffles between requests.
    """
    stmt = (
        _with_participants(select(Match))
        .where(Match.featured_on_homepage.is_(True))
        .order_by(
            Match.homepage_feature_order.nullslast(),
            Match.scheduled_at.nullslast(),
            Match.id,
        )
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_most_recent_stream_match(db: AsyncSession) -> Match | None:
    stmt = (
        _with_participants(select(Match))
        .where(Match.youtube_url.is_not(None))
        .order_by(Match.completed_at.desc().nullslast(), Match.scheduled_at.desc().nullslast())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.unique().scalars().first()


async def get_match_by_id(db: AsyncSession, match_id: uuid.UUID, refresh: bool = False) -> Match | None:
    stmt = _with_participants(select(Match)).where(Match.id == match_id)
    if refresh:
        # The instance is already in the identity map with its collections
        # loaded, and a plain re-query won't overwrite them - so games/pokemon
        # would come back stale after being replaced.
        stmt = stmt.execution_options(populate_existing=True)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def create_match(db: AsyncSession, match_in: MatchCreate) -> Match:
    data = stringify_urls(match_in.model_dump(), _URL_FIELDS)
    match = Match(**data)
    db.add(match)
    await _sync_legacy_round_columns(db, match)
    await db.flush()
    # Compatibility for older administrative clients that created a completed
    # BO1 directly. It becomes one explicit game event (with an unknown legacy
    # Pokémon score) rather than a parent-level Elo event. New result entry
    # always uses save_match_result and requires the score.
    if match.status == MatchStatus.COMPLETED and match.winner_id is not None:
        db.add(
            MatchGame(
                match_id=match.id,
                game_number=1,
                completed_at=match.completed_at,
                winner_id=match.winner_id,
                replay_url=match.replay_url,
            )
        )
        await db.flush()
    await recalculate_elo_ratings(db)
    await db.commit()
    loaded = await get_match_by_id(db, match.id)
    assert loaded is not None
    return loaded


async def update_match(db: AsyncSession, match: Match, match_in: MatchUpdate) -> Match:
    data = stringify_urls(match_in.model_dump(exclude_unset=True), _URL_FIELDS)
    for field, value in data.items():
        setattr(match, field, value)
    if match.best_of == 1 and len(match.games) == 1:
        if "winner_id" in data:
            match.games[0].winner_id = match.winner_id
        if "completed_at" in data:
            match.games[0].completed_at = match.completed_at
    if "playoff_round_id" in data:
        await _sync_legacy_round_columns(db, match)
    await db.flush()
    await recalculate_elo_ratings(db)
    await db.commit()
    # refresh=True: `match` is already in the identity map with playoff_round
    # loaded, and with expire_on_commit=False a plain re-query will not replace
    # an already-populated relationship - so a match moved to another round
    # would come back still reporting the old one.
    loaded = await get_match_by_id(db, match.id, refresh=True)
    assert loaded is not None
    return loaded


async def save_match_result(
    db: AsyncSession,
    match: Match,
    result_in: MatchResultSet,
    *,
    winner_id: uuid.UUID | None,
) -> Match:
    """Write a match's games, both teams, status and derived result atomically.

    One transaction and one Elo rebuild for the whole thing. The previous
    workflow committed the match, then the games, then each team separately,
    which meant an interrupted save could leave a completed match with the old
    series still attached - and it rebuilt Elo once per request.

    The derived values are passed in because deriving them needs the match's
    participants, which the router has already validated the games against.
    """
    try:
        # Delete-then-insert for both collections: the (match_id, game_number)
        # unique constraint makes in-place renumbering order-dependent, and a
        # series is a handful of rows. The flush between delete and insert stops
        # the two statements racing each other within the transaction.
        await db.execute(delete(MatchGame).where(MatchGame.match_id == match.id))
        await db.execute(delete(MatchPokemon).where(MatchPokemon.match_id == match.id))
        await db.flush()

        for game in result_in.games:
            db.add(
                MatchGame(
                    match_id=match.id,
                    game_number=game.game_number,
                    winner_id=game.winner_id,
                    completed_at=game.completed_at,
                    home_pokemon_score=game.home_pokemon_score,
                    away_pokemon_score=game.away_pokemon_score,
                    replay_url=str(game.replay_url) if game.replay_url is not None else None,
                )
            )
        for player_id, team in (
            (match.home_player_id, result_in.home_team),
            (match.away_player_id, result_in.away_team),
        ):
            for pokemon in team:
                db.add(
                    MatchPokemon(
                        match_id=match.id,
                        player_id=player_id,
                        pokeapi_id=pokemon.pokeapi_id,
                        species_name=pokemon.species_name,
                    )
                )

        match.status = result_in.status
        match.best_of = result_in.best_of
        match.completed_at = result_in.completed_at
        match.winner_id = winner_id
        # Legacy parent columns represented a single game's Pokémon score.
        # Mirror only a best-of-one so rollback remains truthful; never put a
        # multi-game series tally into these ambiguous historical columns.
        only_game = result_in.games[0] if result_in.best_of == 1 and result_in.games else None
        match.home_score = only_game.home_pokemon_score if only_game is not None else None
        match.away_score = only_game.away_pokemon_score if only_game is not None else None
        match.youtube_url = str(result_in.youtube_url) if result_in.youtube_url is not None else None

        await db.flush()
        # Once, with the whole result already in place - so a corrected earlier
        # match rebuilds every later rating from the new state exactly once.
        await recalculate_elo_ratings(db)
        await db.commit()
    except Exception:
        # Nothing partial survives: no games without teams, no completed status
        # without its series, no Elo rebuilt from a half-written match.
        await db.rollback()
        raise

    loaded = await get_match_by_id(db, match.id, refresh=True)
    assert loaded is not None
    return loaded


async def delete_match(db: AsyncSession, match: Match) -> None:
    await db.delete(match)
    await db.flush()
    await recalculate_elo_ratings(db)
    await db.commit()
