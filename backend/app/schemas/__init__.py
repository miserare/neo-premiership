from app.schemas.announcement import AnnouncementCreate, AnnouncementRead, AnnouncementUpdate
from app.schemas.home import HomeResponse, HomeSeasonInfo, HomeStream
from app.schemas.match import (
    MatchCreate,
    MatchGameInput,
    MatchGameRead,
    MatchGamesSet,
    MatchRead,
    MatchSeries,
    MatchUpdate,
)
from app.schemas.pokemon import (
    MatchPokemonRead,
    PokemonInput,
    PokemonSet,
    SeasonRosterPokemonRead,
)
from app.schemas.player import (
    PlayerCreate,
    PlayerDetail,
    PlayerRead,
    PlayerRecord,
    PlayerSeasonRecord,
    PlayerSummary,
    PlayerUpdate,
)
from app.schemas.season import (
    BracketRound,
    RosterEntry,
    SeasonCreate,
    SeasonDetail,
    SeasonEntryCreate,
    SeasonEntryRead,
    SeasonEntryUpdate,
    SeasonStream,
    SeasonSummary,
    SeasonUpdate,
    StandingsEntry,
    StandingsGroup,
)

# PlayerDetail references MatchRead by forward-ref string to avoid a circular
# import between player.py and match.py; player.py only imports MatchRead under
# TYPE_CHECKING, so the runtime rebuild needs the type supplied explicitly.
PlayerDetail.model_rebuild(_types_namespace={"MatchRead": MatchRead})

__all__ = [
    "AnnouncementCreate",
    "AnnouncementRead",
    "AnnouncementUpdate",
    "BracketRound",
    "HomeResponse",
    "HomeSeasonInfo",
    "HomeStream",
    "MatchCreate",
    "MatchGameInput",
    "MatchGameRead",
    "MatchGamesSet",
    "MatchPokemonRead",
    "MatchRead",
    "MatchSeries",
    "MatchUpdate",
    "PokemonInput",
    "PokemonSet",
    "SeasonRosterPokemonRead",
    "PlayerCreate",
    "PlayerDetail",
    "PlayerRead",
    "PlayerRecord",
    "PlayerSeasonRecord",
    "PlayerSummary",
    "PlayerUpdate",
    "RosterEntry",
    "SeasonCreate",
    "SeasonDetail",
    "SeasonEntryCreate",
    "SeasonEntryRead",
    "SeasonEntryUpdate",
    "SeasonStream",
    "SeasonSummary",
    "SeasonUpdate",
    "StandingsEntry",
    "StandingsGroup",
]
