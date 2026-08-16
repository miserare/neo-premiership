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
  if (match.games.length === 0) {
    return null;
  }

  return (
    <span className="match-series-links">
      {match.games.map((game) => {
        const score =
          game.home_pokemon_score === null || game.away_pokemon_score === null
            ? "Score not recorded"
            : `${game.home_pokemon_score}–${game.away_pokemon_score}`;
        return (
          <span key={game.id ?? game.game_number} className="match-series-links__game">
            <strong>G{game.game_number}:</strong> {match.home_player.username} {score}{" "}
            {match.away_player.username}
            {game.replay_url && (
              <>
                {" — "}<ExternalLink href={game.replay_url}>Replay</ExternalLink>
              </>
            )}
          </span>
        );
      })}
    </span>
  );
}
