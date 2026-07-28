import type { MatchRead } from "../types";
import ExternalLink from "./ExternalLink";

interface MatchSeriesLinksProps {
  match: MatchRead;
}

/** Replay links for a match.
 *
 * A one-game match gets a single "Replay" link, as before. A multi-game series
 * gets one link per game (G1/G2/G3), so a best-of-three no longer has to hide
 * two of its three replays behind a single field.
 */
export default function MatchSeriesLinks({ match }: MatchSeriesLinksProps) {
  const playable = match.games.filter((game) => game.replay_url);

  if (playable.length === 0) {
    return null;
  }

  if (match.games.length === 1) {
    return <ExternalLink href={playable[0].replay_url as string}>Replay</ExternalLink>;
  }

  return (
    <span className="match-series-links">
      {playable.map((game) => (
        <ExternalLink key={game.game_number} href={game.replay_url as string}>
          G{game.game_number}
        </ExternalLink>
      ))}
    </span>
  );
}

/** "2-1" for a decided multi-game series, otherwise null - a Bo1 reads better
 * as a plain win/loss than as "1-0". */
export function formatSeriesScore(match: MatchRead): string | null {
  if (match.series.game_count < 2) {
    return null;
  }
  return `${match.series.home_wins}-${match.series.away_wins}`;
}
