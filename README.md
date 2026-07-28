# Pokémon Premiership

The league site for the Pokémon Premiership draft league: season archives with
standings and playoff brackets, player profiles with per-season drafted rosters,
match histories with per-game replays, and a token-gated admin area for running
all of it.

## Stack

| Layer    | Choice |
| -------- | ------ |
| Backend  | FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 |
| Database | PostgreSQL 15 |
| Frontend | React 18 + TypeScript, Vite, React Router |
| Serving  | nginx (static build) behind Caddy (automatic TLS) |

## Quick start

Requires Docker and Docker Compose.

```bash
cp .env.example .env      # then edit ADMIN_TOKEN
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m seeds.seed_dev   # optional sample data
```

- Site: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Admin: <http://localhost:5173/admin> (sign in with your `ADMIN_TOKEN`)

The admin area is intentionally not linked from the public navigation.

The database is published on **loopback only, port 55432**, so it doesn't
collide with a Postgres already installed on the host and isn't reachable from
the network. Connect with `psql -h localhost -p 55432 -U neo_premiership`, or
override `DB_HOST_PORT`.

## Configuration

All settings come from environment variables; see `.env.example`.

| Variable | Purpose |
| -------- | ------- |
| `DATABASE_URL` | Postgres DSN. Must use the `postgresql+asyncpg://` driver. |
| `ADMIN_TOKEN` | Shared secret for every admin write, sent as `X-Admin-Token`. **Unset means admin routes fail closed with 503** rather than running open. |
| `CORS_ORIGINS` | Comma-separated origins allowed to call the API. Irrelevant in the default production setup, where the site and API share an origin. |
| `VITE_API_URL` | API base URL, baked in at build time. Leave **empty** in production so the app calls `/api` on its own origin. |
| `ENVIRONMENT` | Defaults to `production`. Set to `development` to turn on SQLAlchemy query echo. |
| `DOMAIN` | Production only. The hostname Caddy requests a certificate for. |

Generate a real admin token with:

```bash
openssl rand -hex 32
```

## Database

Migrations are **not** applied automatically — run them after every deploy that
adds one, including the very first boot:

```bash
docker compose exec backend alembic upgrade head
```

To create one after changing a model:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
```

Review the generated file before committing it; autogenerate misses `CHECK`
constraints and never writes data backfills.

## Tests

```bash
cd backend && python -m pytest        # 52 tests
cd backend && ruff check app/ tests/
cd frontend && npx tsc -b && npm run build
```

Tests run against in-memory SQLite for speed. Note that **SQLite does not
enforce foreign keys**, so anything depending on `ON DELETE` behaviour — player
deletion in particular — must also be checked against Postgres.

## Pokémon catalogue

The draft picker is backed by `frontend/src/data/pokemon.json` — 1340 entries
covering every base species plus mega evolutions, regional variants, Gigantamax
and other alternate forms. It is bundled rather than fetched so the picker works
without a live PokeAPI call, and code-split so only admins download it.

Entries are keyed on **PokeAPI's id, not the national dex number**, which is
what lets forms resolve to their own sprite: Charizard is 6, Mega Charizard X is
10034. Eleven ids in the form range have no sprite in the PokeAPI repo (Let's Go
partner Pikachu/Eevee, Koraidon/Miraidon ride builds, a `zygarde-mega` that
isn't a real form) and are excluded.

To refresh it after a new generation is released:

```bash
curl -s "https://pokeapi.co/api/v2/pokemon?limit=100000" -o /tmp/all_pokemon.json
curl -s "https://pokeapi.co/api/v2/pokemon-species?limit=100000" -o /tmp/species.json
python backend/seeds/generate_pokemon_catalogue.py /tmp
```

The script fails loudly if a name would exceed the `species_name` column limit.

## Deployment

`docker-compose.prod.yml` runs a production stack: a static frontend build
served by nginx, uvicorn without `--reload`, no published database port, and
Caddy terminating TLS.

```bash
# On the server, with DNS for $DOMAIN already pointing at it:
cp .env.example .env      # set DOMAIN, ADMIN_TOKEN, POSTGRES_PASSWORD
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

Caddy obtains and renews Let's Encrypt certificates automatically. It needs
ports 80 and 443 reachable from the internet — 80 is used for the ACME
challenge as well as the HTTPS redirect.

Because Caddy serves the site and proxies `/api` on the **same origin**, the
browser makes same-origin requests: `VITE_API_URL` stays empty and CORS never
applies. If you split the API onto its own subdomain instead, set both
`VITE_API_URL` and `CORS_ORIGINS` accordingly.

The `caddy_data` volume holds the certificates. Don't delete it — re-requesting
certificates on every restart will hit Let's Encrypt's rate limits.

## Project layout

```
backend/
  app/
    models/      SQLAlchemy tables
    schemas/     Pydantic request/response models
    crud/        Database access
    services/    Derived views (standings, brackets, records, home)
    routers/     HTTP endpoints
  alembic/       Migrations
  seeds/         Development sample data
  tests/
frontend/
  src/
    pages/       Route components, including the admin area
    components/  Shared UI
    hooks/       Data fetching
    lib/api.ts   Typed API client and admin-token handling
    data/        Bundled Pokémon species list for the draft picker
  public/        Logo, favicons, self-hosted font
Caddyfile                 Reverse proxy + TLS
docker-compose.yml        Development
docker-compose.prod.yml   Production
```

## Notable behaviour

- **Matches are series.** Each match holds ordered games with their own winner
  and replay URL, so a best-of-three reports `2-1` and links G1/G2/G3. Matches
  with only a legacy single `replay_url` still render as a one-game series.
- **Deleting a player preserves history.** Their matches, per-game winners,
  brought teams, and championships transfer to a hidden placeholder player
  rather than cascading away.
- **Home page links are automatic but overridable.** The stream, document and
  table links derive from league data by default; an admin can pin any of them
  under Admin → Site, and clearing a pinned URL restores the derived one.

## Credits and licence

Pokémon and Pokémon character names are trademarks of Nintendo, Creatures Inc.
and GAME FREAK Inc. This is an unofficial, non-commercial fan project, not
affiliated with or endorsed by them.

Sprites are served from [PokeAPI](https://pokeapi.co/) via jsDelivr. The
bundled [Jost](https://github.com/indestructible-type/Jost) typeface is used
under the SIL Open Font License; see `frontend/public/fonts/OFL.txt`.
