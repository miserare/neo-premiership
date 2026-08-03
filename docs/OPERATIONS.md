# Operations runbook — pk-prem.com

Production runs on a single Ubuntu 24.04 VPS at `107.170.22.92`, as four
containers behind Caddy. Everything below is run as the `deploy` user from
`/srv/pkprem`.

```bash
ssh deploy@107.170.22.92
cd /srv/pkprem
```

`root` SSH login is disabled; administration goes through `deploy` + `sudo`.

---

## Everyday commands

```bash
docker compose -f docker-compose.prod.yml ps          # service health
docker compose -f docker-compose.prod.yml logs -f backend
./scripts/deploy.sh                                   # full deploy with smoke tests
./scripts/deploy.sh --skip-build                      # restart without rebuilding
./scripts/backup.sh                                   # take a backup now
./scripts/backup.sh --check                           # how old is the newest backup?
./scripts/restore.sh --list                           # what backups exist?
```

---

## Administrator accounts

There is deliberately **no default password**. The first administrator must be
created by hand, and the password is typed into a hidden prompt so it never
reaches shell history, the process table, or CI logs.

```bash
docker compose -f docker-compose.prod.yml exec backend \
    python -m app.cli create-admin --username admin
```

The command refuses to read from a pipe, so it cannot be automated with an
embedded password — that is intentional.

Other operations:

```bash
# List administrators
docker compose -f docker-compose.prod.yml exec backend python -m app.cli list-admins

# Change a password (also revokes every existing session)
docker compose -f docker-compose.prod.yml exec backend \
    python -m app.cli reset-password --username admin

# Emergency: sign a user out everywhere without changing their password
docker compose -f docker-compose.prod.yml exec backend \
    python -m app.cli revoke-sessions --username admin
```

**Lost the password?** Use `reset-password`. There is no recovery path that
does not involve server access, by design.

---

## Migrations

Migrations run as a one-shot `migrate` service holding a PostgreSQL advisory
lock, and the backend will not start unless it exits zero. The application can
therefore never serve a half-migrated schema.

### Inspect current state

```bash
# Which revision is the database on?
docker compose -f docker-compose.prod.yml exec db \
    psql -U pkprem -d pkprem -tAc "SELECT version_num FROM alembic_version;"

# Which revision does this release expect?
docker compose -f docker-compose.prod.yml run --rm --entrypoint alembic backend current
docker compose -f docker-compose.prod.yml run --rm --entrypoint alembic backend heads
docker compose -f docker-compose.prod.yml run --rm --entrypoint alembic backend history
```

If `current` and `heads` differ, migrations are pending.

### Recover from a failed migration

1. **Read the error first.** The backend was not started, so the site is
   serving the previous release or nothing at all — there is no rush to act
   blindly.

   ```bash
   docker compose -f docker-compose.prod.yml logs migrate
   ```

2. **Take a backup before touching anything.**

   ```bash
   ./scripts/backup.sh
   ```

3. **If the migration failed part-way**, PostgreSQL runs each migration in a
   transaction, so a failed one is rolled back and `alembic_version` still
   points at the last good revision. Confirm:

   ```bash
   docker compose -f docker-compose.prod.yml exec db \
       psql -U pkprem -d pkprem -tAc "SELECT version_num FROM alembic_version;"
   ```

4. **Fix forward** — correct the migration, redeploy. This is almost always
   preferable to downgrading.

5. **Only if fixing forward is impossible**, roll back one revision:

   ```bash
   docker compose -f docker-compose.prod.yml run --rm --entrypoint alembic backend downgrade -1
   ```

   Downgrades can lose data. `c58b74e91a20` explicitly deletes released roster
   history on downgrade, because the old schema cannot represent it.

   `e4a7c2b8d5f1` drops the `playoff_rounds` table, so rounds planned but not
   yet drawn are lost. Matches are not: the legacy `round_label`/`round_order`
   columns are kept in step by the application precisely so the previous
   release still renders the bracket in the right order after a downgrade.

   **Downgrade before transferring an older tree.** A release older than a
   migration does not contain that migration's file, so Alembic cannot find the
   revision to downgrade *from*. Run the downgrade from the current checkout
   first, then transfer the older tree and deploy.

### Stuck advisory lock

If a `migrate` container was killed mid-run, its lock is released automatically
when the connection drops. If a lock genuinely appears stuck:

```bash
docker compose -f docker-compose.prod.yml exec db \
    psql -U pkprem -d pkprem -c "SELECT pid, granted FROM pg_locks WHERE locktype='advisory';"
```

---

## Backups

- **Schedule:** daily at 03:20 UTC (`pkprem-backup.timer`).
- **Restore drill:** weekly, Sundays 04:30 UTC (`pkprem-restore-check.timer`),
  into a temporary database. Production is never touched.
- **Retention:** 7 daily, 4 weekly, 6 monthly.
- **Location:** `/srv/backups/{daily,weekly,monthly}`, AES-256 encrypted.
- **Key:** `/srv/pkprem/secrets/backup_key`.

> **The encryption key must be copied off this server.** Without it the backups
> are unrecoverable, and a server loss takes both the data and the key.

```bash
systemctl list-timers 'pkprem-*'
journalctl -u pkprem-backup.service -n 50
```

### Verify a backup (safe)

Restores into a throwaway database and drops it afterwards:

```bash
./scripts/restore.sh --verify-latest
```

### Restore into production (destructive)

```bash
./scripts/restore.sh --file /srv/backups/daily/<file>.sql.gz.enc --into-production
```

Requires typing the database name back. Take a fresh backup first — everything
written since the chosen backup will be lost.

### Enable off-site copies

Backups are currently **local only**, which does not protect against losing the
droplet. Add to `.env`:

```
BACKUP_REMOTE=s3://your-bucket/pkprem     # or an rclone remote
```

and install `rclone` or the AWS CLI. Store `backup_key` somewhere other than
this server and other than the backup destination.

---

## Deployment and rollback

Releases are transferred as an exact git archive with the commit recorded in
`/srv/pkprem/RELEASE`. The last deployment is recorded in
`/srv/pkprem/.deploy/last-release.txt`.

```bash
cat RELEASE
cat .deploy/last-release.txt
```

### Rollback

```bash
# On your machine, export the previous commit and transfer it:
git archive <previous-commit> | ssh deploy@107.170.22.92 'tar -x -C /srv/pkprem'
ssh deploy@107.170.22.92 'cd /srv/pkprem && ./scripts/deploy.sh'
```

A rollback across a migration boundary needs the downgrade path above. Check
whether the release you are leaving added a migration before rolling back.

---

## TLS

Caddy obtains and renews Let's Encrypt certificates automatically. Certificates
live in the `caddy_data` volume.

> **Do not delete `caddy_data`.** Re-requesting certificates on every restart
> will hit Let's Encrypt rate limits and lock the domain out for about a week.

```bash
docker compose -f docker-compose.prod.yml logs caddy | grep -i certificate
echo | openssl s_client -connect pk-prem.com:443 -servername pk-prem.com 2>/dev/null \
    | openssl x509 -noout -dates
```

HSTS is currently host-only (`max-age=31536000`, no `includeSubDomains`, no
preload). Only add `includeSubDomains` once every subdomain you intend to use
serves HTTPS — it is hard to reverse.

---

## Firewall and access

```bash
sudo ufw status verbose
```

Open: 22 (SSH), 80 (ACME challenge + HTTPS redirect), 443 (HTTPS). Nothing
else. PostgreSQL, FastAPI and nginx publish no host ports at all.

To restrict SSH to a fixed address (only if you have a static IP — this locks
you out otherwise):

```bash
sudo ufw allow from <your.ip.address> to any port 22 proto tcp
sudo ufw delete allow 22/tcp
```

---

## Health endpoints

| Endpoint  | Meaning |
| --------- | ------- |
| `/health` | Liveness. Process is up. Does **not** touch the database, so a database outage will not cause the process to be killed. |
| `/ready`  | Readiness. Runs `SELECT 1`. Returns 503 while PostgreSQL is unreachable. This is what the container healthcheck uses. |

---

## Common incidents

**Site returns 502.** Backend is unhealthy or restarting.
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail 100 backend
```

**Backend unhealthy but running.** Usually PostgreSQL. Check `/ready`:
```bash
docker compose -f docker-compose.prod.yml exec backend python /app/scripts/healthcheck.py; echo "exit=$?"
```

**Certificate not issuing.** Check DNS resolves to this host and that ports 80
and 443 are reachable from the internet.
```bash
dig +short pk-prem.com A
docker compose -f docker-compose.prod.yml logs caddy | tail -50
```

**Locked out of the admin login.** Login throttling is per-account and per-IP,
recorded in the database, and clears after `LOGIN_LOCKOUT_MINUTES` (15). To
clear immediately:
```bash
docker compose -f docker-compose.prod.yml exec db \
    psql -U pkprem -d pkprem -c "DELETE FROM admin_login_attempts;"
```

**Disk filling.** Container logs are capped at 10 MB × 3 per service. The usual
culprit is backups or Docker build cache:
```bash
df -h /
du -sh /srv/backups
docker system prune -f
```
