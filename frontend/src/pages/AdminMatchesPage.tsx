import { type FormEvent, useEffect, useState } from "react";

import PokemonPicker from "../components/PokemonPicker";
import { useAsync } from "../hooks/useAsync";
import { api, ApiError } from "../lib/api";
import type {
  MatchGameInput,
  MatchRead,
  MatchStage,
  MatchStatus,
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
  round_label: string;
  scheduled_at: string;
}

const EMPTY_CREATE: CreateFormState = {
  home_player_id: "",
  away_player_id: "",
  stage: "group",
  round_label: "",
  scheduled_at: "",
};

export default function AdminMatchesPage() {
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
    refetch,
  } = useAsync<MatchRead[]>(
    () => (seasonId ? api.matches.listBySeason(seasonId) : Promise.resolve([])),
    [seasonId],
  );
  const { data: roster, refetch: refetchRoster } = useAsync<SeasonEntryRead[]>(
    () => (seasonId ? api.seasons.roster.list(seasonId) : Promise.resolve([])),
    [seasonId],
  );

  const [createForm, setCreateForm] = useState<CreateFormState>(EMPTY_CREATE);
  const [createError, setCreateError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const rosterPlayers = (roster ?? []).map((entry) => entry.player);

  function poolFor(playerId: string): PokemonInput[] {
    const entry = (roster ?? []).find((e) => e.player.id === playerId);
    return (entry?.pokemon ?? []).map((p) => ({
      pokeapi_id: p.pokeapi_id,
      species_name: p.species_name,
    }));
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    if (createForm.home_player_id === createForm.away_player_id) {
      setCreateError("A match needs two different players.");
      return;
    }
    try {
      await api.matches.create({
        season_id: seasonId,
        home_player_id: createForm.home_player_id,
        away_player_id: createForm.away_player_id,
        stage: createForm.stage,
        round_label: createForm.round_label.trim() || null,
        scheduled_at: fromLocalInput(createForm.scheduled_at),
      });
      setCreateForm(EMPTY_CREATE);
      refetch();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to create match.");
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
    setRowError(null);
    try {
      await api.matches.delete(match.id);
      if (expandedId === match.id) setExpandedId(null);
      refetch();
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "Failed to delete match.");
    }
  }

  return (
    <div className="admin-matches-page">
      <h1>Manage Matches</h1>

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
                  setCreateForm({ ...createForm, stage: event.target.value as MatchStage })
                }
              >
                <option value="group">Group</option>
                <option value="playoffs">Playoffs</option>
              </select>
            </div>
            <div className="admin-form__row">
              <label htmlFor="create-round">Round label</label>
              <input
                id="create-round"
                value={createForm.round_label}
                onChange={(event) => setCreateForm({ ...createForm, round_label: event.target.value })}
                placeholder="e.g. Semifinal"
                maxLength={64}
              />
            </div>
            <div className="admin-form__row">
              <label htmlFor="create-scheduled">Scheduled for</label>
              <input
                id="create-scheduled"
                type="datetime-local"
                value={createForm.scheduled_at}
                onChange={(event) => setCreateForm({ ...createForm, scheduled_at: event.target.value })}
              />
            </div>
            {createError && (
              <p role="alert" className="admin-form__error">
                {createError}
              </p>
            )}
            <button type="submit" className="admin-form__submit">
              Create match
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
        {rowError && (
          <p role="alert" className="admin-page__error">
            {rowError}
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
                    </span>
                  </div>
                  <div className="admin-players-page__actions">
                    <button
                      type="button"
                      onClick={() => setExpandedId(expandedId === match.id ? null : match.id)}
                    >
                      {expandedId === match.id ? "Close" : "Edit"}
                    </button>
                    <button type="button" onClick={() => handleDelete(match)}>
                      Delete
                    </button>
                  </div>
                </div>

                {expandedId === match.id && (
                  <MatchEditor
                    match={match}
                    homePool={poolFor(match.home_player.id)}
                    awayPool={poolFor(match.away_player.id)}
                    onSaved={() => {
                      refetch();
                      refetchRoster();
                    }}
                  />
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
  homePool: PokemonInput[];
  awayPool: PokemonInput[];
  onSaved: () => void;
}

function MatchEditor({ match, homePool, awayPool, onSaved }: MatchEditorProps) {
  const [status, setStatus] = useState<MatchStatus>(match.status);
  const [winnerId, setWinnerId] = useState(match.winner_id ?? "");
  const [roundLabel, setRoundLabel] = useState(match.round_label ?? "");
  const [scheduledAt, setScheduledAt] = useState(toLocalInput(match.scheduled_at));
  const [completedAt, setCompletedAt] = useState(toLocalInput(match.completed_at));
  const [youtubeUrl, setYoutubeUrl] = useState(match.youtube_url ?? "");
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [detailsSaved, setDetailsSaved] = useState(false);

  const [games, setGames] = useState<MatchGameInput[]>(
    // A synthesized legacy game still edits like a real one; saving persists it.
    match.games.map((game) => ({
      game_number: game.game_number,
      winner_id: game.winner_id,
      replay_url: game.replay_url,
    })),
  );
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [gamesSaved, setGamesSaved] = useState(false);

  const [homeTeam, setHomeTeam] = useState<PokemonInput[]>(
    match.home_team.map((p) => ({ pokeapi_id: p.pokeapi_id, species_name: p.species_name })),
  );
  const [awayTeam, setAwayTeam] = useState<PokemonInput[]>(
    match.away_team.map((p) => ({ pokeapi_id: p.pokeapi_id, species_name: p.species_name })),
  );
  const [teamError, setTeamError] = useState<string | null>(null);
  const [teamSaved, setTeamSaved] = useState(false);

  async function saveDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDetailsError(null);
    setDetailsSaved(false);
    try {
      await api.matches.update(match.id, {
        status,
        winner_id: winnerId || null,
        round_label: roundLabel.trim() || null,
        scheduled_at: fromLocalInput(scheduledAt),
        completed_at: fromLocalInput(completedAt),
        youtube_url: youtubeUrl.trim() || null,
      });
      setDetailsSaved(true);
      onSaved();
    } catch (err) {
      setDetailsError(err instanceof ApiError ? err.message : "Failed to save match.");
    }
  }

  async function saveGames() {
    setGamesError(null);
    setGamesSaved(false);
    try {
      await api.matches.setGames(
        match.id,
        games.map((game, index) => ({
          game_number: index + 1,
          winner_id: game.winner_id || null,
          replay_url: game.replay_url?.trim() || null,
        })),
      );
      setGamesSaved(true);
      onSaved();
    } catch (err) {
      setGamesError(err instanceof ApiError ? err.message : "Failed to save games.");
    }
  }

  async function saveTeams() {
    setTeamError(null);
    setTeamSaved(false);
    try {
      await api.matches.setTeam(match.id, match.home_player.id, homeTeam);
      await api.matches.setTeam(match.id, match.away_player.id, awayTeam);
      setTeamSaved(true);
      onSaved();
    } catch (err) {
      setTeamError(err instanceof ApiError ? err.message : "Failed to save teams.");
    }
  }

  return (
    <div className="admin-match-card__body">
      <form className="admin-form" onSubmit={saveDetails}>
        <h3>Result &amp; schedule</h3>
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
        </div>
        <div className="admin-form__row">
          <label htmlFor={`winner-${match.id}`}>Winner</label>
          <select
            id={`winner-${match.id}`}
            value={winnerId}
            onChange={(event) => setWinnerId(event.target.value)}
          >
            <option value="">Undecided</option>
            <option value={match.home_player.id}>{match.home_player.username}</option>
            <option value={match.away_player.id}>{match.away_player.username}</option>
          </select>
        </div>
        <div className="admin-form__row">
          <label htmlFor={`round-${match.id}`}>Round label</label>
          <input
            id={`round-${match.id}`}
            value={roundLabel}
            onChange={(event) => setRoundLabel(event.target.value)}
            maxLength={64}
          />
        </div>
        <div className="admin-form__row">
          <label htmlFor={`sched-${match.id}`}>Scheduled for</label>
          <input
            id={`sched-${match.id}`}
            type="datetime-local"
            value={scheduledAt}
            onChange={(event) => setScheduledAt(event.target.value)}
          />
        </div>
        <div className="admin-form__row">
          <label htmlFor={`done-${match.id}`}>Completed at</label>
          <input
            id={`done-${match.id}`}
            type="datetime-local"
            value={completedAt}
            onChange={(event) => setCompletedAt(event.target.value)}
          />
        </div>
        <div className="admin-form__row">
          <label htmlFor={`yt-${match.id}`}>Video (YouTube) URL</label>
          <input
            id={`yt-${match.id}`}
            type="url"
            value={youtubeUrl}
            onChange={(event) => setYoutubeUrl(event.target.value)}
          />
        </div>
        {detailsError && (
          <p role="alert" className="admin-form__error">
            {detailsError}
          </p>
        )}
        {detailsSaved && <p className="admin-form__saved">Saved.</p>}
        <button type="submit" className="admin-form__submit">
          Save result
        </button>
      </form>

      <div className="admin-form">
        <h3>Games &amp; replays</h3>
        <p className="admin-form__hint">
          One row per game. A best-of-three has three rows, each with its own replay link.
        </p>
        {games.map((game, index) => (
          <div key={index} className="admin-game-row">
            <span className="admin-game-row__number">G{index + 1}</span>
            <select
              aria-label={`Game ${index + 1} winner`}
              value={game.winner_id ?? ""}
              onChange={(event) => {
                const next = [...games];
                next[index] = { ...game, winner_id: event.target.value || null };
                setGames(next);
              }}
            >
              <option value="">Undecided</option>
              <option value={match.home_player.id}>{match.home_player.username}</option>
              <option value={match.away_player.id}>{match.away_player.username}</option>
            </select>
            <input
              aria-label={`Game ${index + 1} replay URL`}
              type="url"
              placeholder="Replay URL"
              value={game.replay_url ?? ""}
              onChange={(event) => {
                const next = [...games];
                next[index] = { ...game, replay_url: event.target.value };
                setGames(next);
              }}
            />
            <button type="button" onClick={() => setGames(games.filter((_, i) => i !== index))}>
              Remove
            </button>
          </div>
        ))}
        <div className="admin-match-card__actions">
          <button
            type="button"
            onClick={() =>
              setGames([...games, { game_number: games.length + 1, winner_id: null, replay_url: "" }])
            }
            disabled={games.length >= 9}
          >
            Add game
          </button>
          <button type="button" className="admin-form__submit" onClick={saveGames}>
            Save games
          </button>
        </div>
        {gamesError && (
          <p role="alert" className="admin-form__error">
            {gamesError}
          </p>
        )}
        {gamesSaved && <p className="admin-form__saved">Saved.</p>}
      </div>

      <div className="admin-form">
        <h3>Teams brought</h3>
        <p className="admin-form__hint">
          Choose from each player&apos;s drafted pool for this season. Manage those pools on the
          season&apos;s roster page.
        </p>
        <PokemonPicker
          label={`${match.home_player.username} brought`}
          value={homeTeam}
          onChange={setHomeTeam}
          allowedFrom={homePool}
          max={6}
        />
        <PokemonPicker
          label={`${match.away_player.username} brought`}
          value={awayTeam}
          onChange={setAwayTeam}
          allowedFrom={awayPool}
          max={6}
        />
        {teamError && (
          <p role="alert" className="admin-form__error">
            {teamError}
          </p>
        )}
        {teamSaved && <p className="admin-form__saved">Saved.</p>}
        <button type="button" className="admin-form__submit" onClick={saveTeams}>
          Save teams
        </button>
      </div>
    </div>
  );
}
