import { api } from "../lib/api";
import type { Player } from "../types";
import { useAsync } from "./useAsync";

export function usePlayers(q: string) {
  return useAsync<Player[]>(() => api.players.list({ q: q || undefined }), [q]);
}
