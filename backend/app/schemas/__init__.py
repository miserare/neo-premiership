from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementRead,
    AnnouncementUpdate,
)
from app.schemas.home import HomeLink, HomeResponse, HomeSeasonInfo
from app.schemas.match import (
    MatchCreate,
    MatchGameInput,
    MatchGameRead,
    MatchGamesSet,
    MatchRead,
    MatchSeries,
    MatchUpdate,
)
from app.schemas.player import (
    PlayerCreate,
    PlayerDetail,
    PlayerAdmin,
    PlayerPublic,
    PlayerRecord,
    PlayerSeasonRecord,
    PlayerSummary,
    PlayerUpdate,
)
from app.schemas.playoff_round import (
    PlayoffRoundCreate,
    PlayoffRoundRead,
    PlayoffRoundReorder,
    PlayoffRoundUpdate,
)
from app.schemas.pokemon import (
    MatchPokemonSet,
    MatchPokemonRead,
    PokemonInput,
    PokemonSet,
    RosterChangeType,
    RosterPokemonSet,
    SeasonRosterPokemonRead,
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
from app.schemas.site_links import SiteLinksRead, SiteLinksUpdate

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
    "HomeLink",
    "MatchCreate",
    "MatchGameInput",
    "MatchGameRead",
    "MatchGamesSet",
    "MatchPokemonRead",
    "MatchPokemonSet",
    "MatchRead",
    "MatchSeries",
    "MatchUpdate",
    "PokemonInput",
    "PokemonSet",
    "RosterChangeType",
    "RosterPokemonSet",
    "SeasonRosterPokemonRead",
    "SiteLinksRead",
    "SiteLinksUpdate",
    "PlayerCreate",
    "PlayerDetail",
    "PlayerAdmin",
    "PlayerPublic",
    "PlayerRecord",
    "PlayerSeasonRecord",
    "PlayerSummary",
    "PlayerUpdate",
    "PlayoffRoundCreate",
    "PlayoffRoundRead",
    "PlayoffRoundReorder",
    "PlayoffRoundUpdate",
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
