import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import SaveStatus from "../components/SaveStatus";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMutation } from "../hooks/useMutation";
import { api } from "../lib/api";
import type { Player, SeasonSummary } from "../types";

interface SeasonFormState {
  name: string;
  slug: string;
  start_date: string;
  end_date: string;
  champion_id: string;
  overview: string;
  hall_of_fame_description: string;
  sheet_url: string;
}

const EMPTY_FORM: SeasonFormState = {
  name: "",
  slug: "",
  start_date: "",
  end_date: "",
  champion_id: "",
  overview: "",
  hall_of_fame_description: "",
  sheet_url: "",
};

function toCreateInput(form: SeasonFormState) {
  return {
    name: form.name.trim(),
    // Omitted rather than empty: the server derives it from the name.
    slug: form.slug.trim() || undefined,
    start_date: form.start_date,
    end_date: form.end_date || null,
    champion_id: form.champion_id || null,
    overview: form.overview.trim() || null,
    hall_of_fame_description: form.hall_of_fame_description.trim() || null,
    sheet_url: form.sheet_url.trim() || null,
  };
}

function toUpdateInput(form: SeasonFormState) {
  const { slug, ...rest } = toCreateInput(form);
  // An untouched slug is not sent, so renaming a season keeps its URL.
  return slug ? { ...rest, slug } : rest;
}

export default function AdminSeasonsPage() {
  useDocumentTitle("Admin Seasons");
  const {
    data: seasons,
    isLoading,
    error,
    setData,
  } = useAsync<SeasonSummary[]>(() => api.seasons.list({ limit: 500 }), []);
  const { data: players } = useAsync<Player[]>(() => api.players.list({ limit: 500 }), []);

  const mutation = useMutation();
  const [createForm, setCreateForm] = useState<SeasonFormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<SeasonFormState>(EMPTY_FORM);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const created = await mutation.run(
      "create",
      () => api.seasons.create(toCreateInput(createForm)),
      "Season created.",
    );
    if (created.ok) {
      setData((current) => [created.value, ...(current ?? [])]);
      setCreateForm(EMPTY_FORM);
    }
  }

  async function startEdit(season: SeasonSummary) {
    const detail = await mutation.run(`load:${season.id}`, () => api.seasons.get(season.id));
    if (!detail.ok) return;
    // Only switch the row into edit mode once the form is actually populated -
    // otherwise a fast Save click submits an empty/stale editForm (name: "",
    // start_date: "") before the fetch resolves.
    setEditForm({
      name: detail.value.name,
      slug: detail.value.slug,
      start_date: detail.value.start_date,
      end_date: detail.value.end_date ?? "",
      champion_id: detail.value.champion?.id ?? "",
      overview: detail.value.overview ?? "",
      hall_of_fame_description: detail.value.hall_of_fame_description ?? "",
      sheet_url: detail.value.sheet_url ?? "",
    });
    setEditingId(season.id);
  }

  async function handleSaveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingId) return;
    const updated = await mutation.run(
      `edit:${editingId}`,
      () => api.seasons.update(editingId, toUpdateInput(editForm)),
      "Season saved.",
    );
    if (updated.ok) {
      setData((current) =>
        (current ?? []).map((s) => (s.id === updated.value.id ? updated.value : s)),
      );
      setEditingId(null);
    }
  }

  async function handleDelete(season: SeasonSummary) {
    if (
      !window.confirm(`Delete season "${season.name}"? This also removes its matches and roster. Cannot be undone.`)
    ) {
      return;
    }
    const done = await mutation.run(
      `delete:${season.id}`,
      () => api.seasons.delete(season.id),
      "Season deleted.",
    );
    if (done.ok) {
      setData((current) => (current ?? []).filter((s) => s.id !== season.id));
    }
  }

  return (
    <div className="admin-seasons-page">
      <h1>Manage Seasons</h1>
      <SaveStatus success={mutation.success} />

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
            <label htmlFor="create-season-slug">URL slug</label>
            <input
              id="create-season-slug"
              value={createForm.slug}
              onChange={(event) => setCreateForm({ ...createForm, slug: event.target.value })}
              maxLength={64}
              placeholder="derived from the name"
            />
            <p className="admin-form__hint">
              Used in <code>/seasons/6/standings</code>. Leave blank to derive it - &quot;Season 6&quot;
              becomes &quot;6&quot;. Any stable value works, such as <code>summer-2027</code>.
            </p>
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
          <div className="admin-form__row">
            <label htmlFor="create-season-hof">Hall of Fame description</label>
            <textarea
              id="create-season-hof"
              maxLength={4000}
              value={createForm.hall_of_fame_description}
              onChange={(event) =>
                setCreateForm({ ...createForm, hall_of_fame_description: event.target.value })
              }
            />
            <p className="admin-form__hint">
              The championship story shown on the Hall of Fame. Left blank, that page falls back to
              the overview above and says so.
            </p>
          </div>
          {mutation.errorFor("create") && (
            <p role="alert" className="admin-form__error">
              {mutation.errorFor("create")}
            </p>
          )}
          <button type="submit" className="admin-form__submit" disabled={mutation.isPending("create")}>
            {mutation.isPending("create") ? "Creating..." : "Create season"}
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
        {!isLoading && !error && seasons && (
          <table className="players-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Slug</th>
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
                    <td colSpan={6}>
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
                          aria-label="URL slug"
                          value={editForm.slug}
                          onChange={(event) => setEditForm({ ...editForm, slug: event.target.value })}
                          maxLength={64}
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
                        <textarea
                          aria-label="Hall of Fame description"
                          placeholder="Hall of Fame description"
                          maxLength={4000}
                          value={editForm.hall_of_fame_description}
                          onChange={(event) =>
                            setEditForm({ ...editForm, hall_of_fame_description: event.target.value })
                          }
                        />
                        <button type="submit" disabled={mutation.isPending(`edit:${season.id}`)}>
                          {mutation.isPending(`edit:${season.id}`) ? "Saving..." : "Save"}
                        </button>
                        <button type="button" onClick={() => setEditingId(null)}>
                          Cancel
                        </button>
                        {mutation.errorFor(`edit:${season.id}`) && (
                          <p role="alert" className="admin-form__error">
                            {mutation.errorFor(`edit:${season.id}`)}
                          </p>
                        )}
                      </form>
                    </td>
                  </tr>
                ) : (
                  <tr key={season.id}>
                    <td>{season.name}</td>
                    <td>
                      <code>{season.slug}</code>
                    </td>
                    <td>{season.start_date}</td>
                    <td>{season.end_date ?? "-"}</td>
                    <td>{season.champion?.username ?? "-"}</td>
                    <td className="admin-players-page__actions">
                      <Link to={`/admin/seasons/${season.id}`}>Roster</Link>
                      <button
                        type="button"
                        onClick={() => startEdit(season)}
                        disabled={mutation.isPending(`load:${season.id}`)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(season)}
                        disabled={mutation.isPending(`delete:${season.id}`)}
                      >
                        {mutation.isPending(`delete:${season.id}`) ? "Deleting..." : "Delete"}
                      </button>
                      {(mutation.errorFor(`delete:${season.id}`) ||
                        mutation.errorFor(`load:${season.id}`)) && (
                        <p role="alert" className="admin-form__error">
                          {mutation.errorFor(`delete:${season.id}`) ??
                            mutation.errorFor(`load:${season.id}`)}
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
