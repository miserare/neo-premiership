import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { useAsync } from "../hooks/useAsync";
import { api, ApiError } from "../lib/api";
import type { Player, SeasonSummary } from "../types";

interface SeasonFormState {
  name: string;
  start_date: string;
  end_date: string;
  champion_id: string;
  overview: string;
  sheet_url: string;
}

const EMPTY_FORM: SeasonFormState = {
  name: "",
  start_date: "",
  end_date: "",
  champion_id: "",
  overview: "",
  sheet_url: "",
};

function toSeasonInput(form: SeasonFormState) {
  return {
    name: form.name.trim(),
    start_date: form.start_date,
    end_date: form.end_date || null,
    champion_id: form.champion_id || null,
    overview: form.overview.trim() || null,
    sheet_url: form.sheet_url.trim() || null,
  };
}

export default function AdminSeasonsPage() {
  const { data: seasons, isLoading, error, refetch } = useAsync<SeasonSummary[]>(
    () => api.seasons.list({ limit: 500 }),
    [],
  );
  const { data: players } = useAsync<Player[]>(() => api.players.list({ limit: 500 }), []);

  const [createForm, setCreateForm] = useState<SeasonFormState>(EMPTY_FORM);
  const [createError, setCreateError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<SeasonFormState>(EMPTY_FORM);
  const [editError, setEditError] = useState<string | null>(null);

  const [rowError, setRowError] = useState<string | null>(null);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    try {
      await api.seasons.create(toSeasonInput(createForm));
      setCreateForm(EMPTY_FORM);
      refetch();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to create season.");
    }
  }

  async function startEdit(season: SeasonSummary) {
    setEditError(null);
    try {
      const detail = await api.seasons.get(season.id);
      // Only switch the row into edit mode once the form is actually populated -
      // otherwise a fast Save click submits an empty/stale editForm (name: "",
      // start_date: "") before the fetch resolves.
      setEditForm({
        name: detail.name,
        start_date: detail.start_date,
        end_date: detail.end_date ?? "",
        champion_id: detail.champion?.id ?? "",
        overview: detail.overview ?? "",
        sheet_url: detail.sheet_url ?? "",
      });
      setEditingId(season.id);
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Failed to load season.");
    }
  }

  async function handleSaveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingId) return;
    setEditError(null);
    try {
      await api.seasons.update(editingId, toSeasonInput(editForm));
      setEditingId(null);
      refetch();
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Failed to update season.");
    }
  }

  async function handleDelete(season: SeasonSummary) {
    if (
      !window.confirm(`Delete season "${season.name}"? This also removes its matches and roster. Cannot be undone.`)
    ) {
      return;
    }
    setRowError(null);
    try {
      await api.seasons.delete(season.id);
      refetch();
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "Failed to delete season.");
    }
  }

  return (
    <div className="admin-seasons-page">
      <h1>Manage Seasons</h1>

      <section>
        <h2>New Season</h2>
        <form className="admin-form" onSubmit={handleCreate}>
          <div className="admin-form__row">
            <label htmlFor="create-season-name">Name</label>
            <input
              id="create-season-name"
              value={createForm.name}
              onChange={(event) => setCreateForm({ ...createForm, name: event.target.value })}
              minLength={1}
              maxLength={64}
              required
            />
          </div>
          <div className="admin-form__row">
            <label htmlFor="create-season-start">Start date</label>
            <input
              id="create-season-start"
              type="date"
              value={createForm.start_date}
              onChange={(event) => setCreateForm({ ...createForm, start_date: event.target.value })}
              required
            />
          </div>
          <div className="admin-form__row">
            <label htmlFor="create-season-end">End date</label>
            <input
              id="create-season-end"
              type="date"
              value={createForm.end_date}
              onChange={(event) => setCreateForm({ ...createForm, end_date: event.target.value })}
            />
          </div>
          <div className="admin-form__row">
            <label htmlFor="create-season-champion">Champion</label>
            <select
              id="create-season-champion"
              value={createForm.champion_id}
              onChange={(event) => setCreateForm({ ...createForm, champion_id: event.target.value })}
            >
              <option value="">None</option>
              {players?.map((player) => (
                <option key={player.id} value={player.id}>
                  {player.username}
                </option>
              ))}
            </select>
          </div>
          <div className="admin-form__row">
            <label htmlFor="create-season-sheet">Sheet URL</label>
            <input
              id="create-season-sheet"
              type="url"
              value={createForm.sheet_url}
              onChange={(event) => setCreateForm({ ...createForm, sheet_url: event.target.value })}
            />
          </div>
          <div className="admin-form__row">
            <label htmlFor="create-season-overview">Overview</label>
            <textarea
              id="create-season-overview"
              value={createForm.overview}
              onChange={(event) => setCreateForm({ ...createForm, overview: event.target.value })}
            />
          </div>
          {createError && (
            <p role="alert" className="admin-form__error">
              {createError}
            </p>
          )}
          <button type="submit" className="admin-form__submit">
            Create season
          </button>
        </form>
      </section>

      <section>
        <h2>Existing Seasons</h2>
        {isLoading && <p role="status">Loading seasons...</p>}
        {error && (
          <p role="alert" className="admin-page__error">
            {error}
          </p>
        )}
        {rowError && (
          <p role="alert" className="admin-page__error">
            {rowError}
          </p>
        )}

        {!isLoading && !error && seasons && (
          <table className="players-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Start</th>
                <th>End</th>
                <th>Champion</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {seasons.map((season) =>
                editingId === season.id ? (
                  <tr key={season.id}>
                    <td colSpan={5}>
                      <form className="admin-form admin-form--inline" onSubmit={handleSaveEdit}>
                        <input
                          aria-label="Name"
                          value={editForm.name}
                          onChange={(event) => setEditForm({ ...editForm, name: event.target.value })}
                          minLength={1}
                          maxLength={64}
                          required
                        />
                        <input
                          aria-label="Start date"
                          type="date"
                          value={editForm.start_date}
                          onChange={(event) => setEditForm({ ...editForm, start_date: event.target.value })}
                          required
                        />
                        <input
                          aria-label="End date"
                          type="date"
                          value={editForm.end_date}
                          onChange={(event) => setEditForm({ ...editForm, end_date: event.target.value })}
                        />
                        <select
                          aria-label="Champion"
                          value={editForm.champion_id}
                          onChange={(event) => setEditForm({ ...editForm, champion_id: event.target.value })}
                        >
                          <option value="">None</option>
                          {players?.map((player) => (
                            <option key={player.id} value={player.id}>
                              {player.username}
                            </option>
                          ))}
                        </select>
                        <input
                          aria-label="Sheet URL"
                          type="url"
                          value={editForm.sheet_url}
                          onChange={(event) => setEditForm({ ...editForm, sheet_url: event.target.value })}
                        />
                        <textarea
                          aria-label="Overview"
                          value={editForm.overview}
                          onChange={(event) => setEditForm({ ...editForm, overview: event.target.value })}
                        />
                        <button type="submit">Save</button>
                        <button type="button" onClick={() => setEditingId(null)}>
                          Cancel
                        </button>
                        {editError && (
                          <p role="alert" className="admin-form__error">
                            {editError}
                          </p>
                        )}
                      </form>
                    </td>
                  </tr>
                ) : (
                  <tr key={season.id}>
                    <td>{season.name}</td>
                    <td>{season.start_date}</td>
                    <td>{season.end_date ?? "-"}</td>
                    <td>{season.champion?.username ?? "-"}</td>
                    <td className="admin-players-page__actions">
                      <Link to={`/admin/seasons/${season.id}`}>Roster</Link>
                      <button type="button" onClick={() => startEdit(season)}>
                        Edit
                      </button>
                      <button type="button" onClick={() => handleDelete(season)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
