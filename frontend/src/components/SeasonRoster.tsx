import { Link } from "react-router-dom";

import { playerPath } from "../lib/routes";
import type { RosterEntry } from "../types";
import PokemonTeam from "./PokemonTeam";

interface SeasonRosterProps {
  roster: RosterEntry[];
  empty?: string;
}

/**
 * A season's drafted rosters.
 *
 * Ownership is historical: `former_pokemon` are the ones a player held and
 * later released or traded away that season, kept behind a disclosure rather
 * than dropped, so the roster still shows what actually happened.
 */
export default function SeasonRoster({
  roster,
  empty = "No roster recorded yet.",
}: SeasonRosterProps) {
  if (roster.length === 0) {
    return <p>{empty}</p>;
  }

  return (
    <ul className="season-page__roster-cards">
      {roster.map((entry) => (
        <li key={entry.player.id} className="season-roster-card">
          <div className="season-roster-card__header">
            <Link to={playerPath(entry.player.slug)}>{entry.player.username}</Link>
            {entry.group_label && (
              <span className="season-page__group-label">({entry.group_label})</span>
            )}
          </div>
          <PokemonTeam pokemon={entry.pokemon} size={40} emptyLabel="No Pokémon currently rostered." />
          {entry.former_pokemon.length > 0 && (
            <details className="roster-history">
              <summary>Previously rostered ({entry.former_pokemon.length})</summary>
              <PokemonTeam pokemon={entry.former_pokemon} size={32} />
            </details>
          )}
        </li>
      ))}
    </ul>
  );
}
