import { useCallback, useEffect, useState } from "react";

import { api, ApiError, clearAuthFailureMessage, subscribeAuth } from "../lib/api";
import type { AdminSessionInfo } from "../types";

interface AdminSessionState {
  session: AdminSessionInfo | null;
  isLoading: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

/** Tracks who is signed in.
 *
 * There is no client-side token to inspect - the session cookie is HttpOnly -
 * so the only way to know is to ask the server. That check runs once on mount
 * and again whenever a request reports the session was rejected.
 */
export function useAdminSession(): AdminSessionState {
  const [session, setSession] = useState<AdminSessionInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setSession(await api.admin.session());
    } catch {
      // 401 simply means "not signed in"; it is not an error worth surfacing.
      setSession(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // A 401 from any request means our session died underneath us.
  useEffect(() => subscribeAuth(() => setSession(null)), []);

  const signIn = useCallback(async (username: string, password: string) => {
    const info = await api.admin.login(username, password);
    clearAuthFailureMessage();
    setSession(info);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.admin.logout();
    } catch (err) {
      // An already-dead session still ends in the signed-out state we want.
      if (!(err instanceof ApiError)) throw err;
    }
    setSession(null);
  }, []);

  return { session, isLoading, signIn, signOut };
}
