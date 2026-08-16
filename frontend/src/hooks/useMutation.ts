import { useCallback, useRef, useState } from "react";

import { ApiError } from "../lib/api";

/** Identifies which control is saving. A page has many. */
type MutationKey = string;

interface MutationState {
  /** The key currently in flight, or null. */
  pendingKey: MutationKey | null;
  /** Success text for the aria-live region, or null. */
  success: string | null;
  /** Error text, or null. Keyed so it can be shown next to the right form. */
  error: string | null;
  errorKey: MutationKey | null;
}

/** The outcome of a mutation.
 *
 * A discriminated result rather than `T | undefined`, because a delete resolves
 * to `undefined` on success - so "no value" cannot mean "it failed". */
export type MutationOutcome<T> = { ok: true; value: T } | { ok: false };

export interface MutationResult {
  /** Is *this* control saving? Pass the key you gave `run`. */
  isPending: (key: MutationKey) => boolean;
  /** Is anything saving? For guarding a whole-page destructive action. */
  isBusy: boolean;
  success: string | null;
  error: string | null;
  errorFor: (key: MutationKey) => string | null;
  /**
   * Run a mutation under `key`.
   *
   * Callers branch on `ok` to update local state, so no call site needs its own
   * try/catch. A second call while one is in flight is dropped, which is what
   * stops a double-clicked Save sending twice.
   */
  run: <T>(
    key: MutationKey,
    action: () => Promise<T>,
    successMessage?: string,
  ) => Promise<MutationOutcome<T>>;
  reset: () => void;
}

const EMPTY: MutationState = { pendingKey: null, success: null, error: null, errorKey: null };

/**
 * Per-control mutation state for an admin page.
 *
 * Keyed rather than a single `isSaving` flag, because a page shows many forms
 * and rows at once: saving one player must not put every other Save button
 * into a pending state, and an error on one row must not appear under all of
 * them. The key is whatever identifies the control - a row id, or a form name.
 *
 * Nothing here refetches or navigates. Callers update local state from the
 * mutation's own response, which is what keeps scroll position and expanded
 * sections intact across a save.
 */
export function useMutation(): MutationResult {
  const [state, setState] = useState<MutationState>(EMPTY);
  // A ref, not state: the guard has to see the in-flight key synchronously,
  // before React has re-rendered, or two fast clicks both pass the check.
  const inFlight = useRef<MutationKey | null>(null);

  const run = useCallback(
    async <T,>(
      key: MutationKey,
      action: () => Promise<T>,
      successMessage?: string,
    ): Promise<MutationOutcome<T>> => {
      if (inFlight.current !== null) {
        return { ok: false };
      }
      inFlight.current = key;
      setState({ pendingKey: key, success: null, error: null, errorKey: null });
      try {
        const result = await action();
        setState({
          pendingKey: null,
          success: successMessage ?? null,
          error: null,
          errorKey: null,
        });
        return { ok: true, value: result };
      } catch (err) {
        // The entered values are untouched - the caller owns the form state and
        // this hook never clears it - so a failed save can be corrected and
        // retried rather than retyped.
        setState({
          pendingKey: null,
          success: null,
          error: err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
          errorKey: key,
        });
        return { ok: false };
      } finally {
        inFlight.current = null;
      }
    },
    [],
  );

  const isPending = useCallback((key: MutationKey) => state.pendingKey === key, [state.pendingKey]);
  const errorFor = useCallback(
    (key: MutationKey) => (state.errorKey === key ? state.error : null),
    [state.error, state.errorKey],
  );
  const reset = useCallback(() => setState(EMPTY), []);

  return {
    isPending,
    isBusy: state.pendingKey !== null,
    success: state.success,
    error: state.error,
    errorFor,
    run,
    reset,
  };
}
