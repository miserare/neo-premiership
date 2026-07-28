const SPRITE_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon";

interface PokemonSpriteProps {
  pokeapiId: number;
  speciesName: string;
  size?: number;
}

/** A single Pokémon sprite with its name as the accessible label.
 * The sprite is decorative-but-identifying, so alt text carries the species. */
export default function PokemonSprite({ pokeapiId, speciesName, size = 56 }: PokemonSpriteProps) {
  return (
    <img
      className="pokemon-sprite"
      src={`${SPRITE_BASE}/${pokeapiId}.png`}
      alt={speciesName}
      title={speciesName}
      width={size}
      height={size}
      loading="lazy"
    />
  );
}
