import { Link, useSearchParams } from "react-router-dom";

import { useSeasons } from "../hooks/useSeasons";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function SeasonsPage() {
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
              <Link to={`/seasons/${season.id}`}>
                <h2>{season.name}</h2>
              </Link>
              <p className="season-card__dates">
                {formatDate(season.start_date)} - {season.end_date ? formatDate(season.end_date) : "present"}
              </p>
              {season.champion && <p className="season-card__champion">Champion: {season.champion.username}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
