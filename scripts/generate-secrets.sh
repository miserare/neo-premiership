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

# Secret files stay mode 0600, but they must be owned by the uid the backend
# container runs as, because Compose bind-mounts them with host ownership and
# the app runs unprivileged. PostgreSQL is unaffected: its entrypoint starts as
# root and reads the file before dropping to the postgres user.
#
# Owning them by an unmapped uid is also stricter on the host than owning them
# by the deploy user - only root and that uid can read them.
SECRET_UID="${SECRET_UID:-10001}"

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
# Alphanumeric only. base64 emits '/' and '+', which must then be URL-encoded
# into a database URL as %2F/%2B - and a '%' in a connection string breaks
# configparser-based tooling in ways whose error messages quote the URL.
# 64 alphanumeric characters is ~380 bits, far above the 32-byte requirement.
random_secret() {
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 64
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

# Apply container-app ownership. Needs root, so skip cleanly when unavailable
# (local development runs everything as one user anyway).
if [ "$(id -u)" -eq 0 ]; then
    chown "$SECRET_UID:$SECRET_UID" "$SECRETS_DIR"/* 2>/dev/null || true
elif command -v sudo >/dev/null && sudo -n true 2>/dev/null; then
    sudo chown "$SECRET_UID:$SECRET_UID" "$SECRETS_DIR"/* 2>/dev/null || true
else
    echo "  ! could not chown secrets to uid $SECRET_UID (no root); the backend container may not be able to read them"
fi

echo
echo "Permissions:"
ls -ln "$SECRETS_DIR" | awk 'NR>1 {print "  " $1, "uid="$3, $9}'
echo
echo "Done. No secret values were printed."
echo "Next: docker compose -f docker-compose.prod.yml up -d --build"
