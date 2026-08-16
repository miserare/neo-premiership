import { type FormEvent, useEffect, useState } from "react";

import SaveStatus from "../components/SaveStatus";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMutation } from "../hooks/useMutation";
import { formatDate } from "../lib/format";
import { api } from "../lib/api";
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
  useDocumentTitle("Admin Site");
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
  const { data, isLoading, error, setData } = useAsync<SiteLinks>(() => api.siteLinks.get(), []);
  const [form, setForm] = useState<SiteLinks>(EMPTY_LINKS);
  const mutation = useMutation();

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  function field(key: keyof SiteLinks): string {
    return form[key] ?? "";
  }

  function set(key: keyof SiteLinks, value: string) {
    setForm({ ...form, [key]: value.trim() === "" ? null : value });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const saved = await mutation.run("links", () => api.siteLinks.set(form), "Home page links saved.");
    if (saved.ok) {
      // The response is the new state, so nothing is refetched and the form
      // keeps its scroll position and focus.
      setData(saved.value);
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

        <SaveStatus success={mutation.success} error={mutation.error} />
        <button type="submit" className="admin-form__submit" disabled={mutation.isPending("links")}>
          {mutation.isPending("links") ? "Saving..." : "Save links"}
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
    setData,
  } = useAsync<AnnouncementRead[]>(() => api.announcements.list(), []);

  const mutation = useMutation();
  const [createForm, setCreateForm] = useState<AnnouncementFormState>(EMPTY_ANNOUNCEMENT);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<AnnouncementFormState>(EMPTY_ANNOUNCEMENT);

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
    const created = await mutation.run(
      "create",
      () => api.announcements.create(toPayload(createForm)),
      "Announcement posted.",
    );
    if (created.ok) {
      setData((current) => [created.value, ...(current ?? [])]);
      setCreateForm(EMPTY_ANNOUNCEMENT);
    }
  }

  function startEdit(announcement: AnnouncementRead) {
    setEditingId(announcement.id);
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
    const updated = await mutation.run(
      `edit:${editingId}`,
      () => api.announcements.update(editingId, toPayload(editForm)),
      "Announcement saved.",
    );
    if (updated.ok) {
      setData((current) =>
        (current ?? []).map((a) => (a.id === updated.value.id ? updated.value : a)),
      );
      setEditingId(null);
    }
  }

  async function handleDelete(announcement: AnnouncementRead) {
    if (!window.confirm(`Delete "${announcement.title}"? This cannot be undone.`)) return;
    const done = await mutation.run(
      `delete:${announcement.id}`,
      () => api.announcements.delete(announcement.id),
      "Announcement deleted.",
    );
    if (done.ok) {
      setData((current) => (current ?? []).filter((a) => a.id !== announcement.id));
    }
  }

  return (
    <section>
      <h2>Announcements</h2>
      <SaveStatus success={mutation.success} />

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
            rows={6}
            required
          />
          <p className="admin-form__hint">
            Plain text. Line breaks and blank lines are kept exactly as typed on the home page.
          </p>
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
        {mutation.errorFor("create") && (
          <p role="alert" className="admin-form__error">
            {mutation.errorFor("create")}
          </p>
        )}
        <button type="submit" className="admin-form__submit" disabled={mutation.isPending("create")}>
          {mutation.isPending("create") ? "Posting..." : "Post announcement"}
        </button>
      </form>

      {isLoading && <p role="status">Loading announcements...</p>}
      {error && (
        <p role="alert" className="admin-page__error">
          {error}
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
                      rows={6}
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
                  {mutation.errorFor(`edit:${announcement.id}`) && (
                    <p role="alert" className="admin-form__error">
                      {mutation.errorFor(`edit:${announcement.id}`)}
                    </p>
                  )}
                  <div className="admin-match-card__actions">
                    <button
                      type="submit"
                      className="admin-form__submit"
                      disabled={mutation.isPending(`edit:${announcement.id}`)}
                    >
                      {mutation.isPending(`edit:${announcement.id}`) ? "Saving..." : "Save"}
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
                      {formatDate(announcement.published_at)}
                    </span>
                  </div>
                  <div className="admin-players-page__actions">
                    <button type="button" onClick={() => startEdit(announcement)}>
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(announcement)}
                      disabled={mutation.isPending(`delete:${announcement.id}`)}
                    >
                      {mutation.isPending(`delete:${announcement.id}`) ? "Deleting..." : "Delete"}
                    </button>
                    {mutation.errorFor(`delete:${announcement.id}`) && (
                      <p role="alert" className="admin-form__error">
                        {mutation.errorFor(`delete:${announcement.id}`)}
                      </p>
                    )}
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
