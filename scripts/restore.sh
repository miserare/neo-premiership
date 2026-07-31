#!/usr/bin/env bash
#
# Restore an encrypted backup.
#
# Defaults to a TEMPORARY verification database, because that is what you
# actually want almost every time: proof the backup is readable. Overwriting
# production is possible but requires typing the production database name back,
# so it cannot happen by reflex or by a stray shell-history recall.
#
#   ./scripts/restore.sh --list
#   ./scripts/restore.sh --verify-latest              (safe: temp database)
#   ./scripts/restore.sh --file <path>                (safe: temp database)
#   ./scripts/restore.sh --file <path> --into-production   (destructive)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/srv/backups}"
ENC_KEY_FILE="${SECRETS_DIR:-$ROOT/secrets}/backup_key"
VERIFY_DB="pkprem_restore_check"

log()  { echo "[restore] $*"; }
fail() { echo "[restore] ERROR: $*" >&2; exit 1; }

MODE="verify"
FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --list)
            find "$BACKUP_DIR" -name '*.sql.gz.enc' -type f -printf '%TY-%Tm-%Td %TH:%TM  %10s  %p\n' \
                | sort -r | sed 's/^/  /'
            exit 0 ;;
        --verify-latest)
            FILE=$(find "$BACKUP_DIR/daily" -name '*.sql.gz.enc' -type f -printf '%T@ %p\n' \
                   | sort -rn | head -1 | cut -d' ' -f2-)
            [[ -n "$FILE" ]] || fail "no backups found"
            shift ;;
        --file) FILE="$2"; shift 2 ;;
        --into-production) MODE="production"; shift ;;
        *) fail "unknown argument: $1" ;;
    esac
done

[[ -n "$FILE" ]] || fail "specify --file <path> or --verify-latest"
[[ -f "$FILE" ]] || fail "no such file: $FILE"
[[ -s "$ENC_KEY_FILE" ]] || fail "missing decryption key at $ENC_KEY_FILE"

[[ -f "$ROOT/.env" ]] || fail "no .env at $ROOT"
# shellcheck disable=SC1091
set -a; source "$ROOT/.env"; set +a
: "${POSTGRES_USER:?}"; : "${POSTGRES_DB:?}"

decrypt() {
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$ENC_KEY_FILE" -in "$FILE" | gunzip
}

if [[ "$MODE" == "verify" ]]; then
    # Restores into a throwaway database. Production is never touched, so this
    # is safe to run on a schedule.
    log "target: TEMPORARY database '$VERIFY_DB' (production is untouched)"
    log "source: $FILE"

    docker compose -f "$COMPOSE_FILE" exec -T db \
        psql --username "$POSTGRES_USER" --dbname postgres \
        -c "DROP DATABASE IF EXISTS $VERIFY_DB;" -c "CREATE DATABASE $VERIFY_DB;" >/dev/null

    decrypt | docker compose -f "$COMPOSE_FILE" exec -T db \
        psql --username "$POSTGRES_USER" --dbname "$VERIFY_DB" --quiet >/dev/null

    tables=$(docker compose -f "$COMPOSE_FILE" exec -T db psql --username "$POSTGRES_USER" \
             --dbname "$VERIFY_DB" -tAc \
             "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d '\r')
    version=$(docker compose -f "$COMPOSE_FILE" exec -T db psql --username "$POSTGRES_USER" \
             --dbname "$VERIFY_DB" -tAc "SELECT version_num FROM alembic_version;" 2>/dev/null | tr -d '\r' || echo "?")

    log "restored $tables table(s); schema at migration $version"
    (( tables > 5 )) || fail "restored database has too few tables - treat this backup as suspect"

    docker compose -f "$COMPOSE_FILE" exec -T db \
        psql --username "$POSTGRES_USER" --dbname postgres -c "DROP DATABASE $VERIFY_DB;" >/dev/null
    log "verification database dropped. BACKUP IS GOOD."
    exit 0
fi

# ------------------------------------------------------- destructive path

cat <<EOF

  *** THIS WILL OVERWRITE THE PRODUCTION DATABASE ***

    server    : $(hostname)
    database  : $POSTGRES_DB
    backup    : $FILE
    taken     : $(date -r "$FILE" -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || stat -f %Sm "$FILE")

  Every change made since that backup will be lost.
  Consider taking a fresh backup first: ./scripts/backup.sh

EOF
read -r -p "  Type the database name ($POSTGRES_DB) to proceed: " confirm
[[ "$confirm" == "$POSTGRES_DB" ]] || fail "confirmation did not match - nothing was changed"

log "stopping the application so nothing writes mid-restore"
docker compose -f "$COMPOSE_FILE" stop backend >/dev/null

log "restoring into $POSTGRES_DB"
decrypt | docker compose -f "$COMPOSE_FILE" exec -T db \
    psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --quiet >/dev/null

log "restarting the application"
docker compose -f "$COMPOSE_FILE" start backend >/dev/null
log "done. Verify the site before considering this finished."
