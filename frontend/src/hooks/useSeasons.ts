import { api } from "../lib/api";
import type { SeasonSummary } from "../types";
import { useAsync } from "./useAsync";

export function useSeasons(q: string) {
  return useAsync<SeasonSummary[]>(() => api.seasons.list({ q: q || undefined }), [q]);
}
