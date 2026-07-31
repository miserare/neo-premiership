import type {
  AnnouncementCreateInput,
  AnnouncementRead,
  AnnouncementUpdateInput,
  HomeResponse,
  MatchCreateInput,
  MatchGameInput,
  MatchRead,
  MatchUpdateInput,
  Player,
  PlayerCreateInput,
  PlayerDetail,
  PlayerUpdateInput,
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

const API_BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const ADMIN_TOKEN_STORAGE_KEY = "neo-premiership.admin-token";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** The admin write endpoints are gated by a single shared secret (X-Admin-Token),
 * not per-user login - persist it locally so the admin UI doesn't ask every visit. */
const tokenListeners = new Set<() => void>();

/** Why the stored token was dropped, so the sign-in prompt can explain itself
 * instead of the admin silently bouncing back to it mid-edit. */
let authFailureMessage: string | null = null;

export function getAuthFailureMessage(): string | null {
  return authFailureMessage;
}

export function getAdminToken(): string {
  return window.localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? "";
}

export function setAdminToken(token: string): void {
  if (token) {
    window.localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
    authFailureMessage = null;
  } else {
    window.localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
  }
  for (const listener of tokenListeners) {
    listener();
  }
}

/** Lets the admin UI re-render when the token is cleared from anywhere -
 * including request() dropping it after a 401. */
export function subscribeAdminToken(listener: () => void): () => void {
  tokenListeners.add(listener);
  return () => {
    tokenListeners.delete(listener);
  };
}

interface RequestOptions extends RequestInit {
  /** Send this token instead of the stored one. Used to check a candidate token
   * at sign-in, so a failed check never discards an already-working token. */
  adminToken?: string;
}

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const { adminToken: explicitToken, ...requestInit } = init ?? {};
  const token = explicitToken ?? getAdminToken();
  const response = await fetch(`${API_BASE_URL}/api${path}`, {
    ...requestInit,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Admin-Token": token } : {}),
      ...requestInit.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = typeof body?.detail === "string" ? body.detail : response.statusText;
    // A stored token the server rejects is worse than no token: the UI would
    // look signed in while every save fails. Drop it so the prompt comes back.
    if (response.status === 401 && explicitToken === undefined) {
      authFailureMessage = "Your admin token was rejected. Please sign in again.";
      setAdminToken("");
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
    get: (id: string): Promise<PlayerDetail> => request<PlayerDetail>(`/players/${id}`),
    create: (input: PlayerCreateInput): Promise<Player> =>
      request<Player>("/players", { method: "POST", body: JSON.stringify(input) }),
    update: (id: string, input: PlayerUpdateInput): Promise<Player> =>
      request<Player>(`/players/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
    delete: (id: string): Promise<void> => request<void>(`/players/${id}`, { method: "DELETE" }),
  },
  seasons: {
    list: (params: ListParams = {}): Promise<SeasonSummary[]> =>
      request<SeasonSummary[]>(`/seasons${buildQuery(params)}`),
    get: (id: string): Promise<SeasonDetail> => request<SeasonDetail>(`/seasons/${id}`),
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
    /** Resolves if `token` is accepted; throws ApiError (401 wrong token,
     * 503 server has no ADMIN_TOKEN configured) otherwise. */
    verify: (token: string): Promise<{ ok: boolean }> =>
      request<{ ok: boolean }>("/admin/session", { adminToken: token }),
  },
};
