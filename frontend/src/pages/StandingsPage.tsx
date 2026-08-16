import { Link, Navigate, useParams } from "react-router-dom";

import ExternalLink from "../components/ExternalLink";
import SeasonRoster from "../components/SeasonRoster";
import StandingsGroups from "../components/StandingsGroups";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useAsync } from "../hooks/useAsync";
import { api } from "../lib/api";
import { formatDateRange } from "../lib/format";
import { seasonStandingsPath } from "../lib/routes";
import type { SeasonDetail } from "../types";

/** Does this reference look like a UUID rather than a slug? */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Group standings for one season.
 *
 * Serves three routes: `/standings` (whichever season the league is in),
 * `/seasons/:slug/standings`, and the legacy `/seasons/:uuid/standings`, which
 * redirects to the slug form.
 *
 * Group Standings are rendered above the roster - the table is what a visitor
 * comes here for, and the roster is context for it.
 */
export default function StandingsPage() {
  const { seasonRef } = useParams<{ seasonRef?: string }>();

  const {
    data: season,
    isLoading,
    error,
  } = useAsync<SeasonDetail>(
    () => (seasonRef ? api.seasons.get(seasonRef) : api.seasons.current()),
    [seasonRef],
  );

  // null while loading, so the tab does not flash the bare site name and then
  // replace it a moment later.
  useDocumentTitle(season ? `${season.name} Standings` : isLoading ? null : "Standings");

  if (isLoading) {
    return <p role="status">Loading standings...</p>;
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

  // A legacy UUID URL resolves, then redirects to the canonical slug.
  if (seasonRef && UUID.test(seasonRef)) {
    return <Navigate to={seasonStandingsPath(season.slug)} replace />;
  }

  const isCurrentRoute = !seasonRef;

  return (
    <div className="season-page standings-page">
      <div className="season-page__header">
        <h1>{season.name} Standings</h1>
        <span className={season.is_active ? "badge badge--active" : "badge badge--inactive"}>
          {season.is_active ? "In season" : "Completed"}
        </span>
      </div>
      <p className="season-page__dates">{formatDateRange(season.start_date, season.end_date)}</p>

      {/* Between seasons /standings shows the most recently started season.
          Saying so is the difference between an archive and a wrong table. */}
      {isCurrentRoute && !season.is_active && (
        <p className="standings-page__context">
          The league is between seasons. These are the final standings of {season.name}, the most
          recently started season.
        </p>
      )}

      {season.sheet_url && (
        <p>
          <ExternalLink href={season.sheet_url}>Open Season Sheet</ExternalLink>
        </p>
      )}

      <section aria-labelledby="standings-heading">
        <h2 id="standings-heading">Group Standings</h2>
        <StandingsGroups groups={season.standings} />
      </section>

      <section aria-labelledby="roster-heading">
        <h2 id="roster-heading">Roster</h2>
        <SeasonRoster roster={season.roster} />
      </section>

      <p className="standings-page__more">
        <Link to={`/seasons/${season.slug}`}>Full {season.name} page, including the bracket</Link>
      </p>
    </div>
  );
}
