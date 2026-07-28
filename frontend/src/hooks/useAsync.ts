import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../lib/api";

interface UseAsyncResult<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

/** Generic loading/error/data wrapper around a fetcher, re-run whenever `deps` change. */
export function useAsync<T>(fetcher: () => Promise<T>, deps: unknown[]): UseAsyncResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchIndex, setRefetchIndex] = useState(0);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let isCancelled = false;

    async function run() {
      setIsLoading(true);
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

  return { data, isLoading, error, refetch };
}
