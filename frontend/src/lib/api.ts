import type {
  AdminSessionInfo,
  AnnouncementCreateInput,
  AnnouncementRead,
  AnnouncementUpdateInput,
  HallOfFameResponse,
  HomeResponse,
  MatchCreateInput,
  MatchGameInput,
  MatchRead,
  MatchResultInput,
  MatchUpdateInput,
  Player,
  PlayerAdmin,
  PlayerCreateInput,
  PlayerDetail,
  PlayerUpdateInput,
  PlayoffRound,
  PlayoffRoundCreateInput,
  PokemonInput,
  RosterPokemonSetInput,
  SeasonCreateInput,
  SeasonDetail,
  SeasonEntryCreateInput,
  SeasonEntryRead,
  SeasonEntryUpdateInput,
  SeasonSummary,
  SeasonUpdateInput,
  SiteLinks,
  SiteLinksInput,
} from "../types";

// Empty in production: the app calls /api on its own origin, which the reverse
// proxy routes to the backend. No cross-origin request, so no CORS and no
// third-party cookie concerns.
const API_BASE_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

const CSRF_COOKIE_NAME = "pp_csrf";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Authentication is an HttpOnly session cookie the browser holds and JavaScript
 * cannot read. Nothing reusable is kept in localStorage or sessionStorage - an
 * XSS bug therefore cannot exfiltrate a durable credential.
 *
 * The only value we read is the CSRF token, which is intentionally readable and
 * useless without the session cookie that accompanies it. */
function readCsrfToken(): string {
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE_NAME}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

const authListeners = new Set<() => void>();

let authFailureMessage: string | null = null;

export function getAuthFailureMessage(): string | null {
  return authFailureMessage;
}

export function clearAuthFailureMessage(): void {
  authFailureMessage = null;
}

/** Lets the admin UI re-render when the server rejects our session. */
export function subscribeAuth(listener: () => void): () => void {
  authListeners.add(listener);
  return () => {
    authListeners.delete(listener);
  };
}

function notifyAuthChanged(): void {
  for (const listener of authListeners) {
    listener();
  }
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

interface RequestOptions extends RequestInit {
  /** Don't treat a 401 as "your session died". Used by the probe that asks
   * whether we are signed in at all: a first-time visitor has no session, and
   * telling them it expired is simply wrong. */
  quiet401?: boolean;
}

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const { quiet401 = false, ...requestInit } = init ?? {};
  const method = (requestInit.method ?? "GET").toUpperCase();
  const csrf = UNSAFE_METHODS.has(method) ? readCsrfToken() : "";

  const response = await fetch(`${API_BASE_URL}/api${path}`, {
    ...requestInit,
    // Send the session cookie. Required even same-origin once the request is
    // issued by fetch with explicit options.
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      ...requestInit.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = typeof body?.detail === "string" ? body.detail : response.statusText;
    // A rejected session is worse than none: the UI would look signed in while
    // every save failed. Surface it so the admin area re-prompts.
    if (response.status === 401 && !quiet401) {
      authFailureMessage = "Your session has expired. Please sign in again.";
      notifyAuthChanged();
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export interface ListParams {
  q?: string;
  skip?: number;
  limit?: number;
}

function buildQuery(params: ListParams): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export const api = {
  players: {
    list: (params: ListParams = {}): Promise<Player[]> =>
      request<Player[]>(`/players${buildQuery(params)}`),
    /** Accepts a canonical slug or a legacy UUID - the API resolves both, which
     * is what lets the app redirect an old link to its canonical form. */
    get: (ref: string): Promise<PlayerDetail> =>
      request<PlayerDetail>(`/players/${encodeURIComponent(ref)}`),
    /** Administrative roster including private fields. Requires a session. */
    listAdmin: (params: ListParams = {}): Promise<PlayerAdmin[]> =>
      request<PlayerAdmin[]>(`/players/admin/list${buildQuery(params)}`),
    create: (input: PlayerCreateInput): Promise<PlayerAdmin> =>
      request<PlayerAdmin>("/players", { method: "POST", body: JSON.stringify(input) }),
    update: (id: string, input: PlayerUpdateInput): Promise<PlayerAdmin> =>
      request<PlayerAdmin>(`/players/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
    delete: (id: string): Promise<void> => request<void>(`/players/${id}`, { method: "DELETE" }),
  },
  seasons: {
    list: (params: ListParams = {}): Promise<SeasonSummary[]> =>
      request<SeasonSummary[]>(`/seasons${buildQuery(params)}`),
    /** Accepts a canonical slug or a legacy UUID. */
    get: (ref: string): Promise<SeasonDetail> =>
      request<SeasonDetail>(`/seasons/${encodeURIComponent(ref)}`),
    /** The active season, or the most recently started one between seasons.
     * The response's `is_active` says which. */
    current: (): Promise<SeasonDetail> => request<SeasonDetail>("/seasons/current"),
    create: (input: SeasonCreateInput): Promise<SeasonSummary> =>
      request<SeasonSummary>("/seasons", { method: "POST", body: JSON.stringify(input) }),
    update: (id: string, input: SeasonUpdateInput): Promise<SeasonSummary> =>
      request<SeasonSummary>(`/seasons/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
    delete: (id: string): Promise<void> => request<void>(`/seasons/${id}`, { method: "DELETE" }),
    roster: {
      list: (seasonId: string): Promise<SeasonEntryRead[]> =>
        request<SeasonEntryRead[]>(`/seasons/${seasonId}/roster`),
      add: (seasonId: string, input: SeasonEntryCreateInput): Promise<SeasonEntryRead> =>
        request<SeasonEntryRead>(`/seasons/${seasonId}/roster`, {
          method: "POST",
          body: JSON.stringify(input),
        }),
      update: (seasonId: string, entryId: string, input: SeasonEntryUpdateInput): Promise<SeasonEntryRead> =>
        request<SeasonEntryRead>(`/seasons/${seasonId}/roster/${entryId}`, {
          method: "PATCH",
          body: JSON.stringify(input),
        }),
      remove: (seasonId: string, entryId: string): Promise<void> =>
        request<void>(`/seasons/${seasonId}/roster/${entryId}`, { method: "DELETE" }),
      setPokemon: (
        seasonId: string,
        entryId: string,
        input: RosterPokemonSetInput,
      ): Promise<SeasonEntryRead> =>
        request<SeasonEntryRead>(`/seasons/${seasonId}/roster/${entryId}/pokemon`, {
          method: "PUT",
          body: JSON.stringify(input),
        }),
    },
    playoffRounds: {
      list: (seasonId: string): Promise<PlayoffRound[]> =>
        request<PlayoffRound[]>(`/seasons/${seasonId}/playoff-rounds`),
      create: (seasonId: string, input: PlayoffRoundCreateInput): Promise<PlayoffRound> =>
        request<PlayoffRound>(`/seasons/${seasonId}/playoff-rounds`, {
          method: "POST",
          body: JSON.stringify(input),
        }),
      rename: (seasonId: string, roundId: string, label: string): Promise<PlayoffRound> =>
        request<PlayoffRound>(`/seasons/${seasonId}/playoff-rounds/${roundId}`, {
          method: "PATCH",
          body: JSON.stringify({ label }),
        }),
      /** Whole-list reorder: the server rewrites contiguous positions in one
       * transaction, so there is no half-applied ordering to recover from. */
      reorder: (seasonId: string, roundIds: string[]): Promise<PlayoffRound[]> =>
        request<PlayoffRound[]>(`/seasons/${seasonId}/playoff-rounds/reorder`, {
          method: "PUT",
          body: JSON.stringify({ round_ids: roundIds }),
        }),
      remove: (seasonId: string, roundId: string): Promise<void> =>
        request<void>(`/seasons/${seasonId}/playoff-rounds/${roundId}`, { method: "DELETE" }),
    },
  },
  matches: {
    listBySeason: (seasonId: string): Promise<MatchRead[]> =>
      request<MatchRead[]>(`/matches?season_id=${encodeURIComponent(seasonId)}`),
    get: (id: string): Promise<MatchRead> => request<MatchRead>(`/matches/${id}`),
    create: (input: MatchCreateInput): Promise<MatchRead> =>
      request<MatchRead>("/matches", { method: "POST", body: JSON.stringify(input) }),
    update: (id: string, input: MatchUpdateInput): Promise<MatchRead> =>
      request<MatchRead>(`/matches/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
    delete: (id: string): Promise<void> => request<void>(`/matches/${id}`, { method: "DELETE" }),
    setGames: (id: string, games: MatchGameInput[]): Promise<MatchRead> =>
      request<MatchRead>(`/matches/${id}/games`, { method: "PUT", body: JSON.stringify({ games }) }),
    setTeam: (id: string, playerId: string, pokemon: PokemonInput[]): Promise<MatchRead> =>
      request<MatchRead>(`/matches/${id}/teams/${playerId}`, {
        method: "PUT",
        body: JSON.stringify({ pokemon }),
      }),
    /** Games, both teams, status and timestamps in one transaction. The series
     * score and match winner come back derived; they are not sent. */
    setResult: (id: string, input: MatchResultInput): Promise<MatchRead> =>
      request<MatchRead>(`/matches/${id}/result`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
  },
  hallOfFame: {
    get: (): Promise<HallOfFameResponse> => request<HallOfFameResponse>("/hall-of-fame"),
  },
  home: {
    get: (): Promise<HomeResponse> => request<HomeResponse>("/home"),
  },
  announcements: {
    list: (): Promise<AnnouncementRead[]> => request<AnnouncementRead[]>("/announcements"),
    create: (input: AnnouncementCreateInput): Promise<AnnouncementRead> =>
      request<AnnouncementRead>("/announcements", { method: "POST", body: JSON.stringify(input) }),
    update: (id: string, input: AnnouncementUpdateInput): Promise<AnnouncementRead> =>
      request<AnnouncementRead>(`/announcements/${id}`, {
        method: "PATCH",
        body: JSON.stringify(input),
      }),
    delete: (id: string): Promise<void> =>
      request<void>(`/announcements/${id}`, { method: "DELETE" }),
  },
  siteLinks: {
    get: (): Promise<SiteLinks> => request<SiteLinks>("/site-links"),
    set: (input: SiteLinksInput): Promise<SiteLinks> =>
      request<SiteLinks>("/site-links", { method: "PUT", body: JSON.stringify(input) }),
  },
  admin: {
    login: (username: string, password: string): Promise<AdminSessionInfo> =>
      request<AdminSessionInfo>("/admin/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),
    session: (): Promise<AdminSessionInfo> =>
      request<AdminSessionInfo>("/admin/session", { quiet401: true }),
    logout: (): Promise<void> => request<void>("/admin/logout", { method: "POST" }),
    logoutEverywhere: (): Promise<void> =>
      request<void>("/admin/logout-everywhere", { method: "POST" }),
    changePassword: (currentPassword: string, newPassword: string): Promise<void> =>
      request<void>("/admin/password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      }),
  },
};
