import { api } from "../lib/api";
import type { SeasonDetail } from "../types";
import { useAsync } from "./useAsync";

export function useSeasonDetail(seasonId: string) {
  return useAsync<SeasonDetail>(() => api.seasons.get(seasonId), [seasonId]);
}
