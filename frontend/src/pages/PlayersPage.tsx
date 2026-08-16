import { Link, useSearchParams } from "react-router-dom";

import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { usePlayers } from "../hooks/usePlayers";
import { formatDate } from "../lib/format";
import { playerPath } from "../lib/routes";

export default function PlayersPage() {
  useDocumentTitle("Players");
  const [searchParams] = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const { data: players, isLoading, error } = usePlayers(q);

  return (
    <div className="players-page">
      <div className="players-page__header">
        <h1>League Players</h1>
      </div>

      {q && (
        <p className="players-page__filter">
          Showing results for &quot;{q}&quot;. <Link to="/players">Clear search</Link>
        </p>
      )}

      {isLoading && <p role="status">Loading players...</p>}

      {error && (
        <p role="alert" className="players-page__error">
          {error}
        </p>
      )}

      {!isLoading && !error && players && players.length === 0 && (
        <p>{q ? `No players match "${q}".` : "No players have joined the league yet."}</p>
      )}

      {!isLoading && !error && players && players.length > 0 && (
        <table className="players-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Elo</th>
              <th>Joined</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {players.map((player) => (
              <tr key={player.id}>
                <td>
                  <Link to={playerPath(player.slug)}>{player.username}</Link>
                </td>
                <td>{player.elo_rating}</td>
                <td>{formatDate(player.join_date)}</td>
                <td>
                  <span className={player.is_active ? "badge badge--active" : "badge badge--inactive"}>
                    {player.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
