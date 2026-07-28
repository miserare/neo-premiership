import PokemonSprite from "./PokemonSprite";

interface TeamMember {
  pokeapi_id: number;
  species_name: string;
}

interface PokemonTeamProps {
  pokemon: TeamMember[];
  size?: number;
  emptyLabel?: string;
}

/** Read-only row of sprites, used for both season draft pools and the teams
 * brought to a match. */
export default function PokemonTeam({ pokemon, size, emptyLabel }: PokemonTeamProps) {
  if (pokemon.length === 0) {
    return emptyLabel ? <p className="pokemon-team__empty">{emptyLabel}</p> : null;
  }

  return (
    <ul className="pokemon-team">
      {pokemon.map((entry, index) => (
        <li key={`${entry.pokeapi_id}-${index}`} className="pokemon-team__item">
          <PokemonSprite pokeapiId={entry.pokeapi_id} speciesName={entry.species_name} size={size} />
          <span className="pokemon-team__name">{entry.species_name}</span>
        </li>
      ))}
    </ul>
  );
}
