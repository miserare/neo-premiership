import { Link, Navigate, useParams } from "react-router-dom";

import ExternalLink from "../components/ExternalLink";
import MatchSeriesLinks from "../components/MatchSeriesLinks";
import PlainText from "../components/PlainText";
import PokemonTeam from "../components/PokemonTeam";
import SeasonRoster from "../components/SeasonRoster";
import StandingsGroups from "../components/StandingsGroups";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useSeasonDetail } from "../hooks/useSeasonDetail";
import { formatDateRange } from "../lib/format";
import { playerPath, seasonPath, seasonStandingsPath } from "../lib/routes";

/** Does this reference look like a UUID rather than a slug? */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function SeasonDetailPage() {
  const { seasonRef } = useParams<{ seasonRef: string }>();
  const { data: season, isLoading, error } = useSeasonDetail(seasonRef ?? "");

  useDocumentTitle(season?.name ?? null);

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

  // A legacy UUID link resolves, then redirects to the canonical slug.
  if (seasonRef && UUID.test(seasonRef)) {
    return <Navigate to={seasonPath(season.slug)} replace />;
  }

  return (
    <div className="season-page">
      <div className="season-page__header">
        <h1>{season.name}</h1>
        <span className={season.is_active ? "badge badge--active" : "badge badge--inactive"}>
          {season.is_active ? "Active" : "Completed"}
        </span>
      </div>
      <p className="season-page__dates">{formatDateRange(season.start_date, season.end_date)}</p>

      {season.sheet_url && (
        <p>
          <ExternalLink href={season.sheet_url}>Open Season Sheet</ExternalLink>
        </p>
      )}

      {season.overview && (
        <PlainText className="season-page__overview">{season.overview}</PlainText>
      )}

      {season.champion && (
        <p className="season-page__champion">
          Champion: <Link to={playerPath(season.champion.slug)}>{season.champion.username}</Link>
        </p>
      )}

      <section aria-labelledby="standings-heading">
        <h2 id="standings-heading">Group Standings</h2>
        <StandingsGroups groups={season.standings} />
        <p className="season-page__standings-link">
          <Link to={seasonStandingsPath(season.slug)}>Standings page for this season</Link>
        </p>
      </section>

      <section aria-labelledby="roster-heading">
        <h2 id="roster-heading">Roster</h2>
        <SeasonRoster roster={season.roster} />
      </section>

      <section aria-labelledby="bracket-heading">
        <h2 id="bracket-heading">Playoff Bracket</h2>
        {season.bracket.length > 0 ? (
          // Rendered in exactly the order the API returned. No sorting, no
          // label-derived classes, no layout that depends on how many rounds
          // there are - ten columns lay out the same way four do, and scroll.
          <div className="bracket" role="region" aria-labelledby="bracket-heading" tabIndex={0}>
            {season.bracket.map((round) => (
              <section key={round.id} className="bracket-round" aria-labelledby={`round-${round.id}`}>
                <h3 id={`round-${round.id}`}>{round.label}</h3>
                <ul className="bracket-round__matches">
                  {round.matches.length === 0 && (
                    <li className="bracket-round__empty">Not drawn yet</li>
                  )}
                  {round.matches.map((match) => (
                    <li key={match.id} className="bracket-match">
                      <span className="visually-hidden">Series score</span>
                      <div
                        className={
                          match.winner_id === match.home_player.id
                            ? "bracket-match__competitor bracket-match__competitor--winner"
                            : "bracket-match__competitor"
                        }
                      >
                        <Link to={playerPath(match.home_player.slug)}>{match.home_player.username}</Link>
                        <span>
                          {match.series.home_series_wins}
                        </span>
                      </div>
                      <div
                        className={
                          match.winner_id === match.away_player.id
                            ? "bracket-match__competitor bracket-match__competitor--winner"
                            : "bracket-match__competitor"
                        }
                      >
                        <Link to={playerPath(match.away_player.slug)}>{match.away_player.username}</Link>
                        <span>
                          {match.series.away_series_wins}
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
              </section>
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
