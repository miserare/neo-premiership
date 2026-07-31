import { Link, useParams } from "react-router-dom";

import ExternalLink from "../components/ExternalLink";
import MatchSeriesLinks from "../components/MatchSeriesLinks";
import PokemonTeam from "../components/PokemonTeam";
import { usePlayerDetail } from "../hooks/usePlayerDetail";
import type { MatchRead } from "../types";

function formatDateTime(iso: string | null): string {
  if (!iso) return "TBD";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function MatchRow({ match, perspectiveId }: { match: MatchRead; perspectiveId: string }) {
  const isHome = match.home_player.id === perspectiveId;
  const opponent = isHome ? match.away_player : match.home_player;
  const won = match.winner_id === perspectiveId;

  // A multi-game series is scored by games won; otherwise fall back to the
  // legacy per-match score fields.
  const isSeries = match.series.game_count > 1;
  const ownScore = isSeries
    ? isHome
      ? match.series.home_wins
      : match.series.away_wins
    : isHome
      ? match.home_score
      : match.away_score;
  const opponentScore = isSeries
    ? isHome
      ? match.series.away_wins
      : match.series.home_wins
    : isHome
      ? match.away_score
      : match.home_score;

  const ownTeam = isHome ? match.home_team : match.away_team;
  const opponentTeam = isHome ? match.away_team : match.home_team;

  return (
    <li className="match-row">
      <div className="match-row__main">
        <span className="match-row__opponent">
          vs <Link to={`/players/${opponent.id}`}>{opponent.username}</Link>
        </span>
        {match.status === "completed" && (
          <span
            className={won ? "match-row__result match-row__result--win" : "match-row__result match-row__result--loss"}
          >
            {/* A match with no recorded score reads as a bare Win/Loss rather
                than a placeholder-filled "Win - -". */}
            {won ? "Win" : "Loss"}
            {ownScore !== null && opponentScore !== null && ` ${ownScore}-${opponentScore}`}
          </span>
        )}
        <span className="match-row__date">
          {formatDateTime(match.status === "completed" ? match.completed_at : match.scheduled_at)}
        </span>
      </div>
      {(ownTeam.length > 0 || opponentTeam.length > 0) && (
        <div className="match-row__teams">
          <PokemonTeam pokemon={ownTeam} size={28} />
          <span className="match-row__teams-divider">vs</span>
          <PokemonTeam pokemon={opponentTeam} size={28} />
        </div>
      )}
      <div className="match-row__links">
        <MatchSeriesLinks match={match} />
        {match.youtube_url && <ExternalLink href={match.youtube_url}>Video</ExternalLink>}
      </div>
    </li>
  );
}

export default function PlayerDetailPage() {
  const { playerId } = useParams<{ playerId: string }>();
  const { data: player, isLoading, error } = usePlayerDetail(playerId ?? "");

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

  return (
    <div className="player-page">
      <div className="player-page__header">
        <h1>{player.username}</h1>
        <span className={player.is_active ? "badge badge--active" : "badge badge--inactive"}>
          {player.is_active ? "Active" : "Inactive"}
        </span>
      </div>

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

      {player.season_records.length > 0 && (
        <section aria-labelledby="season-history-heading">
          <h2 id="season-history-heading">Season History</h2>
          <ul className="player-page__seasons">
            {player.season_records.map((record) => (
              <li key={record.season_id} className="player-season-card">
                <div className="player-season-card__header">
                  <Link to={`/seasons/${record.season_id}`}>{record.season_name}</Link>
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
        {player.backlog.length > 0 ? (
          <ul className="match-list">
            {player.backlog.map((match) => (
              <MatchRow key={match.id} match={match} perspectiveId={player.id} />
            ))}
          </ul>
        ) : (
          <p>No upcoming matches.</p>
        )}
      </section>

      <section aria-labelledby="history-heading">
        <h2 id="history-heading">Match History</h2>
        {player.completed_matches.length > 0 ? (
          <ul className="match-list">
            {player.completed_matches.map((match) => (
              <MatchRow key={match.id} match={match} perspectiveId={player.id} />
            ))}
          </ul>
        ) : (
          <p>No completed matches yet.</p>
        )}
      </section>
    </div>
  );
}
