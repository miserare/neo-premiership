import { type FormEvent, useEffect, useState } from "react";

import { useAsync } from "../hooks/useAsync";
import { api, ApiError } from "../lib/api";
import type { PlayoffRound, SeasonSummary } from "../types";

/** Manage a season's playoff rounds.
 *
 * The list is always shown in `display_order`, which is the only thing that
 * decides where a round appears on the public bracket. Renaming is separate
 * from moving, so neither can happen by accident, and moving sends the whole
 * ordered list to one transactional endpoint rather than a position at a time.
 */
export default function AdminPlayoffRoundsPage() {
  const { data: seasons } = useAsync<SeasonSummary[]>(() => api.seasons.list({ limit: 500 }), []);
  const [seasonId, setSeasonId] = useState("");

  useEffect(() => {
    if (!seasonId && seasons && seasons.length > 0) {
      setSeasonId(seasons[0].id);
    }
  }, [seasons, seasonId]);

  const {
    data: rounds,
    isLoading,
    error,
    refetch,
  } = useAsync<PlayoffRound[]>(
    () => (seasonId ? api.seasons.playoffRounds.list(seasonId) : Promise.resolve([])),
    [seasonId],
  );

  const [newLabel, setNewLabel] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingLabel, setEditingLabel] = useState("");
  // Announced to screen readers after a move, because the visible change is a
  // row swapping places - easy to miss without sight of the list.
  const [status, setStatus] = useState("");

  const ordered = rounds ?? [];

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    if (!newLabel.trim()) {
      setCreateError("A round needs a name.");
      return;
    }
    try {
      await api.seasons.playoffRounds.create(seasonId, { label: newLabel.trim() });
      setNewLabel("");
      setStatus(`Added ${newLabel.trim()} to the end of the bracket.`);
      refetch();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to create the round.");
    }
  }

  async function handleRename(round: PlayoffRound) {
    setActionError(null);
    const label = editingLabel.trim();
    if (!label) {
      setActionError("A round needs a name.");
      return;
    }
    try {
      await api.seasons.playoffRounds.rename(seasonId, round.id, label);
      setEditingId(null);
      setStatus(`Renamed to ${label}. Its position is unchanged.`);
      refetch();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to rename the round.");
    }
  }

  /** Swap a round with its neighbour and send the complete resulting order. */
  async function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= ordered.length) return;
    const next = [...ordered];
    [next[index], next[target]] = [next[target], next[index]];

    setActionError(null);
    setBusy(true);
    try {
      await api.seasons.playoffRounds.reorder(
        seasonId,
        next.map((round) => round.id),
      );
      setStatus(`${ordered[index].label} is now round ${target + 1} of ${ordered.length}.`);
      refetch();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to reorder the rounds.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(round: PlayoffRound) {
    setActionError(null);
    if (!window.confirm(`Delete the round "${round.label}"?`)) return;
    try {
      await api.seasons.playoffRounds.remove(seasonId, round.id);
      setStatus(`Deleted ${round.label}.`);
      refetch();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to delete the round.");
    }
  }

  return (
    <div className="admin-rounds-page">
      <h1>Playoff Rounds</h1>
      <p className="admin-form__hint">
        These are the columns of the public bracket, shown left to right in the order below. The
        names are yours to choose - they play no part in the ordering.
      </p>

      <div className="admin-form__row admin-matches-page__season-select">
        <label htmlFor="admin-round-season">Season</label>
        <select
          id="admin-round-season"
          value={seasonId}
          onChange={(event) => {
            setSeasonId(event.target.value);
            setEditingId(null);
            setStatus("");
          }}
        >
          {(seasons ?? []).map((season) => (
            <option key={season.id} value={season.id}>
              {season.name}
            </option>
          ))}
        </select>
      </div>

      {seasonId && (
        <section>
          <h2>Add a round</h2>
          <form className="admin-form" onSubmit={handleCreate}>
            <div className="admin-form__row">
              <label htmlFor="new-round-label">Round name</label>
              <input
                id="new-round-label"
                value={newLabel}
                onChange={(event) => setNewLabel(event.target.value)}
                placeholder="e.g. Quarterfinal"
                maxLength={64}
                required
              />
              <p className="admin-form__hint">
                New rounds are added at the end. Use Move earlier to place one differently.
              </p>
            </div>
            {createError && (
              <p role="alert" className="admin-form__error">
                {createError}
              </p>
            )}
            <button type="submit" className="admin-form__submit">
              Add round
            </button>
          </form>
        </section>
      )}

      <section>
        <h2>Order</h2>
        {isLoading && <p role="status">Loading rounds...</p>}
        {error && (
          <p role="alert" className="admin-page__error">
            {error}
          </p>
        )}
        {actionError && (
          <p role="alert" className="admin-page__error">
            {actionError}
          </p>
        )}
        <p role="status" className="admin-rounds-page__status">
          {status}
        </p>

        {!isLoading && !error && ordered.length === 0 && (
          <p>
            This season has no playoff rounds yet. Add one above before creating playoff matches.
          </p>
        )}

        {ordered.length > 0 && (
          <ol className="admin-rounds-list">
            {ordered.map((round, index) => (
              <li key={round.id} className="admin-round-row">
                <span className="admin-round-row__position" aria-hidden="true">
                  {round.display_order}
                </span>

                {editingId === round.id ? (
                  <div className="admin-round-row__main">
                    <label className="admin-round-row__rename-label" htmlFor={`rename-${round.id}`}>
                      New name for round {round.display_order}
                    </label>
                    <input
                      id={`rename-${round.id}`}
                      value={editingLabel}
                      onChange={(event) => setEditingLabel(event.target.value)}
                      maxLength={64}
                    />
                  </div>
                ) : (
                  <div className="admin-round-row__main">
                    <strong>{round.label}</strong>
                    <span className="admin-round-row__meta">
                      Round {round.display_order} of {ordered.length} &middot;{" "}
                      {round.match_count === 0
                        ? "no matches yet"
                        : `${round.match_count} match${round.match_count === 1 ? "" : "es"}`}
                    </span>
                  </div>
                )}

                <div className="admin-round-row__actions">
                  {editingId === round.id ? (
                    <>
                      <button type="button" onClick={() => void handleRename(round)}>
                        Save name
                      </button>
                      <button type="button" onClick={() => setEditingId(null)}>
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={busy || index === 0}
                        onClick={() => void move(index, -1)}
                      >
                        Move earlier
                        <span className="visually-hidden"> - {round.label}</span>
                      </button>
                      <button
                        type="button"
                        disabled={busy || index === ordered.length - 1}
                        onClick={() => void move(index, 1)}
                      >
                        Move later
                        <span className="visually-hidden"> - {round.label}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setEditingId(round.id);
                          setEditingLabel(round.label);
                        }}
                      >
                        Rename
                        <span className="visually-hidden"> {round.label}</span>
                      </button>
                      <button
                        type="button"
                        disabled={round.match_count > 0}
                        title={
                          round.match_count > 0
                            ? "Move or delete this round's matches before deleting it."
                            : undefined
                        }
                        onClick={() => void handleDelete(round)}
                      >
                        Delete
                        <span className="visually-hidden"> {round.label}</span>
                      </button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
