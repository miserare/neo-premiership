import type {
  HallOfFameEntry,
  HomeResponse,
  MatchRead,
  PlayerDetail,
  PlayerSummary,
  SeasonDetail,
} from "../types";

/** Fixture builders.
 *
 * Every one takes overrides, so a test states only the fields it is actually
 * about and the rest stay plausible. They mirror the API's shapes, which is
 * what keeps a component test honest about what the server really sends.
 */

let counter = 0;
const nextId = () => `00000000-0000-4000-8000-${String(++counter).padStart(12, "0")}`;

export function playerSummary(overrides: Partial<PlayerSummary> = {}): PlayerSummary {
  return {
    id: nextId(),
    slug: "psykick",
    username: "Psykick",
    elo_rating: 1000,
    is_active: true,
    ...overrides,
  };
}

export function match(overrides: Partial<MatchRead> = {}): MatchRead {
  const home = overrides.home_player ?? playerSummary({ slug: "home", username: "Home" });
  const away = overrides.away_player ?? playerSummary({ slug: "away", username: "Away" });
  return {
    id: nextId(),
    season_id: nextId(),
    home_player: home,
    away_player: away,
    winner_id: null,
    status: "scheduled",
    stage: "group",
    playoff_round_id: null,
    bracket_order: null,
    round_label: null,
    round_order: null,
    scheduled_at: "2026-08-12T23:00:00Z",
    completed_at: null,
    best_of: 1,
    replay_url: null,
    youtube_url: null,
    featured_on_homepage: false,
    homepage_feature_order: null,
    games: [],
    series: { home_series_wins: 0, away_series_wins: 0, game_count: 0, wins_required: 1 },
    home_team: [],
    away_team: [],
    ...overrides,
  };
}

export function completedMatch(overrides: Partial<MatchRead> = {}): MatchRead {
  const base = match(overrides);
  return {
    ...base,
    status: "completed",
    winner_id: overrides.winner_id ?? base.home_player.id,
    completed_at: overrides.completed_at ?? "2026-08-12T23:30:00Z",
    best_of: overrides.best_of ?? 3,
    series: overrides.series ?? {
      home_series_wins: 2,
      away_series_wins: 1,
      game_count: 3,
      wins_required: 2,
    },
    ...overrides,
  };
}

export function playerDetail(overrides: Partial<PlayerDetail> = {}): PlayerDetail {
  return {
    id: nextId(),
    slug: "psykick",
    username: "Psykick",
    biography: null,
    join_date: "2024-01-01T00:00:00Z",
    is_active: true,
    elo_rating: 1000,
    is_site_creator: false,
    championships: [],
    elo_history: [],
    most_recent_season_record: null,
    historical_record: { wins: 0, losses: 0 },
    season_records: [],
    backlog: [],
    completed_matches: [],
    ...overrides,
  };
}

export function seasonDetail(overrides: Partial<SeasonDetail> = {}): SeasonDetail {
  return {
    id: nextId(),
    slug: "7",
    name: "Season 7",
    start_date: "2026-08-13",
    end_date: null,
    is_active: true,
    sheet_url: null,
    overview: null,
    hall_of_fame_description: null,
    champion: null,
    roster: [],
    standings: [],
    bracket: [],
    streams: [],
    ...overrides,
  };
}

export function hallOfFameEntry(overrides: Partial<HallOfFameEntry> = {}): HallOfFameEntry {
  return {
    season_id: nextId(),
    season_slug: "4",
    season_name: "Season 4",
    start_date: "2025-06-14",
    end_date: "2025-08-02",
    champion: playerSummary({ slug: "renk", username: "Renk" }),
    championship_count: 1,
    description: null,
    description_is_fallback: false,
    championship_run: [],
    ...overrides,
  };
}

export function homeResponse(overrides: Partial<HomeResponse> = {}): HomeResponse {
  return {
    announcements: [],
    latest_stream: null,
    document: null,
    table: null,
    current_season: null,
    fixtures: {
      week_start: "2026-08-10T04:00:00Z",
      week_end: "2026-08-17T04:00:00Z",
      timezone: "America/New_York",
      featured: [],
      this_week: [],
    },
    ...overrides,
  };
}
