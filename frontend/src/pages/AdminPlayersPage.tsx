import { type FormEvent, useState } from "react";

import { useAsync } from "../hooks/useAsync";
import { api, ApiError } from "../lib/api";
import type { PlayerAdmin } from "../types";

interface PlayerFormState {
  username: string;
  discord_id: string;
  is_active: boolean;
  initial_elo_rating: string;
}

const EMPTY_FORM: PlayerFormState = {
  username: "",
  discord_id: "",
  is_active: true,
  initial_elo_rating: "",
};

function toPlayerInput(form: PlayerFormState) {
  return {
    username: form.username.trim(),
    discord_id: form.discord_id.trim() || null,
    is_active: form.is_active,
    initial_elo_rating:
      form.initial_elo_rating.trim() === "" ? null : Number(form.initial_elo_rating),
  };
}

export default function AdminPlayersPage() {
  const { data: players, isLoading, error, refetch } = useAsync<PlayerAdmin[]>(
    () => api.players.listAdmin({ limit: 500 }),
    [],
  );

  const [createForm, setCreateForm] = useState<PlayerFormState>(EMPTY_FORM);
  const [createError, setCreateError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<PlayerFormState>(EMPTY_FORM);
  const [editError, setEditError] = useState<string | null>(null);

  const [rowError, setRowError] = useState<string | null>(null);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    try {
      await api.players.create(toPlayerInput(createForm));
      setCreateForm(EMPTY_FORM);
      refetch();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to create player.");
    }
  }

  function startEdit(player: PlayerAdmin) {
    setEditingId(player.id);
    setEditError(null);
    setEditForm({
      username: player.username,
      discord_id: player.discord_id ?? "",
      is_active: player.is_active,
      initial_elo_rating: String(player.initial_elo_rating),
    });
  }

  async function handleSaveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingId) return;
    setEditError(null);
    try {
      await api.players.update(editingId, toPlayerInput(editForm));
      setEditingId(null);
      refetch();
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Failed to update player.");
    }
  }

  async function handleDelete(player: PlayerAdmin) {
    if (!window.confirm(`Delete player "${player.username}"? This cannot be undone.`)) {
      return;
    }
    setRowError(null);
    try {
      await api.players.delete(player.id);
      refetch();
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "Failed to delete player.");
    }
  }

  return (
    <div className="admin-players-page">
      <h1>Manage Players</h1>

      <section>
        <h2>New Player</h2>
        <form className="admin-form" onSubmit={handleCreate}>
          <div className="admin-form__row">
            <label htmlFor="create-username">Username</label>
            <input
              id="create-username"
              value={createForm.username}
              onChange={(event) => setCreateForm({ ...createForm, username: event.target.value })}
              minLength={2}
              maxLength={32}
              required
            />
          </div>
          <div className="admin-form__row">
            <label htmlFor="create-discord">Discord ID</label>
            <input
              id="create-discord"
              value={createForm.discord_id}
              onChange={(event) => setCreateForm({ ...createForm, discord_id: event.target.value })}
              maxLength={32}
            />
          </div>
          <div className="admin-form__row">
            <label htmlFor="create-elo">Starting Elo</label>
            <input
              id="create-elo"
              type="number"
              min={-10000}
              max={10000}
              value={createForm.initial_elo_rating}
              onChange={(event) =>
                setCreateForm({ ...createForm, initial_elo_rating: event.target.value })
              }
              placeholder="1000"
            />
            <p className="admin-form__hint">
              Current Elo is calculated automatically from dated completed matches.
            </p>
          </div>
          <div className="admin-form__row admin-form__row--checkbox">
            <label htmlFor="create-active">
              <input
                id="create-active"
                type="checkbox"
                checked={createForm.is_active}
                onChange={(event) => setCreateForm({ ...createForm, is_active: event.target.checked })}
              />
              Active
            </label>
          </div>
          {createError && (
            <p role="alert" className="admin-form__error">
              {createError}
            </p>
          )}
          <button type="submit" className="admin-form__submit">
            Create player
          </button>
        </form>
      </section>

      <section>
        <h2>Existing Players</h2>
        {isLoading && <p role="status">Loading players...</p>}
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

        {!isLoading && !error && players && (
          <table className="players-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Discord ID</th>
                <th>Starting Elo</th>
                <th>Current Elo</th>
                <th>Active</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {players.map((player) =>
                editingId === player.id ? (
                  <tr key={player.id}>
                    <td colSpan={6}>
                      <form className="admin-form admin-form--inline" onSubmit={handleSaveEdit}>
                        <input
                          aria-label="Username"
                          value={editForm.username}
                          onChange={(event) => setEditForm({ ...editForm, username: event.target.value })}
                          minLength={2}
                          maxLength={32}
                          required
                        />
                        <input
                          aria-label="Discord ID"
                          value={editForm.discord_id}
                          onChange={(event) => setEditForm({ ...editForm, discord_id: event.target.value })}
                          maxLength={32}
                        />
                        <input
                          aria-label="Starting Elo"
                          type="number"
                          min={-10000}
                          max={10000}
                          value={editForm.initial_elo_rating}
                          onChange={(event) =>
                            setEditForm({ ...editForm, initial_elo_rating: event.target.value })
                          }
                        />
                        <label>
                          <input
                            type="checkbox"
                            checked={editForm.is_active}
                            onChange={(event) => setEditForm({ ...editForm, is_active: event.target.checked })}
                          />
                          Active
                        </label>
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
                  <tr key={player.id}>
                    <td>{player.username}</td>
                    <td>{player.discord_id ?? "-"}</td>
                    <td>{player.initial_elo_rating}</td>
                    <td>{player.elo_rating}</td>
                    <td>
                      <span className={player.is_active ? "badge badge--active" : "badge badge--inactive"}>
                        {player.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="admin-players-page__actions">
                      <button type="button" onClick={() => startEdit(player)}>
                        Edit
                      </button>
                      <button type="button" onClick={() => handleDelete(player)}>
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
