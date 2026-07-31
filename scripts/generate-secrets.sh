#!/usr/bin/env bash
#
# Generate production secrets into ./secrets/ with owner-only permissions.
#
# Secrets are written straight to disk and NEVER printed. Nothing here echoes a
# value, so the secrets do not enter your terminal scrollback, shell history,
# CI logs, or this repository (./secrets is gitignored).
#
# Safe to re-run: existing files are left alone unless --rotate is given.

set -euo pipefail

SECRETS_DIR="${SECRETS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/secrets}"
ROTATE=0

usage() {
    cat <<'EOF'
Usage: generate-secrets.sh [--rotate NAME]

  (no arguments)   Create any missing secrets. Existing files are preserved.
  --rotate NAME    Replace one secret: session_secret | postgres_password

Rotating session_secret signs every administrator out.
Rotating postgres_password requires also changing it inside PostgreSQL - see
docs/OPERATIONS.md before doing it.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rotate) ROTATE="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
    esac
done

umask 077
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# 32 bytes of kernel randomness, base64 for safe transport through env files.
random_secret() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -base64 48 | tr -d '\n=' | cut -c1-64
    else
        head -c 48 /dev/urandom | base64 | tr -d '\n=' | cut -c1-64
    fi
}

write_secret() {
    # Two statements, not one: under `set -u` bash expands every argument of a
    # single `local` before assigning any of them, so $name would be unbound.
    local name="$1"
    local path="$SECRETS_DIR/$name"

    if [[ -s "$path" && "$ROTATE" != "$name" ]]; then
        echo "  = $name (already exists, left unchanged)"
        return
    fi
    if [[ -s "$path" && "$ROTATE" == "$name" ]]; then
        cp "$path" "$path.previous-$(date +%Y%m%d%H%M%S)"
        chmod 600 "$path.previous"* 2>/dev/null || true
        echo "  ~ $name (rotated; previous value kept alongside)"
    else
        echo "  + $name (created)"
    fi

    # Written directly to the file. The value is never on stdout.
    random_secret > "$path"
    chmod 600 "$path"
}

echo "Writing secrets to $SECRETS_DIR"
write_secret session_secret
write_secret postgres_password

echo
echo "Permissions:"
ls -l "$SECRETS_DIR" | awk 'NR>1 {print "  " $1, $9}'
echo
echo "Done. No secret values were printed."
echo "Next: docker compose -f docker-compose.prod.yml up -d --build"
