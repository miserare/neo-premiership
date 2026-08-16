// Mirrors backend/app/routers/admin.py::SessionInfo
// Note: no password, hash, or session token ever crosses this boundary - the
// session itself lives in an HttpOnly cookie the browser will not expose.
export interface AdminSessionInfo {
  username: string;
  expires_at: string;
  csrf_token: string;
}

// Mirrors backend/app/schemas/player.py::PlayerPublic
// No discord_id: anonymous responses never carry contact details.
export interface Player {
  id: string;
  /** Canonical URL identity: /player/psykick. Stored, not derived from the
   * username, so renaming a player never breaks their links. */
  slug: string;
  username: string;
  join_date: string;
  is_active: boolean;
  elo_rating: number;
}

// Mirrors backend/app/schemas/player.py::PlayerAdmin
// Only returned from routes guarded by an administrator session.
export interface PlayerAdmin extends Player {
  biography: string | null;
  discord_id: string | null;
  initial_elo_rating: number;
  is_site_creator: boolean;
}

// Mirrors backend/app/schemas/player.py::PlayerCreate
export interface PlayerCreateInput {
  username: string;
  /** Derived from the username when omitted. */
  slug?: string | null;
  biography?: string | null;
  discord_id?: string | null;
  is_active?: boolean;
  initial_elo_rating?: number | null;
  is_site_creator?: boolean;
}

// Mirrors backend/app/schemas/player.py::PlayerUpdate
export interface PlayerUpdateInput {
  username?: string;
  /** Only ever sent when an administrator changes it deliberately. */
  slug?: string;
  biography?: string | null;
  discord_id?: string | null;
  is_active?: boolean;
  initial_elo_rating?: number | null;
  is_site_creator?: boolean;
}

// Mirrors backend/app/schemas/player.py::PlayerSummary
export interface PlayerSummary {
  id: string;
  slug: string;
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
  season_slug: string;
  season_name: string;
  wins: number;
  losses: number;
  pokemon: SeasonRosterPokemon[];
  former_pokemon: SeasonRosterPokemon[];
}

// Mirrors backend/app/schemas/player.py::EloRatingHistoryEntry
export interface EloRatingHistoryEntry {
  match_id: string;
  match_game_id: string;
  game_number: number;
  opponent_id: string;
  opponent_slug: string;
  opponent_username: string;
  occurred_at: string;
  result: 0 | 1;
  expected_score: number;
  rating_before: number;
  rating_after: number;
  rating_change: number;
  player_pokemon_score: number | null;
  opponent_pokemon_score: number | null;
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
  completed_at: string | null;
  winner_id: string | null;
  home_pokemon_score: number | null;
  away_pokemon_score: number | null;
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
  home_series_wins: number;
  away_series_wins: number;
  game_count: number;
  wins_required: number;
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
  playoff_round_id: string | null;
  bracket_order: number | null;
  /** Derived from the referenced round for playoff matches; the group/matchday
   * label for group matches. Never a stale per-match copy. */
  round_label: string | null;
  round_order: number | null;
  scheduled_at: string | null;
  completed_at: string | null;
  best_of: 1 | 3 | 5 | 7 | 9;
  replay_url: string | null;
  youtube_url: string | null;
  /** Administrator highlighting. Explicit data, never inferred from dates. */
  featured_on_homepage: boolean;
  homepage_feature_order: number | null;
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
  best_of: 1 | 3 | 5 | 7 | 9;
  /** Playoff matches only; a group match must leave this unset. */
  playoff_round_id?: string | null;
  bracket_order?: number | null;
  /** Group matches only - a playoff match takes its label from its round. */
  round_label?: string | null;
  scheduled_at?: string | null;
  completed_at?: string | null;
  winner_id?: string | null;
  youtube_url?: string | null;
  featured_on_homepage?: boolean;
  homepage_feature_order?: number | null;
}

// Mirrors backend/app/schemas/match.py::MatchUpdate
// Season, participants, and stage are immutable after creation.
export interface MatchUpdateInput {
  status?: MatchStatus;
  best_of?: 1 | 3 | 5 | 7 | 9;
  playoff_round_id?: string | null;
  bracket_order?: number | null;
  round_label?: string | null;
  scheduled_at?: string | null;
  completed_at?: string | null;
  winner_id?: string | null;
  youtube_url?: string | null;
  featured_on_homepage?: boolean;
  homepage_feature_order?: number | null;
}

// Mirrors backend/app/schemas/player.py::ChampionshipRead
// Derived from seasons.champion_id on every read; there is no is_champion flag.
export interface ChampionshipRead {
  season_id: string;
  season_slug: string;
  season_name: string;
  start_date: string;
  end_date: string | null;
}

// Mirrors backend/app/schemas/match.py::MatchResultGameInput
export interface MatchResultGameInput {
  game_number: number;
  completed_at: string;
  winner_id?: string | null;
  home_pokemon_score: number;
  away_pokemon_score: number;
  replay_url?: string | null;
}

// Mirrors backend/app/schemas/match.py::MatchResultSet
// The series score and match winner are derived server-side from the game
// winners, so neither appears here.
export interface MatchResultInput {
  status: "completed" | "scheduled";
  best_of: 1 | 3 | 5 | 7 | 9;
  completed_at?: string | null;
  games: MatchResultGameInput[];
  home_team: PokemonInput[];
  away_team: PokemonInput[];
  youtube_url?: string | null;
}

// Mirrors backend/app/schemas/player.py::PlayerDetail
export interface PlayerDetail {
  id: string;
  slug: string;
  username: string;
  biography: string | null;
  join_date: string;
  is_active: boolean;
  elo_rating: number;
  is_site_creator: boolean;
  /** Empty for the placeholder player even when a deleted champion's titles
   * were transferred to it. */
  championships: ChampionshipRead[];
  elo_history: EloRatingHistoryEntry[];
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
  slug: string;
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
  /** Derived from the name when omitted ("Season 6" -> "6"). */
  slug?: string | null;
  start_date: string;
  end_date?: string | null;
  champion_id?: string | null;
  overview?: string | null;
  hall_of_fame_description?: string | null;
  sheet_url?: string | null;
}

// Mirrors backend/app/schemas/season.py::SeasonUpdate
export interface SeasonUpdateInput {
  name?: string;
  slug?: string;
  start_date?: string;
  end_date?: string | null;
  champion_id?: string | null;
  overview?: string | null;
  hall_of_fame_description?: string | null;
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
  pokemon_differential: number | null;
  pokemon_differential_complete: boolean;
  tiebreaker_value: number | null;
}

// Mirrors backend/app/schemas/season.py::StandingsGroup
export interface StandingsGroup {
  group_label: string | null;
  standings: StandingsEntry[];
}

// Mirrors backend/app/schemas/season.py::BracketRound
// The array order IS the column order. Never re-sort a bracket in the client -
// `display_order` is the server's answer, and labels carry no ordering at all.
export interface BracketRound {
  id: string;
  label: string;
  display_order: number;
  /** @deprecated Mirror of `label`, kept for older callers. */
  round_label: string;
  /** @deprecated Mirror of `display_order`, kept for older callers. */
  round_order: number;
  matches: MatchRead[];
}

// Mirrors backend/app/schemas/playoff_round.py::PlayoffRoundRead
export interface PlayoffRound {
  id: string;
  season_id: string;
  label: string;
  display_order: number;
  match_count: number;
}

// Mirrors backend/app/schemas/playoff_round.py::PlayoffRoundCreate
export interface PlayoffRoundCreateInput {
  label: string;
  display_order?: number | null;
}

// Mirrors backend/app/schemas/season.py::SeasonStream
export interface SeasonStream {
  url: string;
  label: string;
}

// Mirrors backend/app/schemas/season.py::SeasonDetail
export interface SeasonDetail {
  id: string;
  slug: string;
  name: string;
  start_date: string;
  end_date: string | null;
  /** False between seasons, when this is the most recently started season
   * rather than one in progress. */
  is_active: boolean;
  sheet_url: string | null;
  overview: string | null;
  hall_of_fame_description: string | null;
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
  slug: string;
  name: string;
  is_active: boolean;
  sheet_url: string | null;
  roster: PlayerSummary[];
}

// Mirrors backend/app/schemas/home.py::HomeResponse
// Mirrors backend/app/schemas/home.py::HomeFixtures
// `featured` and `this_week` are separate because they are different claims:
// one is a fact about the calendar, the other an editorial decision. A featured
// match in the current week appears only in `featured`, never in both.
export interface HomeFixtures {
  week_start: string;
  week_end: string;
  timezone: string;
  featured: MatchRead[];
  this_week: MatchRead[];
}

// Mirrors backend/app/schemas/home.py::HomeResponse
export interface HomeResponse {
  announcements: AnnouncementRead[];
  latest_stream: HomeLink | null;
  document: HomeLink | null;
  table: HomeLink | null;
  current_season: HomeSeasonInfo | null;
  fixtures: HomeFixtures;
}

// Mirrors backend/app/schemas/hall_of_fame.py::HallOfFameEntry
export interface HallOfFameEntry {
  season_id: string;
  season_slug: string;
  season_name: string;
  start_date: string;
  end_date: string | null;
  champion: PlayerSummary;
  championship_count: number;
  description: string | null;
  /** True when `description` fell back to the season overview because no Hall
   * of Fame text has been written. */
  description_is_fallback: boolean;
  /** Already in tournament order - by round display_order then bracket
   * position. Never re-sort it in the client. */
  championship_run: MatchRead[];
}

// Mirrors backend/app/schemas/hall_of_fame.py::HallOfFameResponse
export interface HallOfFameResponse {
  entries: HallOfFameEntry[];
}
