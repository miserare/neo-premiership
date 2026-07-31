"""Regenerate frontend/src/data/pokemon.json, the species list behind the admin
draft picker.

    curl -s "https://pokeapi.co/api/v2/pokemon?limit=100000" -o /tmp/all_pokemon.json
    curl -s "https://pokeapi.co/api/v2/pokemon-species?limit=100000" -o /tmp/species.json
    python backend/seeds/generate_pokemon_catalogue.py /tmp

Entries are keyed on PokeAPI's id rather than the national dex number, so
alternate forms get their own artwork - Charizard is 6, Mega Charizard X 10034.

Names are split against the *canonical species* list rather than on the first
hyphen, for two reasons: PokeAPI's default name for some species is itself
qualified (386 is `deoxys-normal`, not `deoxys`), and plenty of species names
contain hyphens (`mr-mime`, `ho-oh`, `porygon-z`, `great-tusk`).
"""
import json
import pathlib
import sys

SP = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")
DEST = pathlib.Path(__file__).resolve().parents[2] / "frontend/src/data/pokemon.json"
MAX_LEN = 64  # species_name column + PokemonInput max_length

# No sprite in the PokeAPI sprites repo - all non-battle (Let's Go partners,
# Koraidon/Miraidon ride builds) or not a real form (zygarde-mega).
NO_SPRITE = {10158, 10159, 10264, 10265, 10266, 10267, 10268, 10269, 10270, 10271, 10301}

BASE_SPECIAL = {
    "nidoran-f": "Nidoran♀", "nidoran-m": "Nidoran♂",
    "mr-mime": "Mr. Mime", "mime-jr": "Mime Jr.", "mr-rime": "Mr. Rime",
    "type-null": "Type: Null", "porygon-z": "Porygon-Z", "porygon2": "Porygon2",
    "farfetchd": "Farfetch'd", "sirfetchd": "Sirfetch'd",
    "ho-oh": "Ho-Oh", "jangmo-o": "Jangmo-o", "hakamo-o": "Hakamo-o", "kommo-o": "Kommo-o",
    "flabebe": "Flabébé", "chi-yu": "Chi-Yu", "chien-pao": "Chien-Pao",
    "ting-lu": "Ting-Lu", "wo-chien": "Wo-Chien",
    "tapu-koko": "Tapu Koko", "tapu-lele": "Tapu Lele",
    "tapu-bulu": "Tapu Bulu", "tapu-fini": "Tapu Fini",
}

# Form qualifiers whose plain title-case would read wrong.
FORM_TOKENS = {
    "alola": "Alolan", "galar": "Galarian", "hisui": "Hisuian", "paldea": "Paldean",
    "gmax": "Gigantamax", "mega": "Mega", "x": "X", "y": "Y",
    "10": "10%", "50": "50%", "gorging": "Gorging", "hangry": "Hangry",
}


def base_display(name: str) -> str:
    if name in BASE_SPECIAL:
        return BASE_SPECIAL[name]
    return " ".join(part.capitalize() for part in name.split("-"))


# Whole-suffix overrides where the in-game name isn't derivable from the slug.
FORM_PHRASES = {
    "dusk": "Dusk Mane", "dawn": "Dawn Wings",          # Necrozma
    "ice": "Ice Rider", "shadow": "Shadow Rider",        # Calyrex
    "single-strike": "Single Strike", "rapid-strike": "Rapid Strike",
}


def form_display(base: str, suffix: str) -> str:
    if base in ("necrozma", "calyrex") and suffix in FORM_PHRASES:
        return FORM_PHRASES[suffix]
    return " ".join(FORM_TOKENS.get(tok, tok.capitalize()) for tok in suffix.split("-"))


species = {e["name"] for e in json.loads((SP / "species.json").read_text())["results"]}
rows = [
    (int(e["url"].rstrip("/").rsplit("/", 1)[-1]), e["name"])
    for e in json.loads((SP / "all_pokemon.json").read_text())["results"]
]


def split(name: str):
    best = None
    for s in species:
        if name == s:
            return s, ""
        if name.startswith(s + "-") and (best is None or len(s) > len(best)):
            best = s
    if best is None:
        raise SystemExit(f"no canonical species resolves {name!r}")
    return best, name[len(best) + 1:]


out = []
for poke_id, raw in sorted(rows):
    if poke_id in NO_SPRITE:
        continue
    base, suffix = split(raw)
    label = base_display(base)
    if suffix:
        label = f"{label} ({form_display(base, suffix)})"
    out.append({"id": poke_id, "name": label})

longest = max(out, key=lambda p: len(p["name"]))
if len(longest["name"]) > MAX_LEN:
    raise SystemExit(f"name too long for species_name({MAX_LEN}): {longest}")

DEST.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

print(f"wrote {len(out)} entries ({DEST.stat().st_size // 1024}KB)")
print(f"  base species : {sum(1 for p in out if p['id'] <= 1025)}")
print(f"  alt forms    : {sum(1 for p in out if p['id'] > 1025)}  (excluded {len(NO_SPRITE)} with no sprite)")
print(f"  longest name : {len(longest['name'])} chars -> {longest['name']!r}  (limit {MAX_LEN})")
