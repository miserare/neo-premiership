import { Fragment, type FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";

import PokemonPicker from "../components/PokemonPicker";
import PokemonTeam from "../components/PokemonTeam";
import SaveStatus from "../components/SaveStatus";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMutation } from "../hooks/useMutation";
import { api } from "../lib/api";
import type { Player, PokemonInput, RosterChangeType, SeasonEntryRead } from "../types";

interface DraftPoolEditorProps {
  seasonId: string;
  entry: SeasonEntryRead;
  onSaved: (updated: SeasonEntryRead) => void;
}

function DraftPoolEditor({ seasonId, entry, onSaved }: DraftPoolEditorProps) {
  const [pool, setPool] = useState<PokemonInput[]>(
    entry.pokemon.map((p) => ({ pokeapi_id: p.pokeapi_id, species_name: p.species_name })),
  );
  const [changeType, setChangeType] = useState<RosterChangeType>(
    entry.former_pokemon.length > 0 ? "free_agency" : "draft",
  );
  const [effectiveAt, setEffectiveAt] = useState("");
  const mutation = useMutation();

  async function save() {
    const saved = await mutation.run(
      "pool",
      () =>
        api.seasons.roster.setPokemon(seasonId, entry.id, {
          pokemon: pool,
          change_type: changeType,
          ...(effectiveAt ? { effective_at: new Date(effectiveAt).toISOString() } : {}),
        }),
      "Roster saved.",
    );
    if (saved.ok) {
      // The updated entry comes back from the save, so the parent list is
      // patched in place and the open editor stays open.
      onSaved(saved.value);
    }
  }

  return (
    <div className="admin-form">
      <h3>Current ownership</h3>
      <p className="admin-form__hint">
        This list is the player&apos;s roster now. Removing a Pokémon archives its ownership;
        previously recorded match teams are never changed.
      </p>
      <PokemonPicker
        label={`${entry.player.username}'s current Pokémon`}
        value={pool}
        onChange={setPool}
        max={12}
      />
      <div className="admin-form__row">
        <label htmlFor={`change-type-${entry.id}`}>Reason for this change</label>
        <select
          id={`change-type-${entry.id}`}
          value={changeType}
          onChange={(event) => setChangeType(event.target.value as RosterChangeType)}
        >
          <option value="draft">Draft</option>
          <option value="free_agency">Free agency / waiver</option>
          <option value="trade">Trade</option>
          <option value="correction">Record correction</option>
        </select>
      </div>
      <div className="admin-form__row">
        <label htmlFor={`effective-at-${entry.id}`}>Effective at</label>
        <input
          id={`effective-at-${entry.id}`}
          type="datetime-local"
          value={effectiveAt}
          onChange={(event) => setEffectiveAt(event.target.value)}
        />
        <p className="admin-form__hint">
          Leave blank to use the current time. For a trade, use the same timestamp when updating
          both players.
        </p>
      </div>
      <SaveStatus success={mutation.success} />
      <button
        type="button"
        className="admin-form__submit"
        onClick={save}
        disabled={mutation.isPending("pool")}
      >
        {mutation.isPending("pool") ? "Saving..." : "Save current roster"}
      </button>
      {entry.former_pokemon.length > 0 && (
        <div className="admin-roster-history">
          <h3>Formerly rostered</h3>
          <ul>
            {entry.former_pokemon.map((pokemon) => (
              <li key={pokemon.id}>
                <strong>{pokemon.species_name}</strong>
                {" — "}
                {pokemon.acquisition_type.replace("_", " ")}
                {pokemon.acquired_at && ` ${new Date(pokemon.acquired_at).toLocaleDateString()}`}
                {" → "}
                {pokemon.release_type?.replace("_", " ")}
                {pokemon.released_at && ` ${new Date(pokemon.released_at).toLocaleDateString()}`}
              </li>
            ))}
          </ul>
        </div>
      )}
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
  useDocumentTitle("Admin Roster");

  const {
    data: season,
    isLoading: seasonLoading,
    error: seasonError,
  } = useAsync(() => api.seasons.get(seasonId!), [seasonId]);
  const {
    data: roster,
    isLoading: rosterLoading,
    error: rosterError,
    setData: setRoster,
  } = useAsync<SeasonEntryRead[]>(() => api.seasons.roster.list(seasonId!), [seasonId]);
  const { data: players } = useAsync<Player[]>(() => api.players.list({ limit: 500 }), []);

  const mutation = useMutation();
  const [newPlayerId, setNewPlayerId] = useState("");
  const [addForm, setAddForm] = useState<EntryFormState>(EMPTY_ENTRY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EntryFormState>(EMPTY_ENTRY_FORM);
  const [draftingId, setDraftingId] = useState<string | null>(null);

  function replaceEntry(updated: SeasonEntryRead) {
    setRoster((current) => (current ?? []).map((e) => (e.id === updated.id ? updated : e)));
  }

  const rosterPlayerIds = new Set((roster ?? []).map((entry) => entry.player.id));
  const availablePlayers = (players ?? []).filter((player) => !rosterPlayerIds.has(player.id));

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!seasonId || !newPlayerId) return;
    const added = await mutation.run(
      "add",
      () => api.seasons.roster.add(seasonId, { player_id: newPlayerId, ...toEntryInput(addForm) }),
      "Player added to the roster.",
    );
    if (added.ok) {
      setRoster((current) => [...(current ?? []), added.value]);
      setNewPlayerId("");
      setAddForm(EMPTY_ENTRY_FORM);
    }
  }

  function startEdit(entry: SeasonEntryRead) {
    setEditingId(entry.id);
    setEditForm({
      group_label: entry.group_label ?? "",
      tiebreaker_value: entry.tiebreaker_value === null ? "" : String(entry.tiebreaker_value),
    });
  }

  async function handleSaveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!seasonId || !editingId) return;
    const updated = await mutation.run(
      `edit:${editingId}`,
      () => api.seasons.roster.update(seasonId, editingId, toEntryInput(editForm)),
      "Roster entry saved.",
    );
    if (updated.ok) {
      replaceEntry(updated.value);
      setEditingId(null);
    }
  }

  async function handleRemove(entry: SeasonEntryRead) {
    if (!seasonId) return;
    if (!window.confirm(`Remove ${entry.player.username} from the roster?`)) {
      return;
    }
    const done = await mutation.run(
      `remove:${entry.id}`,
      () => api.seasons.roster.remove(seasonId, entry.id),
      "Player removed from the roster.",
    );
    if (done.ok) {
      setRoster((current) => (current ?? []).filter((e) => e.id !== entry.id));
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
      <SaveStatus success={mutation.success} error={mutation.error} />

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
                <label htmlFor="add-tiebreaker">Legacy secondary tiebreaker</label>
                <input
                  id="add-tiebreaker"
                  type="number"
                  step="any"
                  value={addForm.tiebreaker_value}
                  onChange={(event) => setAddForm({ ...addForm, tiebreaker_value: event.target.value })}
                />
              </div>
              {mutation.errorFor("add") && (
                <p role="alert" className="admin-form__error">
                  {mutation.errorFor("add")}
                </p>
              )}
              <button type="submit" className="admin-form__submit" disabled={mutation.isPending("add")}>
                {mutation.isPending("add") ? "Adding..." : "Add to roster"}
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
                    <th>Legacy tiebreaker</th>
                    <th>Current Pokémon</th>
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
                              aria-label="Legacy secondary tiebreaker"
                              type="number"
                              step="any"
                              value={editForm.tiebreaker_value}
                              onChange={(event) =>
                                setEditForm({ ...editForm, tiebreaker_value: event.target.value })
                              }
                            />
                            <button type="submit" disabled={mutation.isPending(`edit:${entry.id}`)}>
                              {mutation.isPending(`edit:${entry.id}`) ? "Saving..." : "Save"}
                            </button>
                            <button type="button" onClick={() => setEditingId(null)}>
                              Cancel
                            </button>
                            {mutation.errorFor(`edit:${entry.id}`) && (
                              <p role="alert" className="admin-form__error">
                                {mutation.errorFor(`edit:${entry.id}`)}
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
                              {draftingId === entry.id ? "Close" : "Manage roster"}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleRemove(entry)}
                              disabled={mutation.isPending(`remove:${entry.id}`)}
                            >
                              {mutation.isPending(`remove:${entry.id}`) ? "Removing..." : "Remove"}
                            </button>
                            {mutation.errorFor(`remove:${entry.id}`) && (
                              <p role="alert" className="admin-form__error">
                                {mutation.errorFor(`remove:${entry.id}`)}
                              </p>
                            )}
                          </td>
                        </tr>
                        {draftingId === entry.id && (
                          <tr>
                            <td colSpan={5}>
                              {/* The editor stays open after a save: the
                                  updated entry is patched into the list, so
                                  scroll position and the picker's state
                                  survive. */}
                              <DraftPoolEditor
                                seasonId={seasonId!}
                                entry={entry}
                                onSaved={replaceEntry}
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
