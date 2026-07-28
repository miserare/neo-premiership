import { api } from "../lib/api";
import type { PlayerDetail } from "../types";
import { useAsync } from "./useAsync";

export function usePlayerDetail(playerId: string) {
  return useAsync<PlayerDetail>(() => api.players.get(playerId), [playerId]);
}
