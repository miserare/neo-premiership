import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../lib/api";

interface UseAsyncResult<T> {
  data: T | null;
  /** True only while there is nothing to show yet. */
  isLoading: boolean;
  /** True while a refetch is in flight over data that is already on screen. */
  isRefreshing: boolean;
  error: string | null;
  refetch: () => void;
  /** Replace the local copy from a mutation response, with no extra request. */
  setData: (next: T | ((current: T | null) => T | null) | null) => void;
}

/**
 * Loading/error/data wrapper around a fetcher, re-run whenever `deps` change.
 *
 * The two loading states are deliberately separate. `isLoading` means "there is
 * nothing to render yet"; a refetch after a save sets `isRefreshing` instead
 * and leaves `data` in place. The previous version set one flag on every run,
 * so saving in the admin area replaced the whole page with "Loading..." and
 * read as a reload - losing scroll position and every expanded section with it.
 *
 * `setData` is the other half: most mutations return the updated resource, so
 * the caller can write it straight into local state and skip the round trip
 * altogether.
 */
export function useAsync<T>(fetcher: () => Promise<T>, deps: unknown[]): UseAsyncResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refetchIndex, setRefetchIndex] = useState(0);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  // Read inside the effect rather than listed as a dependency: whether this run
  // is the first one decides which flag it sets, but it must not itself cause
  // another run.
  const hasDataRef = useRef(false);
  hasDataRef.current = data !== null;

  useEffect(() => {
    let isCancelled = false;
    const isRefresh = hasDataRef.current;

    async function run() {
      if (isRefresh) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }
      setError(null);
      try {
        const result = await fetcherRef.current();
        if (!isCancelled) {
          setData(result);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err instanceof ApiError ? err.message : "Failed to load data.");
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
          setIsRefreshing(false);
        }
      }
    }

    run();

    return () => {
      isCancelled = true;
    };
    // deps is spread intentionally - callers pass their own dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, refetchIndex]);

  const refetch = useCallback(() => setRefetchIndex((index) => index + 1), []);

  return { data, isLoading, isRefreshing, error, refetch, setData };
}
