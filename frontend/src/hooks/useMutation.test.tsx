import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../lib/api";
import { useMutation, type MutationOutcome } from "./useMutation";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useMutation", () => {
  it("marks only the submitted control as pending", async () => {
    const { result } = renderHook(() => useMutation());
    const gate = deferred<string>();

    act(() => {
      void result.current.run("player-1", () => gate.promise);
    });

    await waitFor(() => expect(result.current.isPending("player-1")).toBe(true));
    // The other rows on the page are untouched.
    expect(result.current.isPending("player-2")).toBe(false);

    await act(async () => {
      gate.resolve("done");
      await gate.promise;
    });

    expect(result.current.isPending("player-1")).toBe(false);
  });

  it("ignores a second submission while one is in flight", async () => {
    const { result } = renderHook(() => useMutation());
    const gate = deferred<string>();
    const action = vi.fn(() => gate.promise);

    act(() => {
      void result.current.run("save", action);
      // A double-clicked Save button: the second call must not send.
      void result.current.run("save", action);
    });

    await act(async () => {
      gate.resolve("done");
      await gate.promise;
    });

    expect(action).toHaveBeenCalledTimes(1);
  });

  it("returns the response so callers can update state without refetching", async () => {
    const { result } = renderHook(() => useMutation());

    let outcome: MutationOutcome<string> | undefined;
    await act(async () => {
      outcome = await result.current.run("save", async () => "updated");
    });

    expect(outcome).toEqual({ ok: true, value: "updated" });
  });

  it("reports success for a mutation that resolves to nothing", async () => {
    const { result } = renderHook(() => useMutation());

    // A delete resolves to undefined, so "no value" cannot be what signals
    // failure - hence the explicit ok flag.
    let outcome: MutationOutcome<void> | undefined;
    await act(async () => {
      outcome = await result.current.run("delete", async () => undefined);
    });

    expect(outcome?.ok).toBe(true);
  });

  it("announces success in a message the caller supplies", async () => {
    const { result } = renderHook(() => useMutation());

    await act(async () => {
      await result.current.run("save", async () => "ok", "Player saved.");
    });

    expect(result.current.success).toBe("Player saved.");
  });

  it("surfaces the server's message on failure and reports not-ok", async () => {
    const { result } = renderHook(() => useMutation());

    let outcome: MutationOutcome<string> | undefined;
    await act(async () => {
      outcome = await result.current.run("save", async () => {
        throw new ApiError(409, "Username already taken");
      });
    });

    expect(outcome?.ok).toBe(false);
    expect(result.current.error).toBe("Username already taken");
    expect(result.current.success).toBeNull();
  });

  it("attributes the error to the control that caused it", async () => {
    const { result } = renderHook(() => useMutation());

    await act(async () => {
      await result.current.run("row-2", async () => {
        throw new ApiError(422, "That slug is not valid");
      });
    });

    expect(result.current.errorFor("row-2")).toBe("That slug is not valid");
    expect(result.current.errorFor("row-1")).toBeNull();
  });

  it("falls back to a readable message for a non-API failure", async () => {
    const { result } = renderHook(() => useMutation());

    await act(async () => {
      await result.current.run("save", async () => {
        throw new TypeError("network down");
      });
    });

    expect(result.current.error).toBe("Something went wrong. Please try again.");
  });

  it("clears the previous result when a new save starts", async () => {
    const { result } = renderHook(() => useMutation());

    await act(async () => {
      await result.current.run("save", async () => "ok", "Saved.");
    });
    expect(result.current.success).toBe("Saved.");

    const gate = deferred<string>();
    act(() => {
      void result.current.run("save", () => gate.promise);
    });
    await waitFor(() => expect(result.current.success).toBeNull());

    await act(async () => {
      gate.resolve("done");
      await gate.promise;
    });
  });
});
