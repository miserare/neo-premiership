import { Fragment, type FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import PokemonPicker from "../components/PokemonPicker";
import PokemonTeam from "../components/PokemonTeam";
import { useAsync } from "../hooks/useAsync";
import { api, ApiError } from "../lib/api";
import type { Player, PokemonInput, SeasonEntryRead } from "../types";

interface DraftPoolEditorProps {
  seasonId: string;
  entry: SeasonEntryRead;
  onSaved: () => void;
}

function DraftPoolEditor({ seasonId, entry, onSaved }: DraftPoolEditorProps) {
  const [pool, setPool] = useState<PokemonInput[]>(
    entry.pokemon.map((p) => ({ pokeapi_id: p.pokeapi_id, species_name: p.species_name })),
  );
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  async function save() {
    setError(null);
    setIsSaving(true);
    try {
      await api.seasons.roster.setPokemon(seasonId, entry.id, pool);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save drafted Pokémon.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="admin-form">
      <PokemonPicker
        label={`${entry.player.username}'s drafted Pokémon`}
        value={pool}
        onChange={setPool}
        max={12}
      />
      {error && (
        <p role="alert" className="admin-form__error">
          {error}
        </p>
      )}
      <button type="button" className="admin-form__submit" onClick={save} disabled={isSaving}>
        {isSaving ? "Saving..." : "Save draft"}
      </button>
    </div>
  );
}

interface EntryFormState {
  group_label: string;
  tiebreaker_value: string;
}

const EMPTY_ENTRY_FORM: EntryFormState = { group_label: "", tiebreaker_value: "" };

function toEntryInput(form: EntryFormState) {
  return {
    group_label: form.group_label.trim() || null,
    tiebreaker_value: form.tiebreaker_value.trim() === "" ? null : Number(form.tiebreaker_value),
  };
}

export default function AdminSeasonRosterPage() {
  const { seasonId } = useParams<{ seasonId: string }>();

  const {
    data: season,
    isLoading: seasonLoading,
    error: seasonError,
  } = useAsync(() => api.seasons.get(seasonId!), [seasonId]);
  const {
    data: roster,
    isLoading: rosterLoading,
    error: rosterError,
    refetch: refetchRoster,
  } = useAsync<SeasonEntryRead[]>(() => api.seasons.roster.list(seasonId!), [seasonId]);
  const { data: players } = useAsync<Player[]>(() => api.players.list({ limit: 500 }), []);

  const [newPlayerId, setNewPlayerId] = useState("");
  const [addForm, setAddForm] = useState<EntryFormState>(EMPTY_ENTRY_FORM);
  const [addError, setAddError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EntryFormState>(EMPTY_ENTRY_FORM);
  const [editError, setEditError] = useState<string | null>(null);

  const [rowError, setRowError] = useState<string | null>(null);
  const [draftingId, setDraftingId] = useState<string | null>(null);

  const rosterPlayerIds = new Set((roster ?? []).map((entry) => entry.player.id));
  const availablePlayers = (players ?? []).filter((player) => !rosterPlayerIds.has(player.id));

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!seasonId || !newPlayerId) return;
    setAddError(null);
    try {
      await api.seasons.roster.add(seasonId, { player_id: newPlayerId, ...toEntryInput(addForm) });
      setNewPlayerId("");
      setAddForm(EMPTY_ENTRY_FORM);
      refetchRoster();
    } catch (err) {
      setAddError(err instanceof ApiError ? err.message : "Failed to add player to roster.");
    }
  }

  function startEdit(entry: SeasonEntryRead) {
    setEditingId(entry.id);
    setEditError(null);
    setEditForm({
      group_label: entry.group_label ?? "",
      tiebreaker_value: entry.tiebreaker_value === null ? "" : String(entry.tiebreaker_value),
    });
  }

  async function handleSaveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!seasonId || !editingId) return;
    setEditError(null);
    try {
      await api.seasons.roster.update(seasonId, editingId, toEntryInput(editForm));
      setEditingId(null);
      refetchRoster();
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Failed to update roster entry.");
    }
  }

  async function handleRemove(entry: SeasonEntryRead) {
    if (!seasonId) return;
    if (!window.confirm(`Remove ${entry.player.username} from the roster?`)) {
      return;
    }
    setRowError(null);
    try {
      await api.seasons.roster.remove(seasonId, entry.id);
      refetchRoster();
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "Failed to remove roster entry.");
    }
  }

  const isLoading = seasonLoading || rosterLoading;
  const error = seasonError || rosterError;

  return (
    <div className="admin-season-roster-page">
      <p>
        <Link to="/admin/seasons">&larr; Back to seasons</Link>
      </p>
      <h1>{season ? `${season.name} Roster` : "Season Roster"}</h1>

      {isLoading && <p role="status">Loading roster...</p>}
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

      {!isLoading && !error && (
        <>
          <section>
            <h2>Add Player</h2>
            <form className="admin-form" onSubmit={handleAdd}>
              <div className="admin-form__row">
                <label htmlFor="add-player">Player</label>
                <select
                  id="add-player"
                  value={newPlayerId}
                  onChange={(event) => setNewPlayerId(event.target.value)}
                  required
                >
                  <option value="" disabled>
                    Select a player...
                  </option>
                  {availablePlayers.map((player) => (
                    <option key={player.id} value={player.id}>
                      {player.username}
                    </option>
                  ))}
                </select>
              </div>
              <div className="admin-form__row">
                <label htmlFor="add-group-label">Group label</label>
                <input
                  id="add-group-label"
                  value={addForm.group_label}
                  onChange={(event) => setAddForm({ ...addForm, group_label: event.target.value })}
                  maxLength={32}
                />
              </div>
              <div className="admin-form__row">
                <label htmlFor="add-tiebreaker">Tiebreaker value</label>
                <input
                  id="add-tiebreaker"
                  type="number"
                  step="any"
                  value={addForm.tiebreaker_value}
                  onChange={(event) => setAddForm({ ...addForm, tiebreaker_value: event.target.value })}
                />
              </div>
              {addError && (
                <p role="alert" className="admin-form__error">
                  {addError}
                </p>
              )}
              <button type="submit" className="admin-form__submit">
                Add to roster
              </button>
            </form>
          </section>

          <section>
            <h2>Current Roster</h2>
            {roster && roster.length === 0 && <p>No players on this season's roster yet.</p>}
            {roster && roster.length > 0 && (
              <table className="players-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Group</th>
                    <th>Tiebreaker</th>
                    <th>Drafted</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {roster.map((entry) =>
                    editingId === entry.id ? (
                      <tr key={entry.id}>
                        <td colSpan={5}>
                          <form className="admin-form admin-form--inline" onSubmit={handleSaveEdit}>
                            <span>{entry.player.username}</span>
                            <input
                              aria-label="Group label"
                              value={editForm.group_label}
                              onChange={(event) => setEditForm({ ...editForm, group_label: event.target.value })}
                              maxLength={32}
                            />
                            <input
                              aria-label="Tiebreaker value"
                              type="number"
                              step="any"
                              value={editForm.tiebreaker_value}
                              onChange={(event) =>
                                setEditForm({ ...editForm, tiebreaker_value: event.target.value })
                              }
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
                      <Fragment key={entry.id}>
                        <tr>
                          <td>{entry.player.username}</td>
                          <td>{entry.group_label ?? "-"}</td>
                          <td>{entry.tiebreaker_value ?? "-"}</td>
                          <td>
                            <PokemonTeam pokemon={entry.pokemon} size={28} emptyLabel="None" />
                          </td>
                          <td className="admin-players-page__actions">
                            <button type="button" onClick={() => startEdit(entry)}>
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => setDraftingId(draftingId === entry.id ? null : entry.id)}
                            >
                              {draftingId === entry.id ? "Close" : "Draft"}
                            </button>
                            <button type="button" onClick={() => handleRemove(entry)}>
                              Remove
                            </button>
                          </td>
                        </tr>
                        {draftingId === entry.id && (
                          <tr>
                            <td colSpan={5}>
                              <DraftPoolEditor
                                seasonId={seasonId!}
                                entry={entry}
                                onSaved={() => {
                                  setDraftingId(null);
                                  refetchRoster();
                                }}
                              />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ),
                  )}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}
