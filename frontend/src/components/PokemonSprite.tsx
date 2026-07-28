// jsDelivr rather than raw.githubusercontent.com: raw is not a CDN, rate-limits
// per IP, and sends no useful cache headers, while a single season view pulls
// 24+ sprites. jsDelivr serves the same files with a 7-day cache and CORS.
const SPRITE_BASE = "https://cdn.jsdelivr.net/gh/PokeAPI/sprites@master/sprites/pokemon";

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
