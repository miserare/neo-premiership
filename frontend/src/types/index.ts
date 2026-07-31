// Mirrors backend/app/schemas/player.py::PlayerRead
export interface Player {
  id: string;
  username: string;
  discord_id: string | null;
  join_date: string;
  is_active: boolean;
  elo_rating: number;
}

// Mirrors backend/app/schemas/player.py::PlayerCreate
export interface PlayerCreateInput {
  username: string;
  discord_id?: string | null;
  is_active?: boolean;
  elo_rating?: number | null;
}

// Mirrors backend/app/schemas/player.py::PlayerUpdate
export interface PlayerUpdateInput {
  username?: string;
  discord_id?: string | null;
  is_active?: boolean;
  elo_rating?: number | null;
}

// Mirrors backend/app/schemas/player.py::PlayerSummary
export interface PlayerSummary {
  id: string;
  username: string;
  elo_rating: number;
  is_active: boolean;
}

// Mirrors backend/app/schemas/player.py::PlayerRecord
export interface PlayerRecord {
  wins: number;
  losses: number;
}

// Mirrors backend/app/schemas/player.py::PlayerSeasonRecord
export interface PlayerSeasonRecord {
  season_id: string;
  season_name: string;
  wins: number;
  losses: number;
  pokemon: SeasonRosterPokemon[];
  former_pokemon: SeasonRosterPokemon[];
}

// Mirrors backend/app/models/match.py::MatchStatus
export type MatchStatus = "scheduled" | "completed" | "cancelled";

// Mirrors backend/app/models/match.py::MatchStage
export type MatchStage = "group" | "playoffs";

// Mirrors backend/app/schemas/pokemon.py::PokemonInput
export interface PokemonInput {
  pokeapi_id: number;
  species_name: string;
}

// Mirrors backend/app/schemas/pokemon.py::SeasonRosterPokemonRead
export interface SeasonRosterPokemon {
  id: string;
  pokeapi_id: number;
  species_name: string;
  slot: number;
  acquired_at: string | null;
  released_at: string | null;
  acquisition_type: RosterChangeType;
  release_type: RosterChangeType | null;
}

export type RosterChangeType = "draft" | "free_agency" | "trade" | "correction";

// Mirrors backend/app/schemas/pokemon.py::MatchPokemonRead
export interface MatchPokemon {
  id: string;
  player_id: string;
  pokeapi_id: number;
  species_name: string;
}

// Mirrors backend/app/schemas/match.py::MatchGameRead
// `id` is null for a game synthesized from a legacy single replay_url.
export interface MatchGameRead {
  id: string | null;
  game_number: number;
  winner_id: string | null;
  replay_url: string | null;
}

// Mirrors backend/app/schemas/match.py::MatchGameInput
export interface MatchGameInput {
  game_number: number;
  winner_id?: string | null;
  replay_url?: string | null;
}

// Mirrors backend/app/schemas/match.py::MatchSeries
export interface MatchSeries {
  home_wins: number;
  away_wins: number;
  game_count: number;
}

// Mirrors backend/app/schemas/match.py::MatchRead
export interface MatchRead {
  id: string;
  season_id: string;
  home_player: PlayerSummary;
  away_player: PlayerSummary;
  winner_id: string | null;
  status: MatchStatus;
  stage: MatchStage;
  round_label: string | null;
  round_order: number | null;
  bracket_order: number | null;
  scheduled_at: string | null;
  completed_at: string | null;
  home_score: number | null;
  away_score: number | null;
  replay_url: string | null;
  youtube_url: string | null;
  games: MatchGameRead[];
  series: MatchSeries;
  home_team: MatchPokemon[];
  away_team: MatchPokemon[];
}

// Mirrors backend/app/schemas/match.py::MatchCreate
export interface MatchCreateInput {
  season_id: string;
  home_player_id: string;
  away_player_id: string;
  stage: MatchStage;
  status?: MatchStatus;
  round_label?: string | null;
  round_order?: number | null;
  bracket_order?: number | null;
  scheduled_at?: string | null;
  completed_at?: string | null;
  winner_id?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  youtube_url?: string | null;
}

// Mirrors backend/app/schemas/match.py::MatchUpdate
// Season, participants, and stage are immutable after creation.
export interface MatchUpdateInput {
  status?: MatchStatus;
  round_label?: string | null;
  round_order?: number | null;
  bracket_order?: number | null;
  scheduled_at?: string | null;
  completed_at?: string | null;
  winner_id?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  youtube_url?: string | null;
}

// Mirrors backend/app/schemas/player.py::PlayerDetail
export interface PlayerDetail {
  id: string;
  username: string;
  discord_id: string | null;
  join_date: string;
  is_active: boolean;
  elo_rating: number;
  most_recent_season_record: PlayerSeasonRecord | null;
  historical_record: PlayerRecord;
  season_records: PlayerSeasonRecord[];
  backlog: MatchRead[];
  completed_matches: MatchRead[];
}

// Mirrors backend/app/schemas/announcement.py::AnnouncementRead
export interface AnnouncementRead {
  id: string;
  title: string;
  body: string;
  published_at: string;
  link_url: string | null;
}

// Mirrors backend/app/schemas/season.py::SeasonSummary
export interface SeasonSummary {
  id: string;
  name: string;
  start_date: string;
  end_date: string | null;
  champion: PlayerSummary | null;
}

// Mirrors backend/app/schemas/season.py::RosterEntry
export interface RosterEntry {
  player: PlayerSummary;
  group_label: string | null;
  pokemon: SeasonRosterPokemon[];
  former_pokemon: SeasonRosterPokemon[];
}

// Mirrors backend/app/schemas/season.py::SeasonCreate
export interface SeasonCreateInput {
  name: string;
  start_date: string;
  end_date?: string | null;
  champion_id?: string | null;
  overview?: string | null;
  sheet_url?: string | null;
}

// Mirrors backend/app/schemas/season.py::SeasonUpdate
export interface SeasonUpdateInput {
  name?: string;
  start_date?: string;
  end_date?: string | null;
  champion_id?: string | null;
  overview?: string | null;
  sheet_url?: string | null;
}

// Mirrors backend/app/schemas/season.py::SeasonEntryRead
export interface SeasonEntryRead {
  id: string;
  player: PlayerSummary;
  group_label: string | null;
  tiebreaker_value: number | null;
  pokemon: SeasonRosterPokemon[];
  former_pokemon: SeasonRosterPokemon[];
}

export interface RosterPokemonSetInput {
  pokemon: PokemonInput[];
  effective_at?: string;
  change_type?: RosterChangeType;
}

// Mirrors backend/app/schemas/season.py::SeasonEntryCreate
export interface SeasonEntryCreateInput {
  player_id: string;
  group_label?: string | null;
  tiebreaker_value?: number | null;
}

// Mirrors backend/app/schemas/season.py::SeasonEntryUpdate
export interface SeasonEntryUpdateInput {
  group_label?: string | null;
  tiebreaker_value?: number | null;
}

// Mirrors backend/app/schemas/season.py::StandingsEntry
export interface StandingsEntry {
  player: PlayerSummary;
  wins: number;
  losses: number;
  tiebreaker_value: number | null;
}

// Mirrors backend/app/schemas/season.py::StandingsGroup
export interface StandingsGroup {
  group_label: string | null;
  standings: StandingsEntry[];
}

// Mirrors backend/app/schemas/season.py::BracketRound
export interface BracketRound {
  round_label: string;
  round_order: number;
  matches: MatchRead[];
}

// Mirrors backend/app/schemas/season.py::SeasonStream
export interface SeasonStream {
  url: string;
  label: string;
}

// Mirrors backend/app/schemas/season.py::SeasonDetail
export interface SeasonDetail {
  id: string;
  name: string;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  sheet_url: string | null;
  overview: string | null;
  champion: PlayerSummary | null;
  roster: RosterEntry[];
  standings: StandingsGroup[];
  bracket: BracketRound[];
  streams: SeasonStream[];
}

// Mirrors backend/app/schemas/home.py::HomeLink
// `external` is false for the in-site standings link, true once an admin pins
// an outbound URL - the component switches between Link and ExternalLink on it.
export interface HomeLink {
  url: string;
  label: string;
  external: boolean;
}

// Mirrors backend/app/schemas/site_links.py::SiteLinksRead
export interface SiteLinks {
  stream_url: string | null;
  stream_label: string | null;
  document_url: string | null;
  document_label: string | null;
  table_url: string | null;
  table_label: string | null;
}

// Mirrors backend/app/schemas/site_links.py::SiteLinksUpdate
export type SiteLinksInput = SiteLinks;

// Mirrors backend/app/schemas/announcement.py::AnnouncementCreate
export interface AnnouncementCreateInput {
  title: string;
  body: string;
  published_at?: string | null;
  link_url?: string | null;
}

// Mirrors backend/app/schemas/announcement.py::AnnouncementUpdate
export interface AnnouncementUpdateInput {
  title?: string;
  body?: string;
  published_at?: string | null;
  link_url?: string | null;
}

// Mirrors backend/app/schemas/home.py::HomeSeasonInfo
export interface HomeSeasonInfo {
  id: string;
  name: string;
  is_active: boolean;
  sheet_url: string | null;
  roster: PlayerSummary[];
}

// Mirrors backend/app/schemas/home.py::HomeResponse
export interface HomeResponse {
  announcements: AnnouncementRead[];
  latest_stream: HomeLink | null;
  document: HomeLink | null;
  table: HomeLink | null;
  current_season: HomeSeasonInfo | null;
}
