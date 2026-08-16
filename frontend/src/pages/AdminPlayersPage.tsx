import { type FormEvent, useState } from "react";

import SaveStatus from "../components/SaveStatus";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMutation } from "../hooks/useMutation";
import { api } from "../lib/api";
import type { PlayerAdmin } from "../types";

interface PlayerFormState {
  username: string;
  slug: string;
  biography: string;
  discord_id: string;
  is_active: boolean;
  is_site_creator: boolean;
  initial_elo_rating: string;
}

const EMPTY_FORM: PlayerFormState = {
  username: "",
  slug: "",
  biography: "",
  discord_id: "",
  is_active: true,
  is_site_creator: false,
  initial_elo_rating: "",
};

function toCreateInput(form: PlayerFormState) {
  return {
    username: form.username.trim(),
    // Omitted rather than empty: the server derives it from the username, and
    // an empty string would be a validation error instead.
    slug: form.slug.trim() || undefined,
    biography: form.biography.trim() || null,
    discord_id: form.discord_id.trim() || null,
    is_active: form.is_active,
    is_site_creator: form.is_site_creator,
    initial_elo_rating:
      form.initial_elo_rating.trim() === "" ? null : Number(form.initial_elo_rating),
  };
}

function toUpdateInput(form: PlayerFormState) {
  const { slug, ...rest } = toCreateInput(form);
  // An untouched slug field is not sent at all, so renaming a player never
  // rewrites the URL people have already shared.
  return slug ? { ...rest, slug } : rest;
}

export default function AdminPlayersPage() {
  useDocumentTitle("Admin Players");
  const {
    data: players,
    isLoading,
    error,
    setData,
  } = useAsync<PlayerAdmin[]>(() => api.players.listAdmin({ limit: 500 }), []);

  const mutation = useMutation();
  const [createForm, setCreateForm] = useState<PlayerFormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<PlayerFormState>(EMPTY_FORM);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const created = await mutation.run(
      "create",
      () => api.players.create(toCreateInput(createForm)),
      "Player created.",
    );
    if (created.ok) {
      // Straight into local state from the response - no refetch, so the page
      // does not blink back through a loading state.
      setData((current) => [...(current ?? []), created.value]);
      setCreateForm(EMPTY_FORM);
    }
    // On failure the form keeps every entered value, so it can be corrected.
  }

  function startEdit(player: PlayerAdmin) {
    setEditingId(player.id);
    setEditForm({
      username: player.username,
      slug: player.slug,
      biography: player.biography ?? "",
      discord_id: player.discord_id ?? "",
      is_active: player.is_active,
      is_site_creator: player.is_site_creator,
      initial_elo_rating: String(player.initial_elo_rating),
    });
  }

  async function handleSaveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingId) return;
    const updated = await mutation.run(
      `edit:${editingId}`,
      () => api.players.update(editingId, toUpdateInput(editForm)),
      "Player saved.",
    );
    if (updated.ok) {
      setData((current) =>
        (current ?? []).map((p) => (p.id === updated.value.id ? updated.value : p)),
      );
      setEditingId(null);
    }
  }

  async function handleDelete(player: PlayerAdmin) {
    if (!window.confirm(`Delete player "${player.username}"? This cannot be undone.`)) {
      return;
    }
    const key = `delete:${player.id}`;
    const done = await mutation.run(key, () => api.players.delete(player.id), "Player deleted.");
    if (done.ok) {
      setData((current) => (current ?? []).filter((p) => p.id !== player.id));
    }
  }

  return (
    <div className="admin-players-page">
      <h1>Manage Players</h1>
      <SaveStatus success={mutation.success} />

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
            <label htmlFor="create-slug">URL slug</label>
            <input
              id="create-slug"
              value={createForm.slug}
              onChange={(event) => setCreateForm({ ...createForm, slug: event.target.value })}
              maxLength={64}
              placeholder="derived from the username"
            />
            <p className="admin-form__hint">
              The player&apos;s public address, as in <code>/player/psykick</code>. Leave blank to
              derive it from the username. Changing it later breaks existing links.
            </p>
          </div>
          <div className="admin-form__row">
            <label htmlFor="create-biography">Biography</label>
            <textarea
              id="create-biography"
              rows={4}
              maxLength={4000}
              value={createForm.biography}
              onChange={(event) => setCreateForm({ ...createForm, biography: event.target.value })}
            />
            <p className="admin-form__hint">
              Plain text, shown near the top of their profile. Line breaks are kept.
            </p>
          </div>
          <div className="admin-form__row">
            <label htmlFor="create-discord">Discord ID</label>
            <input
              id="create-discord"
              value={createForm.discord_id}
              onChange={(event) => setCreateForm({ ...createForm, discord_id: event.target.value })}
              maxLength={32}
            />
            <p className="admin-form__hint">Private. Never shown on the public site.</p>
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
          <div className="admin-form__row admin-form__row--checkbox">
            <label htmlFor="create-site-creator">
              <input
                id="create-site-creator"
                type="checkbox"
                checked={createForm.is_site_creator}
                onChange={(event) =>
                  setCreateForm({ ...createForm, is_site_creator: event.target.checked })
                }
              />
              Site Creator
            </label>
            <p className="admin-form__hint">Only one non-placeholder player can hold this marker.</p>
          </div>
          {mutation.errorFor("create") && (
            <p role="alert" className="admin-form__error">
              {mutation.errorFor("create")}
            </p>
          )}
          <button type="submit" className="admin-form__submit" disabled={mutation.isPending("create")}>
            {mutation.isPending("create") ? "Creating..." : "Create player"}
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

        {!isLoading && !error && players && (
          <table className="players-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Slug</th>
                <th>Discord ID</th>
                <th>Starting Elo</th>
                <th>Current Elo</th>
                <th>Active</th>
                <th>Site Creator</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {players.map((player) =>
                editingId === player.id ? (
                  <tr key={player.id}>
                    <td colSpan={8}>
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
                          aria-label="URL slug"
                          value={editForm.slug}
                          onChange={(event) => setEditForm({ ...editForm, slug: event.target.value })}
                          maxLength={64}
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
                        <label>
                          <input
                            type="checkbox"
                            checked={editForm.is_site_creator}
                            onChange={(event) =>
                              setEditForm({ ...editForm, is_site_creator: event.target.checked })
                            }
                          />
                          Site Creator
                        </label>
                        <textarea
                          aria-label="Biography"
                          rows={3}
                          maxLength={4000}
                          placeholder="Biography"
                          value={editForm.biography}
                          onChange={(event) => setEditForm({ ...editForm, biography: event.target.value })}
                        />
                        <button type="submit" disabled={mutation.isPending(`edit:${player.id}`)}>
                          {mutation.isPending(`edit:${player.id}`) ? "Saving..." : "Save"}
                        </button>
                        <button type="button" onClick={() => setEditingId(null)}>
                          Cancel
                        </button>
                        {mutation.errorFor(`edit:${player.id}`) && (
                          <p role="alert" className="admin-form__error">
                            {mutation.errorFor(`edit:${player.id}`)}
                          </p>
                        )}
                      </form>
                    </td>
                  </tr>
                ) : (
                  <tr key={player.id}>
                    <td>{player.username}</td>
                    <td>
                      <code>{player.slug}</code>
                    </td>
                    <td>{player.discord_id ?? "-"}</td>
                    <td>{player.initial_elo_rating}</td>
                    <td>{player.elo_rating}</td>
                    <td>
                      <span className={player.is_active ? "badge badge--active" : "badge badge--inactive"}>
                        {player.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>{player.is_site_creator ? "Yes" : "No"}</td>
                    <td className="admin-players-page__actions">
                      <button type="button" onClick={() => startEdit(player)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(player)}
                        disabled={mutation.isPending(`delete:${player.id}`)}
                      >
                        {mutation.isPending(`delete:${player.id}`) ? "Deleting..." : "Delete"}
                      </button>
                      {mutation.errorFor(`delete:${player.id}`) && (
                        <p role="alert" className="admin-form__error">
                          {mutation.errorFor(`delete:${player.id}`)}
                        </p>
                      )}
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
