import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../lib/api";
import { useAsync } from "./useAsync";

describe("useAsync", () => {
  it("reports the first load as loading", async () => {
    const { result } = renderHook(() => useAsync(async () => "first", []));

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isRefreshing).toBe(false);

    await waitFor(() => expect(result.current.data).toBe("first"));
    expect(result.current.isLoading).toBe(false);
  });

  it("keeps the existing data visible while refetching", async () => {
    let call = 0;
    const fetcher = vi.fn(async () => {
      call += 1;
      return `value ${call}`;
    });
    const { result } = renderHook(() => useAsync(fetcher, []));
    await waitFor(() => expect(result.current.data).toBe("value 1"));

    act(() => result.current.refetch());

    // This is the whole point: a refetch after a save must not blank the page
    // and re-render it as an initial loading state.
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBe("value 1");

    await waitFor(() => expect(result.current.data).toBe("value 2"));
    expect(result.current.isRefreshing).toBe(false);
  });

  it("flags a refetch as refreshing rather than loading", async () => {
    let resolve!: (value: string) => void;
    const fetcher = vi
      .fn<() => Promise<string>>()
      .mockResolvedValueOnce("first")
      .mockImplementationOnce(() => new Promise<string>((res) => (resolve = res)));

    const { result } = renderHook(() => useAsync(fetcher, []));
    await waitFor(() => expect(result.current.data).toBe("first"));

    act(() => result.current.refetch());
    await waitFor(() => expect(result.current.isRefreshing).toBe(true));
    expect(result.current.isLoading).toBe(false);

    await act(async () => {
      resolve("second");
    });
    await waitFor(() => expect(result.current.isRefreshing).toBe(false));
  });

  it("lets a caller write the mutation response straight into local state", async () => {
    const fetcher = vi.fn(async () => "from server");
    const { result } = renderHook(() => useAsync(fetcher, []));
    await waitFor(() => expect(result.current.data).toBe("from server"));

    act(() => result.current.setData("from the save response"));

    expect(result.current.data).toBe("from the save response");
    // No extra request: the mutation already returned the updated resource.
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("surfaces the API's message on failure", async () => {
    const { result } = renderHook(() =>
      useAsync(async () => {
        throw new ApiError(404, "Player not found");
      }, []),
    );

    await waitFor(() => expect(result.current.error).toBe("Player not found"));
    expect(result.current.isLoading).toBe(false);
  });

  it("re-runs when its dependencies change", async () => {
    const fetcher = vi.fn(async (id: string) => `player ${id}`);
    const { result, rerender } = renderHook(({ id }) => useAsync(() => fetcher(id), [id]), {
      initialProps: { id: "a" },
    });
    await waitFor(() => expect(result.current.data).toBe("player a"));

    rerender({ id: "b" });
    await waitFor(() => expect(result.current.data).toBe("player b"));
  });
});
