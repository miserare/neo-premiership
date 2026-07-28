import { type FormEvent, useEffect, useState } from "react";

import { useAsync } from "../hooks/useAsync";
import { api, ApiError } from "../lib/api";
import type { AnnouncementRead, SiteLinks } from "../types";

/** datetime-local wants "YYYY-MM-DDTHH:mm"; the API speaks ISO-8601 with a zone. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

const EMPTY_LINKS: SiteLinks = {
  stream_url: null,
  stream_label: null,
  document_url: null,
  document_label: null,
  table_url: null,
  table_label: null,
};

interface AnnouncementFormState {
  title: string;
  body: string;
  link_url: string;
  published_at: string;
}

const EMPTY_ANNOUNCEMENT: AnnouncementFormState = {
  title: "",
  body: "",
  link_url: "",
  published_at: "",
};

export default function AdminSitePage() {
  return (
    <div className="admin-site-page">
      <h1>Site Content</h1>
      <HomeLinksEditor />
      <AnnouncementsEditor />
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function HomeLinksEditor() {
  const { data, isLoading, error, refetch } = useAsync<SiteLinks>(() => api.siteLinks.get(), []);
  const [form, setForm] = useState<SiteLinks>(EMPTY_LINKS);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  function field(key: keyof SiteLinks): string {
    return form[key] ?? "";
  }

  function set(key: keyof SiteLinks, value: string) {
    setForm({ ...form, [key]: value.trim() === "" ? null : value });
    setSaved(false);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveError(null);
    setSaved(false);
    try {
      await api.siteLinks.set(form);
      setSaved(true);
      refetch();
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to save links.");
    }
  }

  if (isLoading) return <p role="status">Loading site links...</p>;
  if (error) {
    return (
      <p role="alert" className="admin-page__error">
        {error}
      </p>
    );
  }

  return (
    <section>
      <h2>Home Page Links</h2>
      <form className="admin-form" onSubmit={handleSubmit}>
        <p className="admin-form__hint">
          Leave a URL blank to let the site work it out automatically: the stream falls back to the
          most recent match with a video, the document to the current season&apos;s sheet, and the
          table to that season&apos;s own page.
        </p>

        <div className="admin-form__row">
          <label htmlFor="stream-url">Stream URL</label>
          <input
            id="stream-url"
            type="url"
            value={field("stream_url")}
            onChange={(event) => set("stream_url", event.target.value)}
            placeholder="Automatic - latest match video"
          />
        </div>
        <div className="admin-form__row">
          <label htmlFor="stream-label">Stream label</label>
          <input
            id="stream-label"
            value={field("stream_label")}
            onChange={(event) => set("stream_label", event.target.value)}
            maxLength={120}
            placeholder="Watch the latest stream"
          />
        </div>

        <div className="admin-form__row">
          <label htmlFor="doc-url">Document URL</label>
          <input
            id="doc-url"
            type="url"
            value={field("document_url")}
            onChange={(event) => set("document_url", event.target.value)}
            placeholder="Automatic - current season sheet"
          />
        </div>
        <div className="admin-form__row">
          <label htmlFor="doc-label">Document label</label>
          <input
            id="doc-label"
            value={field("document_label")}
            onChange={(event) => set("document_label", event.target.value)}
            maxLength={120}
            placeholder="Open the league document"
          />
        </div>

        <div className="admin-form__row">
          <label htmlFor="table-url">Table URL</label>
          <input
            id="table-url"
            type="url"
            value={field("table_url")}
            onChange={(event) => set("table_url", event.target.value)}
            placeholder="Automatic - current season standings"
          />
        </div>
        <div className="admin-form__row">
          <label htmlFor="table-label">Table label</label>
          <input
            id="table-label"
            value={field("table_label")}
            onChange={(event) => set("table_label", event.target.value)}
            maxLength={120}
            placeholder="View the league table"
          />
        </div>

        {saveError && (
          <p role="alert" className="admin-form__error">
            {saveError}
          </p>
        )}
        {saved && <p className="admin-form__saved">Saved.</p>}
        <button type="submit" className="admin-form__submit">
          Save links
        </button>
      </form>
    </section>
  );
}

/* -------------------------------------------------------------------------- */

function AnnouncementsEditor() {
  const {
    data: announcements,
    isLoading,
    error,
    refetch,
  } = useAsync<AnnouncementRead[]>(() => api.announcements.list(), []);

  const [createForm, setCreateForm] = useState<AnnouncementFormState>(EMPTY_ANNOUNCEMENT);
  const [createError, setCreateError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<AnnouncementFormState>(EMPTY_ANNOUNCEMENT);
  const [editError, setEditError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  function toPayload(form: AnnouncementFormState) {
    return {
      title: form.title.trim(),
      body: form.body.trim(),
      link_url: form.link_url.trim() || null,
      published_at: fromLocalInput(form.published_at),
    };
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    try {
      await api.announcements.create(toPayload(createForm));
      setCreateForm(EMPTY_ANNOUNCEMENT);
      refetch();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to post announcement.");
    }
  }

  function startEdit(announcement: AnnouncementRead) {
    setEditingId(announcement.id);
    setEditError(null);
    setEditForm({
      title: announcement.title,
      body: announcement.body,
      link_url: announcement.link_url ?? "",
      published_at: toLocalInput(announcement.published_at),
    });
  }

  async function handleSaveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingId) return;
    setEditError(null);
    try {
      await api.announcements.update(editingId, toPayload(editForm));
      setEditingId(null);
      refetch();
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Failed to save announcement.");
    }
  }

  async function handleDelete(announcement: AnnouncementRead) {
    if (!window.confirm(`Delete "${announcement.title}"? This cannot be undone.`)) return;
    setRowError(null);
    try {
      await api.announcements.delete(announcement.id);
      refetch();
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "Failed to delete announcement.");
    }
  }

  return (
    <section>
      <h2>Announcements</h2>

      <form className="admin-form" onSubmit={handleCreate}>
        <h3>New announcement</h3>
        <div className="admin-form__row">
          <label htmlFor="ann-title">Title</label>
          <input
            id="ann-title"
            value={createForm.title}
            onChange={(event) => setCreateForm({ ...createForm, title: event.target.value })}
            maxLength={160}
            required
          />
        </div>
        <div className="admin-form__row">
          <label htmlFor="ann-body">Body</label>
          <textarea
            id="ann-body"
            value={createForm.body}
            onChange={(event) => setCreateForm({ ...createForm, body: event.target.value })}
            required
          />
        </div>
        <div className="admin-form__row">
          <label htmlFor="ann-link">Link URL</label>
          <input
            id="ann-link"
            type="url"
            value={createForm.link_url}
            onChange={(event) => setCreateForm({ ...createForm, link_url: event.target.value })}
          />
        </div>
        <div className="admin-form__row">
          <label htmlFor="ann-date">Published at</label>
          <input
            id="ann-date"
            type="datetime-local"
            value={createForm.published_at}
            onChange={(event) => setCreateForm({ ...createForm, published_at: event.target.value })}
          />
          <p className="admin-form__hint">Leave blank to publish with the current time.</p>
        </div>
        {createError && (
          <p role="alert" className="admin-form__error">
            {createError}
          </p>
        )}
        <button type="submit" className="admin-form__submit">
          Post announcement
        </button>
      </form>

      {isLoading && <p role="status">Loading announcements...</p>}
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

      {!isLoading && !error && announcements && announcements.length === 0 && (
        <p>No announcements posted yet.</p>
      )}

      {!isLoading && !error && announcements && announcements.length > 0 && (
        <ul className="admin-match-list">
          {announcements.map((announcement) =>
            editingId === announcement.id ? (
              <li key={announcement.id} className="admin-match-card">
                <form className="admin-form" onSubmit={handleSaveEdit}>
                  <div className="admin-form__row">
                    <label htmlFor={`edit-title-${announcement.id}`}>Title</label>
                    <input
                      id={`edit-title-${announcement.id}`}
                      value={editForm.title}
                      onChange={(event) => setEditForm({ ...editForm, title: event.target.value })}
                      maxLength={160}
                      required
                    />
                  </div>
                  <div className="admin-form__row">
                    <label htmlFor={`edit-body-${announcement.id}`}>Body</label>
                    <textarea
                      id={`edit-body-${announcement.id}`}
                      value={editForm.body}
                      onChange={(event) => setEditForm({ ...editForm, body: event.target.value })}
                      required
                    />
                  </div>
                  <div className="admin-form__row">
                    <label htmlFor={`edit-link-${announcement.id}`}>Link URL</label>
                    <input
                      id={`edit-link-${announcement.id}`}
                      type="url"
                      value={editForm.link_url}
                      onChange={(event) => setEditForm({ ...editForm, link_url: event.target.value })}
                    />
                  </div>
                  <div className="admin-form__row">
                    <label htmlFor={`edit-date-${announcement.id}`}>Published at</label>
                    <input
                      id={`edit-date-${announcement.id}`}
                      type="datetime-local"
                      value={editForm.published_at}
                      onChange={(event) =>
                        setEditForm({ ...editForm, published_at: event.target.value })
                      }
                    />
                  </div>
                  {editError && (
                    <p role="alert" className="admin-form__error">
                      {editError}
                    </p>
                  )}
                  <div className="admin-match-card__actions">
                    <button type="submit" className="admin-form__submit">
                      Save
                    </button>
                    <button type="button" onClick={() => setEditingId(null)}>
                      Cancel
                    </button>
                  </div>
                </form>
              </li>
            ) : (
              <li key={announcement.id} className="admin-match-card">
                <div className="admin-match-card__header">
                  <div>
                    <strong>{announcement.title}</strong>
                    <span className="admin-match-card__meta">
                      {new Date(announcement.published_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </div>
                  <div className="admin-players-page__actions">
                    <button type="button" onClick={() => startEdit(announcement)}>
                      Edit
                    </button>
                    <button type="button" onClick={() => handleDelete(announcement)}>
                      Delete
                    </button>
                  </div>
                </div>
              </li>
            ),
          )}
        </ul>
      )}
    </section>
  );
}
