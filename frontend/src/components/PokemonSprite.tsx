import { useState } from "react";

// jsDelivr rather than raw.githubusercontent.com: raw is not a CDN, rate-limits
// per IP, and sends no useful cache headers, while a single season view pulls
// 24+ sprites. jsDelivr serves the same files with a 7-day cache and CORS.
//
// Keyed on PokeAPI's id, not the national dex number, so alternate forms resolve
// to their own artwork: Charizard is 6, Mega Charizard X is 10034.
const SPRITE_BASE = "https://cdn.jsdelivr.net/gh/PokeAPI/sprites@master/sprites/pokemon";

interface PokemonSpriteProps {
  pokeapiId: number;
  speciesName: string;
  size?: number;
}

/** A single Pokémon sprite with its name as the accessible label.
 * The sprite is decorative-but-identifying, so alt text carries the species. */
export default function PokemonSprite({ pokeapiId, speciesName, size = 56 }: PokemonSpriteProps) {
  const [failed, setFailed] = useState(false);

  // A handful of PokeAPI ids have no sprite in the repo, and a CDN can always
  // hiccup. Fall back to a readable initial rather than a broken-image icon.
  if (failed) {
    return (
      <span
        className="pokemon-sprite pokemon-sprite--fallback"
        style={{ width: size, height: size }}
        title={speciesName}
        role="img"
        aria-label={speciesName}
      >
        {speciesName.slice(0, 1).toUpperCase()}
      </span>
    );
  }

  return (
    <img
      className="pokemon-sprite"
      src={`${SPRITE_BASE}/${pokeapiId}.png`}
      alt={speciesName}
      title={speciesName}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
