import { Link } from "react-router-dom";

import { formatDateTime, matchTimestamp } from "../lib/format";
import { playerPath } from "../lib/routes";
import type { MatchRead, PlayerSummary } from "../types";
import ExternalLink from "./ExternalLink";
import MatchSeriesLinks from "./MatchSeriesLinks";
import PokemonTeam from "./PokemonTeam";

interface MatchRowProps {
  match: MatchRead;
  /**
   * Whose side to tell the story from. With a player id the row reads "vs
   * Opponent - Win 2-1"; without one it reads neutrally as "A vs B", which is
   * what the homepage fixtures want since neither player is "the" player
   * there.
   */
  perspectiveId?: string;
  /** Shown above the row - "Group A - Matchday 1", or a round name. */
  label?: string | null;
  /** Renders the "Featured" marker. Text, not colour alone. */
  featured?: boolean;
}

function scoreFor(match: MatchRead, isHome: boolean): [number | null, number | null] {
  const home = match.series.home_series_wins;
  const away = match.series.away_series_wins;
  return isHome ? [home, away] : [away, home];
}

function PlayerLink({ player }: { player: PlayerSummary }) {
  return <Link to={playerPath(player.slug)}>{player.username}</Link>;
}

/**
 * One match, as a list item.
 *
 * Extracted from the player profile so the player page, the Hall of Fame's
 * championship runs and the homepage fixtures all render a match the same way -
 * with the same replay links, teams, score and date - instead of three copies
 * drifting apart.
 */
export default function MatchRow({ match, perspectiveId, label, featured }: MatchRowProps) {
  const isHome = perspectiveId ? match.home_player.id === perspectiveId : true;
  const subject = isHome ? match.home_player : match.away_player;
  const other = isHome ? match.away_player : match.home_player;
  const [ownScore, otherScore] = scoreFor(match, isHome);

  const ownTeam = isHome ? match.home_team : match.away_team;
  const otherTeam = isHome ? match.away_team : match.home_team;

  const isCompleted = match.status === "completed";
  const won = isCompleted && match.winner_id === subject.id;

  return (
    <li className={featured ? "match-row match-row--featured" : "match-row"}>
      {(label || featured) && (
        <div className="match-row__meta">
          {featured && (
            // Text, not just the accent colour, so the distinction survives
            // greyscale, colour blindness and a screen reader.
            <span className="match-row__featured-flag">Featured</span>
          )}
          {label && <span className="match-row__label">{label}</span>}
        </div>
      )}
      <div className="match-row__main">
        <span className="match-row__opponent">
          {perspectiveId ? (
            <>
              vs <PlayerLink player={other} />
            </>
          ) : (
            <>
              <PlayerLink player={match.home_player} /> vs{" "}
              <PlayerLink player={match.away_player} />
            </>
          )}
        </span>
        {isCompleted && perspectiveId && (
          <span
            className={
              won ? "match-row__result match-row__result--win" : "match-row__result match-row__result--loss"
            }
          >
            {/* A match with no recorded score reads as a bare Win/Loss rather
                than a placeholder-filled "Win - -". */}
            {won ? "Win" : "Loss"}
            {ownScore !== null && otherScore !== null && ` · Series: ${ownScore}–${otherScore}`}
          </span>
        )}
        {isCompleted && !perspectiveId && ownScore !== null && otherScore !== null && (
          <span className="match-row__result">
            Series: {ownScore}–{otherScore}
          </span>
        )}
        {!isCompleted && (
          <span className="match-row__status">
            {match.status === "cancelled" ? "Cancelled" : "Scheduled"}
          </span>
        )}
        <span className="match-row__date">{formatDateTime(matchTimestamp(match))}</span>
      </div>
      {(ownTeam.length > 0 || otherTeam.length > 0) && (
        <div className="match-row__teams">
          <PokemonTeam pokemon={ownTeam} size={28} />
          <span className="match-row__teams-divider">vs</span>
          <PokemonTeam pokemon={otherTeam} size={28} />
        </div>
      )}
      <div className="match-row__links">
        <MatchSeriesLinks match={match} />
        {match.youtube_url && <ExternalLink href={match.youtube_url}>Video</ExternalLink>}
      </div>
    </li>
  );
}
