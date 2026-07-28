import { api } from "../lib/api";
import type { HomeResponse } from "../types";
import { useAsync } from "./useAsync";

export function useHome() {
  return useAsync<HomeResponse>(() => api.home.get(), []);
}
