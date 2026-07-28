import { Link, useParams } from "react-router-dom";

import ExternalLink from "../components/ExternalLink";
import MatchSeriesLinks from "../components/MatchSeriesLinks";
import PokemonTeam from "../components/PokemonTeam";
import { useSeasonDetail } from "../hooks/useSeasonDetail";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function SeasonDetailPage() {
  const { seasonId } = useParams<{ seasonId: string }>();
  const { data: season, isLoading, error } = useSeasonDetail(seasonId ?? "");

  if (isLoading) {
    return <p role="status">Loading season...</p>;
  }

  if (error) {
    return (
      <p role="alert" className="season-page__error">
        {error}
      </p>
    );
  }

  if (!season) {
    return null;
  }

  return (
    <div className="season-page">
      <div className="season-page__header">
        <h1>{season.name}</h1>
        <span className={season.is_active ? "badge badge--active" : "badge badge--inactive"}>
          {season.is_active ? "Active" : "Completed"}
        </span>
      </div>
      <p className="season-page__dates">
        {formatDate(season.start_date)} - {season.end_date ? formatDate(season.end_date) : "present"}
      </p>

      {season.sheet_url && (
        <p>
          <ExternalLink href={season.sheet_url}>Open Season Sheet</ExternalLink>
        </p>
      )}

      {season.overview && <p className="season-page__overview">{season.overview}</p>}

      {season.champion && (
        <p className="season-page__champion">
          Champion: <Link to={`/players/${season.champion.id}`}>{season.champion.username}</Link>
        </p>
      )}

      <section aria-labelledby="roster-heading">
        <h2 id="roster-heading">Roster</h2>
        {season.roster.length > 0 ? (
          <ul className="season-page__roster-cards">
            {season.roster.map((entry) => (
              <li key={entry.player.id} className="season-roster-card">
                <div className="season-roster-card__header">
                  <Link to={`/players/${entry.player.id}`}>{entry.player.username}</Link>
                  {entry.group_label && (
                    <span className="season-page__group-label">({entry.group_label})</span>
                  )}
                </div>
                <PokemonTeam pokemon={entry.pokemon} size={40} />
              </li>
            ))}
          </ul>
        ) : (
          <p>No roster recorded yet.</p>
        )}
      </section>

      <section aria-labelledby="standings-heading">
        <h2 id="standings-heading">Group Standings</h2>
        {season.standings.length > 0 ? (
          season.standings.map((group) => (
            <div key={group.group_label ?? "ungrouped"} className="standings-group">
              {group.group_label && <h3>{group.group_label}</h3>}
              <table className="standings-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Wins</th>
                    <th>Losses</th>
                  </tr>
                </thead>
                <tbody>
                  {group.standings.map((entry) => (
                    <tr key={entry.player.id}>
                      <td>
                        <Link to={`/players/${entry.player.id}`}>{entry.player.username}</Link>
                      </td>
                      <td>{entry.wins}</td>
                      <td>{entry.losses}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))
        ) : (
          <p>No standings available yet.</p>
        )}
      </section>

      <section aria-labelledby="bracket-heading">
        <h2 id="bracket-heading">Playoff Bracket</h2>
        {season.bracket.length > 0 ? (
          <div className="bracket">
            {season.bracket.map((round) => (
              <div key={`${round.round_order}-${round.round_label}`} className="bracket-round">
                <h3>{round.round_label}</h3>
                <ul className="bracket-round__matches">
                  {round.matches.map((match) => (
                    <li key={match.id} className="bracket-match">
                      <div
                        className={
                          match.winner_id === match.home_player.id
                            ? "bracket-match__competitor bracket-match__competitor--winner"
                            : "bracket-match__competitor"
                        }
                      >
                        <Link to={`/players/${match.home_player.id}`}>{match.home_player.username}</Link>
                        <span>
                          {match.series.game_count > 1 ? match.series.home_wins : (match.home_score ?? "-")}
                        </span>
                      </div>
                      <div
                        className={
                          match.winner_id === match.away_player.id
                            ? "bracket-match__competitor bracket-match__competitor--winner"
                            : "bracket-match__competitor"
                        }
                      >
                        <Link to={`/players/${match.away_player.id}`}>{match.away_player.username}</Link>
                        <span>
                          {match.series.game_count > 1 ? match.series.away_wins : (match.away_score ?? "-")}
                        </span>
                      </div>
                      {(match.home_team.length > 0 || match.away_team.length > 0) && (
                        <div className="bracket-match__teams">
                          <PokemonTeam pokemon={match.home_team} size={24} />
                          <PokemonTeam pokemon={match.away_team} size={24} />
                        </div>
                      )}
                      <div className="bracket-match__links">
                        <MatchSeriesLinks match={match} />
                        {match.youtube_url && <ExternalLink href={match.youtube_url}>Video</ExternalLink>}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : (
          <p>The playoff bracket hasn&apos;t been set yet.</p>
        )}
      </section>

      <section aria-labelledby="streams-heading">
        <h2 id="streams-heading">Streams</h2>
        {season.streams.length > 0 ? (
          <ul className="season-page__streams">
            {season.streams.map((stream) => (
              <li key={stream.url}>
                <ExternalLink href={stream.url}>{stream.label}</ExternalLink>
              </li>
            ))}
          </ul>
        ) : (
          <p>No streams linked yet.</p>
        )}
      </section>
    </div>
  );
}
