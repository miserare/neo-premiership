import { Link } from "react-router-dom";

import MatchList from "../components/MatchList";
import PlainText from "../components/PlainText";
import { useAsync } from "../hooks/useAsync";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { api } from "../lib/api";
import { formatDateRange } from "../lib/format";
import { playerPath, seasonStandingsPath } from "../lib/routes";
import type { HallOfFameResponse } from "../types";

/**
 * Every season the league has crowned a champion, newest first.
 *
 * The championship run comes from the API already in tournament order, and is
 * rendered exactly as it arrives - the client does no sorting of its own. Each
 * run reuses the same MatchRow the player pages and homepage fixtures use, so
 * replays, the stream link and both teams look the same everywhere.
 */
export default function HallOfFamePage() {
  useDocumentTitle("Hall of Fame");
  const { data, isLoading, error } = useAsync<HallOfFameResponse>(() => api.hallOfFame.get(), []);

  if (isLoading) {
    return <p role="status">Loading the Hall of Fame...</p>;
  }

  if (error) {
    return (
      <p role="alert" className="hall-of-fame__error">
        {error}
      </p>
    );
  }

  const entries = data?.entries ?? [];

  return (
    <div className="hall-of-fame">
      <h1>Hall of Fame</h1>
      <p className="hall-of-fame__intro">
        Every champion the Pokémon Premiership has crowned, with the playoff run that got them
        there.
      </p>

      {entries.length === 0 ? (
        <p className="hall-of-fame__empty">
          No champion has been recorded yet. A season appears here once its winner is set.
        </p>
      ) : (
        <ul className="hall-of-fame__list">
          {entries.map((entry) => (
            <li key={entry.season_id} className="hall-of-fame-entry">
              <div className="hall-of-fame-entry__header">
                <div>
                  <h2 className="hall-of-fame-entry__champion">
                    <span className="hall-of-fame-entry__star" aria-hidden="true">
                      ★
                    </span>
                    <Link to={playerPath(entry.champion.slug)}>{entry.champion.username}</Link>
                  </h2>
                  <p className="hall-of-fame-entry__title">
                    {entry.championship_count > 1
                      ? `${entry.championship_count}× Champion`
                      : "Champion"}
                    {" · "}
                    <Link to={seasonStandingsPath(entry.season_slug)}>{entry.season_name}</Link>
                  </p>
                </div>
                <p className="hall-of-fame-entry__dates">
                  {formatDateRange(entry.start_date, entry.end_date)}
                </p>
              </div>

              {entry.description ? (
                <>
                  <PlainText className="hall-of-fame-entry__description">
                    {entry.description}
                  </PlainText>
                  {entry.description_is_fallback && (
                    <p className="hall-of-fame-entry__fallback-note">
                      From the season overview - no Hall of Fame write-up has been added yet.
                    </p>
                  )}
                </>
              ) : (
                <p className="hall-of-fame-entry__fallback-note">
                  No write-up has been added for this championship yet.
                </p>
              )}

              <section aria-label={`${entry.champion.username}'s championship run`}>
                <h3>Championship run</h3>
                <MatchList
                  matches={entry.championship_run}
                  perspectiveId={entry.champion.id}
                  labelFor={(match) => match.round_label}
                  empty="No playoff matches were recorded for this run."
                />
              </section>

              <p className="hall-of-fame-entry__links">
                <Link to={seasonStandingsPath(entry.season_slug)}>
                  {entry.season_name} standings
                </Link>
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
