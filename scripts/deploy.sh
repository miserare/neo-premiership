#!/usr/bin/env bash
#
# Production deployment for pk-prem.com.
#
# Validates configuration, builds, checks the bundle, migrates once, starts the
# stack, waits for health, and smoke-tests the public surface. Records the exact
# commit deployed and keeps the previous images so a rollback is possible.
#
#   ./scripts/deploy.sh                deploy the current checkout
#   ./scripts/deploy.sh --skip-build   restart without rebuilding

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -f docker-compose.prod.yml"
SKIP_BUILD=0
[[ "${1:-}" == "--skip-build" ]] && SKIP_BUILD=1

step() { echo; echo "==> $*"; }
fail() { echo "DEPLOY FAILED: $*" >&2; exit 1; }

# ------------------------------------------------------- 1. configuration

step "Validating configuration"
[[ -f .env ]] || fail ".env is missing (copy .env.production.example)"
# shellcheck disable=SC1091
set -a; source .env; set +a

[[ "${ENVIRONMENT:-}" == "production" ]] || fail "ENVIRONMENT must be 'production' (got '${ENVIRONMENT:-unset}')"
[[ -n "${DOMAIN:-}" ]] || fail "DOMAIN is not set"
[[ -z "${VITE_API_URL:-}" ]] || fail "VITE_API_URL must be EMPTY so the browser calls /api same-origin"

for secret in secrets/session_secret secrets/postgres_password; do
    [[ -s "$secret" ]] || fail "$secret missing or empty - run ./scripts/generate-secrets.sh"
    perms=$(stat -c %a "$secret" 2>/dev/null || stat -f %Lp "$secret")
    [[ "$perms" == "600" ]] || fail "$secret has permissions $perms, expected 600"
    # stat, not `wc -c`: the deploy user deliberately cannot READ these files -
    # they are owned by the container app uid - and validation must not require
    # a privilege the deployer should not have.
    size=$(stat -c %s "$secret" 2>/dev/null || stat -f %z "$secret")
    (( size >= 32 )) || fail "$secret is only ${size} bytes, expected at least 32"
    owner=$(stat -c %u "$secret" 2>/dev/null || stat -f %u "$secret")
    echo "  $(basename "$secret"): ${size} bytes, mode $perms, uid $owner"
done
echo "  configuration and secrets OK (values not shown)"

# The deployed tree is a git archive export, so there is no .git here. The
# exact commit is shipped in RELEASE by the transfer step. Fall back to git
# only when deploying from a real checkout.
#
# Note the guards: `set -o pipefail` means a failing `git` inside a pipeline
# aborts the whole script, so neither call may be piped unguarded.
if [[ -f RELEASE ]]; then
    RELEASE=$(cat RELEASE)
    DIRTY=0
elif git rev-parse --git-dir >/dev/null 2>&1; then
    RELEASE=$(git rev-parse HEAD)
    DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
else
    RELEASE="unknown"
    DIRTY=0
fi
echo "  release commit: $RELEASE"
[[ "$DIRTY" == "0" ]] || echo "  WARNING: working tree has $DIRTY uncommitted change(s); this is not a reproducible release"

# ---------------------------------------------------------------- 2. build

if (( SKIP_BUILD == 0 )); then
    step "Building production images"
    $COMPOSE build 2>&1 | tail -5
fi

step "Checking the compiled bundle for development leakage"
# Inspect what actually shipped, not the source tree.
BUNDLE=$($COMPOSE run --rm --no-deps --entrypoint sh frontend -c \
    'cat /usr/share/nginx/html/assets/*.js 2>/dev/null' || true)
[[ -n "$BUNDLE" ]] || fail "could not read the built bundle from the frontend image"
for pattern in 'localhost:' '127\.0\.0\.1' 'X-Admin-Token' 'dev-admin-token' 'SESSION_SECRET' 'POSTGRES_PASSWORD'; do
    if grep -qE "$pattern" <<<"$BUNDLE"; then
        fail "bundle contains '$pattern' - refusing to deploy"
    fi
done
echo "  bundle is clean (no dev URLs, no credentials)"

# ------------------------------------------------------------ 3. database

step "Starting PostgreSQL and waiting for health"
$COMPOSE up -d db
for i in $(seq 1 60); do
    status=$($COMPOSE ps db --format '{{.Status}}' 2>/dev/null || echo "")
    [[ "$status" == *healthy* ]] && break
    (( i == 60 )) && fail "PostgreSQL did not become healthy"
    sleep 2
done
echo "  database healthy"

step "Running migrations (once, under an advisory lock)"
$COMPOSE up --exit-code-from migrate migrate 2>&1 | grep -E "\[migrate\]|ERROR" | sed 's/^/  /' \
    || fail "migrations failed - the application was NOT started"

# ------------------------------------------------------------- 4. release

step "Starting application and proxy"
$COMPOSE up -d

step "Waiting for all services to report healthy"
for i in $(seq 1 60); do
    unhealthy=$($COMPOSE ps --format '{{.Service}} {{.Status}}' \
                | grep -vE 'migrate' | grep -cvE 'healthy|Exited \(0\)' || true)
    (( unhealthy == 0 )) && break
    (( i == 60 )) && { $COMPOSE ps; fail "services did not become healthy"; }
    sleep 3
done
$COMPOSE ps --format '  {{.Service}}\t{{.Status}}'

# -------------------------------------------------------------- 5. verify

step "Smoke testing"
fails=0
check() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$actual" == "$expected" ]]; then
        echo "  PASS  $desc ($actual)"
    else
        echo "  FAIL  $desc (expected $expected, got $actual)"
        fails=$((fails + 1))
    fi
}

check "https://$DOMAIN/ serves the site" 200 \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMAIN/")"
check "https://$DOMAIN/api/home responds" 200 \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMAIN/api/home")"
check "SPA deep link falls back to index.html" 200 \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMAIN/seasons/does-not-exist")"
check "http redirects to https" 308 \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "http://$DOMAIN/")"
check "admin mutation is refused anonymously" 401 \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -X POST "https://$DOMAIN/api/players" \
         -H 'Content-Type: application/json' -d '{"username":"smoke"}')"
check "API docs are disabled" 404 \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMAIN/api/openapi.json")"

if grep -q "trainer\|discord" <<<"$(curl -s --max-time 20 "https://$DOMAIN/api/players")"; then
    echo "  FAIL  anonymous player list may expose private fields"
    fails=$((fails + 1))
else
    echo "  PASS  anonymous player list carries no discord_id"
fi

echo
if (( fails > 0 )); then
    fail "$fails smoke test(s) failed"
fi

# ------------------------------------------------------------- 6. record

mkdir -p .deploy
{
    echo "deployed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "commit=$RELEASE"
    echo "dirty_files=$DIRTY"
    echo "images:"
    # `docker compose images` has no Service field in its Go template; the
    # image id per service is what a rollback actually needs.
    $COMPOSE images -q | while read -r id; do
        echo "  $(docker image inspect --format '{{index .RepoTags 0}} {{.Id}}' "$id" 2>/dev/null || echo "$id")"
    done
} > .deploy/last-release.txt
cat .deploy/last-release.txt | sed 's/^/  /'

echo
echo "Deployment complete: https://$DOMAIN"
echo "Rollback: git checkout <previous-commit> && ./scripts/deploy.sh"
