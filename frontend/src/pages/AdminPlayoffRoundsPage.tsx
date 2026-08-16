import { type FormEvent, useEffect, useState } from "react";

import SaveStatus from "../components/SaveStatus";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMutation } from "../hooks/useMutation";
import { api } from "../lib/api";
import type { PlayoffRound, SeasonSummary } from "../types";

/** Manage a season's playoff rounds.
 *
 * The list is always shown in `display_order`, which is the only thing that
 * decides where a round appears on the public bracket. Renaming is separate
 * from moving, so neither can happen by accident, and moving sends the whole
 * ordered list to one transactional endpoint rather than a position at a time.
 */
export default function AdminPlayoffRoundsPage() {
  useDocumentTitle("Admin Playoff Rounds");
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
    setData,
  } = useAsync<PlayoffRound[]>(
    () => (seasonId ? api.seasons.playoffRounds.list(seasonId) : Promise.resolve([])),
    [seasonId],
  );

  const mutation = useMutation();
  const [newLabel, setNewLabel] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingLabel, setEditingLabel] = useState("");

  const ordered = rounds ?? [];

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    const label = newLabel.trim();
    if (!label) {
      setLocalError("A round needs a name.");
      return;
    }
    const created = await mutation.run(
      "create",
      () => api.seasons.playoffRounds.create(seasonId, { label }),
      `Added ${label} to the end of the bracket.`,
    );
    if (created.ok) {
      setData((current) => [...(current ?? []), created.value]);
      setNewLabel("");
    }
  }

  async function handleRename(round: PlayoffRound) {
    setLocalError(null);
    const label = editingLabel.trim();
    if (!label) {
      setLocalError("A round needs a name.");
      return;
    }
    const renamed = await mutation.run(
      `rename:${round.id}`,
      () => api.seasons.playoffRounds.rename(seasonId, round.id, label),
      `Renamed to ${label}. Its position is unchanged.`,
    );
    if (renamed.ok) {
      setData((current) =>
        (current ?? []).map((r) => (r.id === renamed.value.id ? renamed.value : r)),
      );
      setEditingId(null);
    }
  }

  /** Swap a round with its neighbour and send the complete resulting order. */
  async function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= ordered.length) return;
    const next = [...ordered];
    [next[index], next[target]] = [next[target], next[index]];

    setLocalError(null);
    const reordered = await mutation.run(
      `move:${ordered[index].id}`,
      () =>
        api.seasons.playoffRounds.reorder(
          seasonId,
          next.map((round) => round.id),
        ),
      `${ordered[index].label} is now round ${target + 1} of ${ordered.length}.`,
    );
    if (reordered.ok) {
      // The endpoint returns the whole reordered list, so the local copy is
      // replaced from the response rather than refetched.
      setData(reordered.value);
    }
  }

  async function handleDelete(round: PlayoffRound) {
    setLocalError(null);
    if (!window.confirm(`Delete the round "${round.label}"?`)) return;
    const done = await mutation.run(
      `delete:${round.id}`,
      () => api.seasons.playoffRounds.remove(seasonId, round.id),
      `Deleted ${round.label}.`,
    );
    if (done.ok) {
      setData((current) => (current ?? []).filter((r) => r.id !== round.id));
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
            setLocalError(null);
            mutation.reset();
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
            {(mutation.errorFor("create") || localError) && (
              <p role="alert" className="admin-form__error">
                {mutation.errorFor("create") ?? localError}
              </p>
            )}
            <button type="submit" className="admin-form__submit" disabled={mutation.isPending("create")}>
              {mutation.isPending("create") ? "Adding..." : "Add round"}
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
        {/* The visible change after a move is a row swapping places, which is
            easy to miss without sight of the list - so it is announced. */}
        <SaveStatus success={mutation.success} />

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
                      <button
                        type="button"
                        onClick={() => void handleRename(round)}
                        disabled={mutation.isPending(`rename:${round.id}`)}
                      >
                        {mutation.isPending(`rename:${round.id}`) ? "Saving..." : "Save name"}
                      </button>
                      <button type="button" onClick={() => setEditingId(null)}>
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={mutation.isBusy || index === 0}
                        onClick={() => void move(index, -1)}
                      >
                        Move earlier
                        <span className="visually-hidden"> - {round.label}</span>
                      </button>
                      <button
                        type="button"
                        disabled={mutation.isBusy || index === ordered.length - 1}
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
                        disabled={round.match_count > 0 || mutation.isPending(`delete:${round.id}`)}
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
                      {(mutation.errorFor(`delete:${round.id}`) ||
                        mutation.errorFor(`move:${round.id}`) ||
                        mutation.errorFor(`rename:${round.id}`)) && (
                        <p role="alert" className="admin-form__error">
                          {mutation.errorFor(`delete:${round.id}`) ??
                            mutation.errorFor(`move:${round.id}`) ??
                            mutation.errorFor(`rename:${round.id}`)}
                        </p>
                      )}
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
