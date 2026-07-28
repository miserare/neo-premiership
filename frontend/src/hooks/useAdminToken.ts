import { useCallback, useSyncExternalStore } from "react";

import { getAdminToken, setAdminToken, subscribeAdminToken } from "../lib/api";

/** Reactive view of the admin token stored in localStorage (see lib/api.ts).
 * Subscribing rather than holding local state matters because request() clears
 * the token on a 401 - the sign-in prompt has to come back on its own. */
export function useAdminToken() {
  const token = useSyncExternalStore(subscribeAdminToken, getAdminToken);

  const saveToken = useCallback((next: string) => setAdminToken(next), []);
  const clearToken = useCallback(() => setAdminToken(""), []);

  return { token, saveToken, clearToken };
}
