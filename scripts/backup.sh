#!/usr/bin/env bash
#
# Encrypted PostgreSQL backup with daily/weekly/monthly retention.
#
# A Docker volume is not a backup: it dies with the droplet, and it does not
# protect against a bad migration or a mistaken delete. This takes a real
# pg_dump, encrypts it before it ever leaves the database host, and keeps a
# generational history.
#
#   ./scripts/backup.sh                 take a backup
#   ./scripts/backup.sh --check         report the age of the newest backup
#
# Off-site: set BACKUP_REMOTE (an rclone remote or s3:// URL) in .env. Until
# then backups are local-only, which is stated loudly rather than skipped
# silently.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/srv/backups}"
SECRETS_DIR="${SECRETS_DIR:-$ROOT/secrets}"
ENC_KEY_FILE="$SECRETS_DIR/backup_key"

RETAIN_DAILY="${BACKUP_RETENTION_DAILY:-7}"
RETAIN_WEEKLY="${BACKUP_RETENTION_WEEKLY:-4}"
RETAIN_MONTHLY="${BACKUP_RETENTION_MONTHLY:-6}"

# Alert if the newest backup is older than this.
MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-30}"

log()  { echo "[backup] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
fail() { echo "[backup] ERROR: $*" >&2; exit 1; }

# ------------------------------------------------------------------ --check

if [[ "${1:-}" == "--check" ]]; then
    newest=$(find "$BACKUP_DIR/daily" -name '*.sql.gz.enc' -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 || true)
    if [[ -z "$newest" ]]; then
        echo "CRITICAL: no backups found in $BACKUP_DIR/daily"
        exit 2
    fi
    ts=${newest%% *}
    age_hours=$(( ( $(date +%s) - ${ts%.*} ) / 3600 ))
    if (( age_hours > MAX_AGE_HOURS )); then
        echo "CRITICAL: newest backup is ${age_hours}h old (limit ${MAX_AGE_HOURS}h): ${newest#* }"
        exit 2
    fi
    echo "OK: newest backup is ${age_hours}h old"
    exit 0
fi

# ------------------------------------------------------------------- backup

command -v openssl >/dev/null || fail "openssl is required for encryption"

[[ -f "$ROOT/.env" ]] || fail "no .env at $ROOT"
# shellcheck disable=SC1091
set -a; source "$ROOT/.env"; set +a
: "${POSTGRES_USER:?POSTGRES_USER not set in .env}"
: "${POSTGRES_DB:?POSTGRES_DB not set in .env}"

# The encryption key is generated once and must be kept somewhere OTHER than
# this server, or an attacker who takes the box also takes the plaintext.
if [[ ! -s "$ENC_KEY_FILE" ]]; then
    log "no backup key found; generating one"
    mkdir -p "$SECRETS_DIR"; chmod 700 "$SECRETS_DIR"
    openssl rand -base64 48 | tr -d '\n=' > "$ENC_KEY_FILE"
    chmod 600 "$ENC_KEY_FILE"
    log "created $ENC_KEY_FILE - COPY IT SOMEWHERE OFF THIS SERVER; without it backups cannot be restored"
fi

mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly}
chmod 750 "$BACKUP_DIR" "$BACKUP_DIR"/{daily,weekly,monthly}

stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$BACKUP_DIR/daily/pkprem-$stamp.sql.gz.enc"
tmp=$(mktemp "$BACKUP_DIR/.in-progress.XXXXXX")
# Never leave a truncated file that looks like a valid backup.
trap 'rm -f "$tmp"' EXIT

log "dumping database $POSTGRES_DB"
# --clean --if-exists so the dump can rebuild over an existing schema during a
# restore drill. Streamed straight into gzip and openssl: the plaintext dump is
# never written to disk.
docker compose -f "$COMPOSE_FILE" exec -T db \
    pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --clean --if-exists \
    | gzip -9 \
    | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$ENC_KEY_FILE" \
    > "$tmp"

size=$(stat -c %s "$tmp" 2>/dev/null || stat -f %z "$tmp")
(( size > 500 )) || fail "dump is implausibly small (${size} bytes) - refusing to keep it"

mv "$tmp" "$target"
chmod 600 "$target"
trap - EXIT
log "wrote $target (${size} bytes, encrypted)"

# Generational copies: hard links, so they cost no extra disk until the daily
# copy is pruned.
[[ "$(date -u +%u)" == "7" ]] && ln -f "$target" "$BACKUP_DIR/weekly/$(basename "$target")" && log "kept weekly copy"
[[ "$(date -u +%d)" == "01" ]] && ln -f "$target" "$BACKUP_DIR/monthly/$(basename "$target")" && log "kept monthly copy"

prune() {
    local dir="$1" keep="$2"
    local n
    n=$(find "$dir" -name '*.sql.gz.enc' -type f | wc -l)
    if (( n > keep )); then
        find "$dir" -name '*.sql.gz.enc' -type f -printf '%T@ %p\n' \
            | sort -n | head -n $(( n - keep )) | cut -d' ' -f2- \
            | while read -r old; do rm -f "$old"; log "pruned $(basename "$old")"; done
    fi
}
prune "$BACKUP_DIR/daily"   "$RETAIN_DAILY"
prune "$BACKUP_DIR/weekly"  "$RETAIN_WEEKLY"
prune "$BACKUP_DIR/monthly" "$RETAIN_MONTHLY"

# --------------------------------------------------------------- off-site

if [[ -n "${BACKUP_REMOTE:-}" ]]; then
    log "uploading to $BACKUP_REMOTE"
    if command -v rclone >/dev/null; then
        rclone copy "$target" "$BACKUP_REMOTE" || fail "off-site upload failed"
    elif command -v aws >/dev/null; then
        aws s3 cp "$target" "$BACKUP_REMOTE/" || fail "off-site upload failed"
    else
        fail "BACKUP_REMOTE is set but neither rclone nor aws CLI is installed"
    fi
    log "off-site copy complete"
else
    log "NOTE: BACKUP_REMOTE is unset - backups are LOCAL ONLY and will not survive loss of this server"
fi

log "done"
