import { Link, useSearchParams } from "react-router-dom";

import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useSeasons } from "../hooks/useSeasons";
import { formatDateRange } from "../lib/format";
import { playerPath, seasonPath } from "../lib/routes";

export default function SeasonsPage() {
  useDocumentTitle("Seasons");
  const [searchParams] = useSearchParams();
  const q = searchParams.get("q") ?? "";
  const { data: seasons, isLoading, error } = useSeasons(q);

  return (
    <div className="seasons-page">
      <h1>Season Archive</h1>

      {q && (
        <p className="seasons-page__filter">
          Showing results for &quot;{q}&quot;. <Link to="/seasons">Clear search</Link>
        </p>
      )}

      {isLoading && <p role="status">Loading seasons...</p>}

      {error && (
        <p role="alert" className="seasons-page__error">
          {error}
        </p>
      )}

      {!isLoading && !error && seasons && seasons.length === 0 && (
        <p>{q ? `No seasons match "${q}".` : "No seasons have been recorded yet."}</p>
      )}

      {!isLoading && !error && seasons && seasons.length > 0 && (
        <ul className="seasons-list">
          {seasons.map((season) => (
            <li key={season.id} className="season-card">
              <Link to={seasonPath(season.slug)}>
                <h2>{season.name}</h2>
              </Link>
              <p className="season-card__dates">
                {formatDateRange(season.start_date, season.end_date)}
              </p>
              {season.champion && (
                <p className="season-card__champion">
                  Champion:{" "}
                  <Link to={playerPath(season.champion.slug)}>{season.champion.username}</Link>
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
