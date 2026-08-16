import { type FormEvent, useEffect, useState } from "react";

import PokemonPicker from "../components/PokemonPicker";
import SaveStatus from "../components/SaveStatus";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useMutation } from "../hooks/useMutation";
import { api } from "../lib/api";
import type {
  MatchRead,
  MatchResultGameInput,
  MatchStage,
  MatchStatus,
  PlayoffRound,
  PokemonInput,
  SeasonEntryRead,
  SeasonSummary,
} from "../types";

/** datetime-local wants "YYYY-MM-DDTHH:mm"; the API speaks ISO-8601 with a zone. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

interface CreateFormState {
  home_player_id: string;
  away_player_id: string;
  stage: MatchStage;
  /** Group stage only - the free-text group/matchday label. */
  round_label: string;
  /** Playoffs only - which round this match belongs to. */
  playoff_round_id: string;
  /** Playoffs only - the match's position within that round, 1 = top. */
  bracket_order: string;
  scheduled_at: string;
}

const EMPTY_CREATE: CreateFormState = {
  home_player_id: "",
  away_player_id: "",
  stage: "group",
  round_label: "",
  playoff_round_id: "",
  bracket_order: "",
  scheduled_at: "",
};

export default function AdminMatchesPage() {
  useDocumentTitle("Admin Matches");
  const { data: seasons } = useAsync<SeasonSummary[]>(() => api.seasons.list({ limit: 500 }), []);
  const [seasonId, setSeasonId] = useState("");

  // Default to the newest season once the list arrives.
  useEffect(() => {
    if (!seasonId && seasons && seasons.length > 0) {
      setSeasonId(seasons[0].id);
    }
  }, [seasons, seasonId]);

  const {
    data: matches,
    isLoading,
    error,
    setData,
  } = useAsync<MatchRead[]>(
    () => (seasonId ? api.matches.listBySeason(seasonId) : Promise.resolve([])),
    [seasonId],
  );
  const { data: roster } = useAsync<SeasonEntryRead[]>(
    () => (seasonId ? api.seasons.roster.list(seasonId) : Promise.resolve([])),
    [seasonId],
  );
  const { data: playoffRounds } = useAsync<PlayoffRound[]>(
    () => (seasonId ? api.seasons.playoffRounds.list(seasonId) : Promise.resolve([])),
    [seasonId],
  );
  // Already in display_order from the API; presented as-is.
  const rounds = playoffRounds ?? [];

  const mutation = useMutation();
  const [createForm, setCreateForm] = useState<CreateFormState>(EMPTY_CREATE);
  const [createError, setCreateError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const rosterPlayers = (roster ?? []).map((entry) => entry.player);

  /** Patch one match in the list from a save response. The expanded editor
   * stays open and keeps its scroll position - nothing is refetched. */
  function replaceMatch(updated: MatchRead) {
    setData((current) => (current ?? []).map((m) => (m.id === updated.id ? updated : m)));
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    if (createForm.home_player_id === createForm.away_player_id) {
      setCreateError("A match needs two different players.");
      return;
    }
    const isPlayoff = createForm.stage === "playoffs";
    if (isPlayoff && !createForm.playoff_round_id) {
      setCreateError("Choose which playoff round this match belongs to.");
      return;
    }
    const created = await mutation.run(
      "create",
      () =>
        api.matches.create({
          season_id: seasonId,
          home_player_id: createForm.home_player_id,
          away_player_id: createForm.away_player_id,
          stage: createForm.stage,
          // The two stages carry different fields, and neither leaks into the
          // other: a group match never sends a round, a playoff match never
          // sends a label.
          playoff_round_id: isPlayoff ? createForm.playoff_round_id : null,
          bracket_order:
            isPlayoff && createForm.bracket_order.trim() !== ""
              ? Number(createForm.bracket_order)
              : null,
          round_label: isPlayoff ? null : createForm.round_label.trim() || null,
          scheduled_at: fromLocalInput(createForm.scheduled_at),
        }),
      "Match created.",
    );
    if (created.ok) {
      setData((current) => [...(current ?? []), created.value]);
      setCreateForm(EMPTY_CREATE);
    }
  }

  async function handleDelete(match: MatchRead) {
    if (
      !window.confirm(
        `Delete ${match.home_player.username} vs ${match.away_player.username}? This also removes its games.`,
      )
    ) {
      return;
    }
    const done = await mutation.run(
      `delete:${match.id}`,
      () => api.matches.delete(match.id),
      "Match deleted.",
    );
    if (done.ok) {
      if (expandedId === match.id) setExpandedId(null);
      setData((current) => (current ?? []).filter((m) => m.id !== match.id));
    }
  }

  return (
    <div className="admin-matches-page">
      <h1>Manage Matches</h1>
      <SaveStatus success={mutation.success} />

      <div className="admin-form__row admin-matches-page__season-select">
        <label htmlFor="admin-match-season">Season</label>
        <select
          id="admin-match-season"
          value={seasonId}
          onChange={(event) => setSeasonId(event.target.value)}
        >
          {(seasons ?? []).map((season) => (
            <option key={season.id} value={season.id}>
              {season.name}
            </option>
          ))}
        </select>
      </div>

      {seasonId && rosterPlayers.length < 2 && (
        <p className="admin-page__error">
          This season needs at least two players on its roster before matches can be created.
        </p>
      )}

      {seasonId && rosterPlayers.length >= 2 && (
        <section>
          <h2>New Match</h2>
          <form className="admin-form" onSubmit={handleCreate}>
            <div className="admin-form__row">
              <label htmlFor="create-home">Home player</label>
              <select
                id="create-home"
                value={createForm.home_player_id}
                onChange={(event) => setCreateForm({ ...createForm, home_player_id: event.target.value })}
                required
              >
                <option value="">Select...</option>
                {rosterPlayers.map((player) => (
                  <option key={player.id} value={player.id}>
                    {player.username}
                  </option>
                ))}
              </select>
            </div>
            <div className="admin-form__row">
              <label htmlFor="create-away">Away player</label>
              <select
                id="create-away"
                value={createForm.away_player_id}
                onChange={(event) => setCreateForm({ ...createForm, away_player_id: event.target.value })}
                required
              >
                <option value="">Select...</option>
                {rosterPlayers.map((player) => (
                  <option key={player.id} value={player.id}>
                    {player.username}
                  </option>
                ))}
              </select>
            </div>
            <div className="admin-form__row">
              <label htmlFor="create-stage">Stage</label>
              <select
                id="create-stage"
                value={createForm.stage}
                onChange={(event) =>
                  // Switching stage clears the other stage's fields, so a round
                  // chosen for a playoff match cannot be carried into a group
                  // match by accident.
                  setCreateForm({
                    ...createForm,
                    stage: event.target.value as MatchStage,
                    playoff_round_id: "",
                    bracket_order: "",
                    round_label: "",
                  })
                }
              >
                <option value="group">Group</option>
                <option value="playoffs">Playoffs</option>
              </select>
            </div>

            {createForm.stage === "group" ? (
              <div className="admin-form__row">
                <label htmlFor="create-round">Group label</label>
                <input
                  id="create-round"
                  value={createForm.round_label}
                  onChange={(event) =>
                    setCreateForm({ ...createForm, round_label: event.target.value })
                  }
                  placeholder="e.g. Group A"
                  maxLength={64}
                />
              </div>
            ) : rounds.length === 0 ? (
              <p role="alert" className="admin-form__error">
                This season has no playoff rounds yet. Create one under Rounds first, then come
                back to add matches to it.
              </p>
            ) : (
              <>
                <div className="admin-form__row">
                  <label htmlFor="create-playoff-round">Playoff round</label>
                  <select
                    id="create-playoff-round"
                    value={createForm.playoff_round_id}
                    onChange={(event) =>
                      setCreateForm({ ...createForm, playoff_round_id: event.target.value })
                    }
                    required
                  >
                    <option value="">Select...</option>
                    {rounds.map((round) => (
                      <option key={round.id} value={round.id}>
                        {round.display_order}. {round.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="admin-form__row">
                  <label htmlFor="create-bracket-order">Position in round</label>
                  <input
                    id="create-bracket-order"
                    type="number"
                    min={1}
                    step={1}
                    value={createForm.bracket_order}
                    onChange={(event) =>
                      setCreateForm({ ...createForm, bracket_order: event.target.value })
                    }
                  />
                  <p className="admin-form__hint">
                    Position 1 is the first (top) match of the round. Each position can be used
                    once per round; leave a number unused for a bye.
                  </p>
                </div>
              </>
            )}
            <div className="admin-form__row">
              <label htmlFor="create-scheduled">Scheduled for</label>
              <input
                id="create-scheduled"
                type="datetime-local"
                value={createForm.scheduled_at}
                onChange={(event) => setCreateForm({ ...createForm, scheduled_at: event.target.value })}
              />
            </div>
            {(createError || mutation.errorFor("create")) && (
              <p role="alert" className="admin-form__error">
                {createError ?? mutation.errorFor("create")}
              </p>
            )}
            <button type="submit" className="admin-form__submit" disabled={mutation.isPending("create")}>
              {mutation.isPending("create") ? "Creating..." : "Create match"}
            </button>
          </form>
        </section>
      )}

      <section>
        <h2>Matches</h2>
        {isLoading && <p role="status">Loading matches...</p>}
        {error && (
          <p role="alert" className="admin-page__error">
            {error}
          </p>
        )}

        {!isLoading && !error && matches && matches.length === 0 && (
          <p>No matches recorded for this season yet.</p>
        )}

        {!isLoading && !error && matches && matches.length > 0 && (
          <ul className="admin-match-list">
            {matches.map((match) => (
              <li key={match.id} className="admin-match-card">
                <div className="admin-match-card__header">
                  <div>
                    <strong>
                      {match.home_player.username} vs {match.away_player.username}
                    </strong>
                    <span className="admin-match-card__meta">
                      {match.round_label || (match.stage === "group" ? "Group" : "Playoffs")} &middot;{" "}
                      {match.status}
                      {match.series.game_count > 1 &&
                        ` · ${match.series.home_wins}-${match.series.away_wins}`}
                      {match.featured_on_homepage && " · featured"}
                    </span>
                  </div>
                  <div className="admin-players-page__actions">
                    <button
                      type="button"
                      onClick={() => setExpandedId(expandedId === match.id ? null : match.id)}
                    >
                      {expandedId === match.id ? "Close" : "Edit"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(match)}
                      disabled={mutation.isPending(`delete:${match.id}`)}
                    >
                      {mutation.isPending(`delete:${match.id}`) ? "Deleting..." : "Delete"}
                    </button>
                    {mutation.errorFor(`delete:${match.id}`) && (
                      <p role="alert" className="admin-form__error">
                        {mutation.errorFor(`delete:${match.id}`)}
                      </p>
                    )}
                  </div>
                </div>

                {expandedId === match.id && (
                  <MatchEditor match={match} playoffRounds={rounds} onSaved={replaceMatch} />
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

interface MatchEditorProps {
  match: MatchRead;
  playoffRounds: PlayoffRound[];
  onSaved: (updated: MatchRead) => void;
}

function MatchEditor({ match, playoffRounds, onSaved }: MatchEditorProps) {
  return (
    <div className="admin-match-card__body">
      <ScheduleForm match={match} playoffRounds={playoffRounds} onSaved={onSaved} />
      <ResultForm match={match} onSaved={onSaved} />
    </div>
  );
}

/**
 * Where and when a match is played - everything that is true before it starts.
 *
 * Deliberately separate from the result form below, and it never touches games,
 * teams, scores or the winner: editing a match's group label must not disturb
 * what the players actually brought.
 */
function ScheduleForm({ match, playoffRounds, onSaved }: MatchEditorProps) {
  const isPlayoff = match.stage === "playoffs";
  const mutation = useMutation();
  const [status, setStatus] = useState<MatchStatus>(match.status);
  const [roundLabel, setRoundLabel] = useState(match.round_label ?? "");
  const [playoffRoundId, setPlayoffRoundId] = useState(match.playoff_round_id ?? "");
  const [bracketOrder, setBracketOrder] = useState(
    match.bracket_order === null ? "" : String(match.bracket_order),
  );
  const [scheduledAt, setScheduledAt] = useState(toLocalInput(match.scheduled_at));
  const [featured, setFeatured] = useState(match.featured_on_homepage);
  const [featureOrder, setFeatureOrder] = useState(
    match.homepage_feature_order === null ? "" : String(match.homepage_feature_order),
  );

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const saved = await mutation.run(
      "schedule",
      () =>
        api.matches.update(match.id, {
          // Only cancellation and un-cancellation live here; completing a match
          // is what the result form does, from the games.
          status,
          ...(isPlayoff
            ? {
                playoff_round_id: playoffRoundId || null,
                bracket_order: bracketOrder.trim() === "" ? null : Number(bracketOrder),
              }
            : { round_label: roundLabel.trim() || null }),
          scheduled_at: fromLocalInput(scheduledAt),
          featured_on_homepage: featured,
          homepage_feature_order:
            featured && featureOrder.trim() !== "" ? Number(featureOrder) : null,
        }),
      "Schedule saved.",
    );
    if (saved.ok) onSaved(saved.value);
  }

  return (
    <form className="admin-form" onSubmit={save}>
      <h3>Scheduling</h3>
      <p className="admin-form__hint">
        When and where this match sits. Saving here never changes the recorded games or teams.
      </p>
      <div className="admin-form__row">
        <label htmlFor={`status-${match.id}`}>Status</label>
        <select
          id={`status-${match.id}`}
          value={status}
          onChange={(event) => setStatus(event.target.value as MatchStatus)}
        >
          <option value="scheduled">Scheduled</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <p className="admin-form__hint">
          Use Cancelled for a match that will not be played. Completing a match is done by entering
          its result below, which derives the score and winner from the games.
        </p>
      </div>
      {isPlayoff ? (
        <>
          <div className="admin-form__row">
            <label htmlFor={`round-${match.id}`}>Playoff round</label>
            <select
              id={`round-${match.id}`}
              value={playoffRoundId}
              onChange={(event) => setPlayoffRoundId(event.target.value)}
            >
              <option value="">Unassigned</option>
              {playoffRounds.map((round) => (
                <option key={round.id} value={round.id}>
                  {round.display_order}. {round.label}
                </option>
              ))}
            </select>
            <p className="admin-form__hint">
              Rename a round under Rounds - the name is shared by every match in it.
            </p>
          </div>
          <div className="admin-form__row">
            <label htmlFor={`slot-${match.id}`}>Position in round</label>
            <input
              id={`slot-${match.id}`}
              type="number"
              min={1}
              step={1}
              value={bracketOrder}
              onChange={(event) => setBracketOrder(event.target.value)}
            />
            <p className="admin-form__hint">Position 1 is the first (top) match of the round.</p>
          </div>
        </>
      ) : (
        <div className="admin-form__row">
          <label htmlFor={`round-${match.id}`}>Group label</label>
          <input
            id={`round-${match.id}`}
            value={roundLabel}
            onChange={(event) => setRoundLabel(event.target.value)}
            maxLength={64}
          />
        </div>
      )}
      <div className="admin-form__row">
        <label htmlFor={`sched-${match.id}`}>Scheduled for</label>
        <input
          id={`sched-${match.id}`}
          type="datetime-local"
          value={scheduledAt}
          onChange={(event) => setScheduledAt(event.target.value)}
        />
        <p className="admin-form__hint">
          Decides which league week the home page lists this match in.
        </p>
      </div>
      <div className="admin-form__row admin-form__row--checkbox">
        <label htmlFor={`feature-${match.id}`}>
          <input
            id={`feature-${match.id}`}
            type="checkbox"
            checked={featured}
            onChange={(event) => setFeatured(event.target.checked)}
          />
          Feature on the home page
        </label>
        <p className="admin-form__hint">
          A featured match appears on the home page whatever week it falls in, and whether it is
          scheduled, completed or cancelled.
        </p>
      </div>
      {featured && (
        <div className="admin-form__row">
          <label htmlFor={`feature-order-${match.id}`}>Feature position</label>
          <input
            id={`feature-order-${match.id}`}
            type="number"
            min={1}
            step={1}
            value={featureOrder}
            onChange={(event) => setFeatureOrder(event.target.value)}
          />
          <p className="admin-form__hint">
            1 shows first. Leave blank to place it after the numbered ones.
          </p>
        </div>
      )}
      <SaveStatus success={mutation.success} error={mutation.error} />
      <button type="submit" className="admin-form__submit" disabled={mutation.isPending("schedule")}>
        {mutation.isPending("schedule") ? "Saving..." : "Save scheduling"}
      </button>
    </form>
  );
}

interface GameDraft {
  winner_id: string;
  replay_url: string;
}

interface ResultFormProps {
  match: MatchRead;
  onSaved: (updated: MatchRead) => void;
}

/**
 * The whole result, in one form and one save.
 *
 * Games, both teams, the completion time and the stream link go to a single
 * transactional endpoint. The series score and the match winner are *not*
 * entered - they are derived from the game winners, shown below before saving,
 * and computed again server-side. That is what makes it impossible for the
 * recorded score and the recorded games to disagree.
 */
function ResultForm({ match, onSaved }: ResultFormProps) {
  const mutation = useMutation();
  const [games, setGames] = useState<GameDraft[]>(
    // A game synthesized from a legacy single replay_url edits like a real one;
    // saving persists it as a real row.
    match.games.map((game) => ({
      winner_id: game.winner_id ?? "",
      replay_url: game.replay_url ?? "",
    })),
  );
  const [homeTeam, setHomeTeam] = useState<PokemonInput[]>(
    match.home_team.map((p) => ({ pokeapi_id: p.pokeapi_id, species_name: p.species_name })),
  );
  const [awayTeam, setAwayTeam] = useState<PokemonInput[]>(
    match.away_team.map((p) => ({ pokeapi_id: p.pokeapi_id, species_name: p.species_name })),
  );
  const [completedAt, setCompletedAt] = useState(toLocalInput(match.completed_at));
  const [youtubeUrl, setYoutubeUrl] = useState(match.youtube_url ?? "");
  const [markCompleted, setMarkCompleted] = useState(match.status === "completed");
  const [localError, setLocalError] = useState<string | null>(null);

  // The same derivation the server performs, shown before saving so the
  // administrator sees what will be recorded.
  const homeWins = games.filter((game) => game.winner_id === match.home_player.id).length;
  const awayWins = games.filter((game) => game.winner_id === match.away_player.id).length;
  const decided = homeWins !== awayWins;
  const derivedWinner = !decided
    ? null
    : homeWins > awayWins
      ? match.home_player.username
      : match.away_player.username;
  const everyGameHasAWinner = games.every((game) => game.winner_id !== "");

  function updateGame(index: number, patch: Partial<GameDraft>) {
    setGames(games.map((game, i) => (i === index ? { ...game, ...patch } : game)));
  }

  async function save() {
    setLocalError(null);
    if (markCompleted) {
      if (games.length === 0) {
        setLocalError("A completed match needs at least one game.");
        return;
      }
      if (!everyGameHasAWinner) {
        setLocalError("Every game needs a winner before the match can be completed.");
        return;
      }
      if (!decided) {
        setLocalError(
          `This series is level at ${homeWins}-${awayWins}. Add the deciding game, or leave it as still scheduled.`,
        );
        return;
      }
      if (!completedAt) {
        setLocalError("A completed match needs a completion time - it sets the Elo order.");
        return;
      }
    }

    const payload = {
      status: markCompleted ? ("completed" as const) : ("scheduled" as const),
      completed_at: markCompleted ? fromLocalInput(completedAt) : null,
      // Numbered automatically from their position, so removing game 2 of three
      // renumbers the rest rather than leaving a gap.
      games: games
        .filter((game) => game.winner_id !== "")
        .map<MatchResultGameInput>((game, index) => ({
          game_number: index + 1,
          winner_id: game.winner_id,
          replay_url: game.replay_url.trim() || null,
        })),
      home_team: homeTeam,
      away_team: awayTeam,
      youtube_url: youtubeUrl.trim() || null,
    };

    const saved = await mutation.run("result", () => api.matches.setResult(match.id, payload), "Result saved.");
    if (saved.ok) onSaved(saved.value);
  }

  return (
    <div className="admin-form admin-result-form">
      <h3>{match.status === "completed" ? "Edit result" : "Enter result"}</h3>
      <p className="admin-form__hint">
        Games, teams and the stream link are saved together in one operation. The series score and
        the winner are worked out from the games below - there is nothing to type twice.
      </p>

      <div className="admin-form__row">
        <span className="admin-form__label">Games</span>
        {games.length === 0 && <p className="admin-form__hint">No games recorded yet.</p>}
        {games.map((game, index) => (
          <div key={index} className="admin-game-row">
            <span className="admin-game-row__number">G{index + 1}</span>
            <select
              aria-label={`Game ${index + 1} winner`}
              value={game.winner_id}
              onChange={(event) => updateGame(index, { winner_id: event.target.value })}
            >
              <option value="">Winner...</option>
              <option value={match.home_player.id}>{match.home_player.username}</option>
              <option value={match.away_player.id}>{match.away_player.username}</option>
            </select>
            <input
              aria-label={`Game ${index + 1} replay URL`}
              type="url"
              placeholder="Replay URL"
              value={game.replay_url}
              onChange={(event) => updateGame(index, { replay_url: event.target.value })}
            />
            <button type="button" onClick={() => setGames(games.filter((_, i) => i !== index))}>
              Remove
              <span className="visually-hidden"> game {index + 1}</span>
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setGames([...games, { winner_id: "", replay_url: "" }])}
          disabled={games.length >= 9}
        >
          Add game
        </button>
      </div>

      <p className="admin-result-form__derived" role="status">
        <strong>Series:</strong> {match.home_player.username} {homeWins} - {awayWins}{" "}
        {match.away_player.username}
        {" · "}
        <strong>Winner:</strong>{" "}
        {games.length === 0
          ? "no games yet"
          : derivedWinner ?? `level at ${homeWins}-${awayWins}, so not decided`}
      </p>

      <PokemonPicker
        label={`${match.home_player.username} brought`}
        value={homeTeam}
        onChange={setHomeTeam}
        max={6}
      />
      <PokemonPicker
        label={`${match.away_player.username} brought`}
        value={awayTeam}
        onChange={setAwayTeam}
        max={6}
      />
      <p className="admin-form__hint">
        Any Pokémon can be recorded here, whether or not the roster says the player owned it at the
        time. This is a record of what was actually brought, so substitutions, corrections and
        one-off rulings can be entered as they happened.
      </p>

      <div className="admin-form__row">
        <label htmlFor={`result-yt-${match.id}`}>Video (YouTube) URL</label>
        <input
          id={`result-yt-${match.id}`}
          type="url"
          value={youtubeUrl}
          onChange={(event) => setYoutubeUrl(event.target.value)}
        />
      </div>

      <div className="admin-form__row admin-form__row--checkbox">
        <label htmlFor={`result-complete-${match.id}`}>
          <input
            id={`result-complete-${match.id}`}
            type="checkbox"
            checked={markCompleted}
            onChange={(event) => setMarkCompleted(event.target.checked)}
          />
          This match is complete
        </label>
        <p className="admin-form__hint">
          Leave unticked for a series still in progress: the games are still recorded, but no winner
          is set and it stays out of Elo.
        </p>
      </div>

      {markCompleted && (
        <div className="admin-form__row">
          <label htmlFor={`result-done-${match.id}`}>Completed at</label>
          <input
            id={`result-done-${match.id}`}
            type="datetime-local"
            value={completedAt}
            onChange={(event) => setCompletedAt(event.target.value)}
            required
          />
          <p className="admin-form__hint">
            This timestamp determines Elo calculation order. Correcting an earlier result rebuilds
            every rating after it.
          </p>
        </div>
      )}

      {localError && (
        <p role="alert" className="admin-form__error">
          {localError}
        </p>
      )}
      <SaveStatus success={mutation.success} error={mutation.error} />
      <button
        type="button"
        className="admin-form__submit"
        onClick={save}
        disabled={mutation.isPending("result")}
      >
        {mutation.isPending("result") ? "Saving..." : "Save result"}
      </button>
    </div>
  );
}
