"""The Hall of Fame: every season that has a recorded champion.

Nothing here is stored twice. Champions come from `seasons.champion_id`, and a
championship run is the champion's own playoff matches read back out of the
existing match rows - there is no Hall of Fame table to keep in step.
"""

import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import matches as match_crud
from app.crud import playoff_rounds as round_crud
from app.crud import seasons as season_crud
from app.models.match import Match, MatchStage
from app.models.season import Season
from app.schemas.player import PlayerSummary
from app.schemas.hall_of_fame import HallOfFameEntry, HallOfFameResponse
from app.services.matches import to_match_read


def championship_run(
    champion_id: uuid.UUID, playoff_matches: list[Match], round_order: dict[uuid.UUID, int]
) -> list[Match]:
    """The champion's playoff matches that season, in tournament order.

    "Their run" is defined structurally: playoff-stage matches in this season
    that the champion actually played in. It is never inferred from player
    names, round labels, or dates.

    Ordering is by the round's explicit `display_order`, then by the match's
    bracket position - the same two explicit fields the public bracket sorts
    on. A match not yet assigned to a round sorts last rather than first, so an
    unplaced match cannot masquerade as the opening fixture; match id breaks
    remaining ties so the order is stable across requests.
    """
    mine = [
        match
        for match in playoff_matches
        if champion_id in (match.home_player_id, match.away_player_id)
    ]

    def key(match: Match) -> tuple[int, int, int, int, str]:
        order = round_order.get(match.playoff_round_id) if match.playoff_round_id else None
        return (
            1 if order is None else 0,
            order or 0,
            1 if match.bracket_order is None else 0,
            match.bracket_order or 0,
            str(match.id),
        )

    return sorted(mine, key=key)


def _description(season: Season) -> tuple[str | None, bool]:
    """The Hall of Fame text, falling back to the season overview.

    The flag lets the page say which one it is showing instead of passing a
    season summary off as championship prose.
    """
    written = (season.hall_of_fame_description or "").strip()
    if written:
        return written, False
    overview = (season.overview or "").strip()
    if overview:
        return overview, True
    return None, False


async def build_hall_of_fame(db: AsyncSession) -> HallOfFameResponse:
    """Every championship season, newest first.

    Four queries in total regardless of how many seasons there are: the
    champion seasons, all their playoff matches, and all their playoff rounds.
    """
    seasons = await season_crud.get_champion_seasons(db)
    if not seasons:
        return HallOfFameResponse(entries=[])

    season_ids = [season.id for season in seasons]
    playoff_matches = await match_crud.get_matches_for_seasons(
        db, season_ids, stage=MatchStage.PLAYOFFS
    )
    rounds = await round_crud.get_rounds_for_seasons(db, season_ids)
    round_order = {playoff_round.id: playoff_round.display_order for playoff_round in rounds}

    matches_by_season: dict[uuid.UUID, list[Match]] = defaultdict(list)
    for match in playoff_matches:
        matches_by_season[match.season_id].append(match)

    # Counted across the whole Hall of Fame, so a two-time champion reads as
    # "2× Champion" on both of their entries.
    titles_per_player: dict[uuid.UUID, int] = defaultdict(int)
    for season in seasons:
        assert season.champion_id is not None
        titles_per_player[season.champion_id] += 1

    entries = []
    for season in seasons:
        assert season.champion is not None and season.champion_id is not None
        description, is_fallback = _description(season)
        entries.append(
            HallOfFameEntry(
                season_id=season.id,
                season_slug=season.slug,
                season_name=season.name,
                start_date=season.start_date,
                end_date=season.end_date,
                champion=PlayerSummary.model_validate(season.champion),
                championship_count=titles_per_player[season.champion_id],
                description=description,
                description_is_fallback=is_fallback,
                championship_run=[
                    to_match_read(match)
                    for match in championship_run(
                        season.champion_id, matches_by_season.get(season.id, []), round_order
                    )
                ],
            )
        )
    return HallOfFameResponse(entries=entries)
