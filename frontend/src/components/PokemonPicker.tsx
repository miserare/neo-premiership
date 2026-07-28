import { useEffect, useMemo, useState } from "react";

import type { PokemonInput } from "../types";
import PokemonSprite from "./PokemonSprite";

interface Species {
  id: number;
  name: string;
}

/** The full species list is ~30KB and only ever needed behind the admin token,
 * so it is code-split out of the bundle public visitors download. */
let speciesPromise: Promise<Species[]> | null = null;
function loadSpecies(): Promise<Species[]> {
  if (!speciesPromise) {
    speciesPromise = import("../data/pokemon.json").then((mod) => mod.default as Species[]);
  }
  return speciesPromise;
}

interface PokemonPickerProps {
  value: PokemonInput[];
  onChange: (next: PokemonInput[]) => void;
  /** Restrict choices to a player's drafted pool (used for match teams). */
  allowedFrom?: PokemonInput[];
  max?: number;
  label: string;
}

export default function PokemonPicker({
  value,
  onChange,
  allowedFrom,
  max = 12,
  label,
}: PokemonPickerProps) {
  const [species, setSpecies] = useState<Species[]>([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    loadSpecies().then((list) => {
      if (!cancelled) setSpecies(list);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const options: Species[] = useMemo(() => {
    if (allowedFrom) {
      return allowedFrom.map((p) => ({ id: p.pokeapi_id, name: p.species_name }));
    }
    return species;
  }, [allowedFrom, species]);

  const chosenIds = new Set(value.map((p) => p.pokeapi_id));
  const matches = useMemo(() => {
    const pool = options.filter((s) => !chosenIds.has(s.id));
    // Every whitespace-separated word must appear somewhere in the name, in any
    // order. With forms in the catalogue a name looks like "Charizard (Mega X)",
    // so a plain substring match would miss "mega charizard".
    const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (terms.length === 0) return allowedFrom ? pool : pool.slice(0, 0);
    return pool
      .filter((s) => {
        const name = s.name.toLowerCase();
        return terms.every((term) => name.includes(term));
      })
      .slice(0, 12);
    // chosenIds is derived from `value`, which is already a dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options, query, value, allowedFrom]);

  function add(entry: Species) {
    if (value.length >= max) return;
    onChange([...value, { pokeapi_id: entry.id, species_name: entry.name }]);
    setQuery("");
  }

  function removeAt(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }

  return (
    <div className="pokemon-picker">
      <span className="pokemon-picker__label">
        {label} ({value.length}/{max})
      </span>

      {value.length > 0 && (
        <ul className="pokemon-picker__chosen">
          {value.map((entry, index) => (
            <li key={`${entry.pokeapi_id}-${index}`} className="pokemon-picker__chip">
              <PokemonSprite pokeapiId={entry.pokeapi_id} speciesName={entry.species_name} size={32} />
              <span>{entry.species_name}</span>
              <button
                type="button"
                aria-label={`Remove ${entry.species_name}`}
                onClick={() => removeAt(index)}
              >
                &times;
              </button>
            </li>
          ))}
        </ul>
      )}

      {value.length < max && (
        <>
          <input
            type="search"
            className="pokemon-picker__search"
            placeholder={
              allowedFrom
                ? "Filter this player's pool..."
                : "Find a Pokémon - try \"mega charizard\" or \"galarian\""
            }
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label={`Search Pokémon to add to ${label}`}
          />
          {matches.length > 0 && (
            <ul className="pokemon-picker__results">
              {matches.map((entry) => (
                <li key={entry.id}>
                  <button type="button" onClick={() => add(entry)}>
                    <PokemonSprite pokeapiId={entry.id} speciesName={entry.name} size={32} />
                    <span>{entry.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {allowedFrom && allowedFrom.length === 0 && (
            <p className="pokemon-picker__hint">
              This player has no drafted Pokémon for this season yet.
            </p>
          )}
        </>
      )}
    </div>
  );
}
