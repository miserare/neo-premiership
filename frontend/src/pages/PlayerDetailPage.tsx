import { Link, useParams } from "react-router-dom";

import ChampionBadge from "../components/ChampionBadge";
import Disclosure from "../components/Disclosure";
import MatchList from "../components/MatchList";
import PlainText from "../components/PlainText";
import PokemonTeam from "../components/PokemonTeam";
import SiteCreatorBadge from "../components/SiteCreatorBadge";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { usePlayerDetail } from "../hooks/usePlayerDetail";
import { formatDateTime } from "../lib/format";
import { playerPath, seasonPath } from "../lib/routes";
import type { EloRatingHistoryEntry } from "../types";

/** How many of each list to show before the disclosure. */
const PREVIEW_COUNT = 5;

function EloTable({ entries }: { entries: EloRatingHistoryEntry[] }) {
  return (
    <div className="table-scroll">
      <table className="players-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Game</th>
            <th>Opponent</th>
            <th>Result</th>
            <th>Before</th>
            <th>Change</th>
            <th>After</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.match_game_id}>
              <td>{formatDateTime(entry.occurred_at)}</td>
              <td>
                G{entry.game_number}
                {entry.player_pokemon_score !== null && entry.opponent_pokemon_score !== null
                  ? ` · ${entry.player_pokemon_score}–${entry.opponent_pokemon_score}`
                  : " · Score not recorded"}
              </td>
              <td>
                <Link to={playerPath(entry.opponent_slug)}>{entry.opponent_username}</Link>
              </td>
              <td>{entry.result === 1 ? "Win" : "Loss"}</td>
              <td>{entry.rating_before}</td>
              <td>{entry.rating_change > 0 ? `+${entry.rating_change}` : entry.rating_change}</td>
              <td>{entry.rating_after}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PlayerDetailPage() {
  const { playerSlug } = useParams<{ playerSlug: string }>();
  const { data: player, isLoading, error } = usePlayerDetail(playerSlug ?? "");

  // null while loading: the title is not known yet, and guessing would flash
  // the site name and then replace it.
  useDocumentTitle(player?.username ?? null);

  if (isLoading) {
    return <p role="status">Loading player...</p>;
  }

  if (error) {
    return (
      <p role="alert" className="player-page__error">
        {error}
      </p>
    );
  }

  if (!player) {
    return null;
  }

  // Already newest-first from the API, so the recent list is simply its head -
  // both views read the same array and neither issues a second request.
  const completed = player.completed_matches;
  const recent = completed.slice(0, PREVIEW_COUNT);
  const eloHistory = player.elo_history;

  return (
    <div className="player-page">
      <div className="player-page__header">
        <h1>{player.username}</h1>
        <span className={player.is_active ? "badge badge--active" : "badge badge--inactive"}>
          {player.is_active ? "Active" : "Inactive"}
        </span>
      </div>

      <ChampionBadge championships={player.championships} />
      {player.is_site_creator && <SiteCreatorBadge />}

      {player.biography && (
        <PlainText className="player-page__biography">{player.biography}</PlainText>
      )}

      <dl className="player-page__stats">
        <div>
          <dt>Elo Rating</dt>
          <dd>{player.elo_rating}</dd>
        </div>
        <div>
          <dt>Most Recent Season</dt>
          <dd>
            {player.most_recent_season_record
              ? `${player.most_recent_season_record.season_name}: ${player.most_recent_season_record.wins}-${player.most_recent_season_record.losses}`
              : "No season played yet"}
          </dd>
        </div>
        <div>
          <dt>Historical Record</dt>
          <dd>
            {player.historical_record.wins}-{player.historical_record.losses}
          </dd>
        </div>
      </dl>

      <section aria-labelledby="recent-heading">
        <h2 id="recent-heading">Recent Matches</h2>
        <MatchList matches={recent} perspectiveId={player.id} empty="No completed matches yet." />
      </section>

      <section aria-labelledby="elo-history-heading">
        <h2 id="elo-history-heading">Elo History</h2>
        {eloHistory.length === 0 ? (
          <p>No Elo-rated games yet.</p>
        ) : eloHistory.length <= PREVIEW_COUNT ? (
          // Nothing is hidden, so there is nothing to expand - a control here
          // would only ever be a no-op.
          <EloTable entries={eloHistory} />
        ) : (
          <Disclosure
            showLabel={`Show full Elo history (${eloHistory.length} games)`}
            hideLabel="Show recent five"
          >
            {(expanded) => (
              <EloTable entries={expanded ? eloHistory : eloHistory.slice(0, PREVIEW_COUNT)} />
            )}
          </Disclosure>
        )}
      </section>

      {player.season_records.length > 0 && (
        <section aria-labelledby="season-history-heading">
          <h2 id="season-history-heading">Season History</h2>
          <ul className="player-page__seasons">
            {player.season_records.map((record) => (
              <li key={record.season_id} className="player-season-card">
                <div className="player-season-card__header">
                  <Link to={seasonPath(record.season_slug)}>{record.season_name}</Link>
                  <span className="player-season-card__record">
                    {record.wins}-{record.losses}
                  </span>
                </div>
                <PokemonTeam
                  pokemon={record.pokemon}
                  emptyLabel="No currently rostered Pokémon recorded for this season."
                />
                {record.former_pokemon.length > 0 && (
                  <details className="roster-history">
                    <summary>Previously rostered ({record.former_pokemon.length})</summary>
                    <PokemonTeam pokemon={record.former_pokemon} size={36} />
                  </details>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="backlog-heading">
        <h2 id="backlog-heading">Upcoming Matches</h2>
        <MatchList matches={player.backlog} perspectiveId={player.id} empty="No upcoming matches." />
      </section>

      <section aria-labelledby="history-heading">
        <h2 id="history-heading">Match History</h2>
        {completed.length <= PREVIEW_COUNT ? (
          // Everything is already in Recent Matches above; repeating it would
          // just be the same list twice.
          <p>
            {completed.length === 0
              ? "No completed matches yet."
              : "Every completed match is shown under Recent Matches above."}
          </p>
        ) : (
          <Disclosure
            showLabel={`View all matches (${completed.length})`}
            hideLabel="Show fewer matches"
          >
            {(expanded) =>
              expanded ? (
                <MatchList
                  matches={completed}
                  perspectiveId={player.id}
                  empty="No completed matches yet."
                />
              ) : null
            }
          </Disclosure>
        )}
      </section>
    </div>
  );
}
