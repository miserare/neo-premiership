#!/bin/sh
#
# Run database migrations exactly once, then exit.
#
# This runs as its own one-shot Compose service, and the backend is gated on it
# exiting 0, so the API is never started against a half-migrated schema.
#
# It NEVER runs a seed script. Production starts with an empty, migrated schema.

set -eu

echo "[migrate] starting"

python - <<'PY'
import asyncio
import subprocess
import sys

from sqlalchemy import text

from app.database import engine

# Arbitrary but fixed key ("pkpr"). Any process using the same key serialises
# against us.
LOCK_ID = 0x706B7072
MAX_WAIT_ATTEMPTS = 60


async def wait_for_database() -> None:
    for attempt in range(1, MAX_WAIT_ATTEMPTS + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print(f"[migrate] database reachable after {attempt} attempt(s)", flush=True)
            return
        except Exception:
            if attempt == MAX_WAIT_ATTEMPTS:
                raise
            await asyncio.sleep(2)


async def main() -> int:
    await wait_for_database()

    # Hold a session-scoped advisory lock for the whole alembic run. If two
    # migrate containers start together, exactly one proceeds and the other
    # waits, then finds nothing to do. The lock is released automatically if
    # this process dies, so it can never be left held.
    async with engine.connect() as lock_conn:
        print("[migrate] acquiring advisory lock", flush=True)
        await lock_conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": LOCK_ID})
        try:
            print("[migrate] lock held; running alembic upgrade head", flush=True)
            # Alembic opens its own connection; the lock exists purely to
            # serialise concurrent starters.
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd="/app",
                capture_output=True,
                text=True,
            )
            sys.stdout.write(result.stdout)
            if result.returncode != 0:
                sys.stderr.write(result.stderr)
                print("[migrate] FAILED: alembic exited non-zero", file=sys.stderr, flush=True)
                return result.returncode
            print("[migrate] alembic upgrade complete", flush=True)
        finally:
            await lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_ID})

    await engine.dispose()
    return 0


try:
    sys.exit(asyncio.run(main()))
except Exception as exc:  # noqa: BLE001 - report the reason and fail the service
    print(f"[migrate] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(1)
PY

echo "[migrate] done"
