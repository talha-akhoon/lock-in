# Restore runbook

An untested backup is not a backup. Every member has a real financial stake in
this data, so run the drill below **before** the first challenge starts, and
again whenever the schema changes materially.

Everything here is copy-pasteable. Substitute only the values in `<angle
brackets>`.

## What the backup is

`.github/workflows/backup.yml` runs weekly and on demand. Each run writes
`lockin-<YYYY-MM-DD>.sql.gz.enc` to two places:

- a GitHub Actions artifact named `lockin-backup-<run-id>` (kept 90 days)
- `gs://lockin-505614-backups/` (kept until you delete it)

That is a plain `pg_dump` (SQL format, no owners, no ACLs), gzipped, then
encrypted with AES-256-CBC using PBKDF2 at 100,000 iterations.

Two secrets are required, and neither may be the value the application uses:

| Secret | Value |
| --- | --- |
| `BACKUP_DATABASE_URL` | Neon's **direct** (non-pooled) connection string, in plain `postgresql://` form with `?sslmode=require` |
| `BACKUP_ENCRYPTION_KEY` | A long passphrase stored somewhere other than GitHub |

`pg_dump` rejects the `postgresql+psycopg://` scheme the application uses, so
the URL must not carry the driver suffix. The workflow fails loudly rather than
silently producing an empty file if it does.

## Step 1 — Get the archive

From GitHub:

```bash
gh run list --workflow "Weekly database backup" --limit 5
gh run download <run-id> --dir ./restore
cd restore
ls -lh
```

Or from GCS (survives the 90-day artifact window):

```bash
gcloud storage ls gs://lockin-505614-backups/
gcloud storage cp gs://lockin-505614-backups/lockin-<YYYY-MM-DD>.sql.gz.enc ./restore/
cd restore
ls -lh
```

Anything under a kilobyte is a failed dump, not a small database.

## Step 2 — Decrypt and decompress

```bash
export BACKUP_ENCRYPTION_KEY='<the passphrase>'

openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
  -pass env:BACKUP_ENCRYPTION_KEY \
  -in lockin-<YYYY-MM-DD>.sql.gz.enc \
  | gunzip > lockin.sql

head -n 20 lockin.sql   # should start with "-- PostgreSQL database dump"
grep -c "COPY public" lockin.sql
```

If `openssl` reports `bad decrypt`, the passphrase is wrong. There is no
recovery path from a lost passphrase — that is the point of storing it
separately.

## Step 3 — Restore into a throwaway database first

Never restore straight over production. Prove the dump is good locally:

```bash
docker run -d --name lockin-restore \
  -e POSTGRES_PASSWORD=restore \
  -e POSTGRES_USER=lockin \
  -e POSTGRES_DB=lockin_restore \
  -p 55433:5432 \
  postgres:17-alpine

until docker exec lockin-restore pg_isready -U lockin; do sleep 1; done

psql "postgresql://lockin:restore@127.0.0.1:55433/lockin_restore" \
  --set ON_ERROR_STOP=on -f lockin.sql
```

## Step 4 — Verify the restore is actually usable

Row counts, not vibes:

```bash
psql "postgresql://lockin:restore@127.0.0.1:55433/lockin_restore" -c "
SELECT 'users' AS table, count(*) FROM users
UNION ALL SELECT 'teams', count(*) FROM teams
UNION ALL SELECT 'challenges', count(*) FROM challenges
UNION ALL SELECT 'challenge_participants', count(*) FROM challenge_participants
UNION ALL SELECT 'goals', count(*) FROM goals
UNION ALL SELECT 'goal_progress_entries', count(*) FROM goal_progress_entries
UNION ALL SELECT 'daily_checkins', count(*) FROM daily_checkins
UNION ALL SELECT 'forfeit_obligations', count(*) FROM forfeit_obligations
UNION ALL SELECT 'audit_logs', count(*) FROM audit_logs
ORDER BY 1;"
```

Confirm the schema is at the same migration as the code, and that the
invariants survived the round trip:

```bash
psql "postgresql://lockin:restore@127.0.0.1:55433/lockin_restore" \
  -c "SELECT version_num FROM alembic_version;" \
  -c "SELECT indexname FROM pg_indexes WHERE indexname IN
        ('uq_team_members_one_active_team','uq_challenges_one_open_per_team');"
```

Then point the application at it and sign in:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://lockin:restore@127.0.0.1:55433/lockin_restore \
  uv run uvicorn app.main:app --port 8001
curl -fsS http://127.0.0.1:8001/healthz
```

Tear the drill down when finished:

```bash
docker rm -f lockin-restore
rm -f lockin.sql lockin-*.sql.gz.enc
```

The decrypted `lockin.sql` contains every member's email and goals. Do not
leave it on disk.

## Step 5 — Restoring for real

Only after step 4 passes on the same artifact.

1. **Stop writes.** Scale Cloud Run to zero so nothing is half-written during
   the restore:

   ```bash
   gcloud run services update lockin --region <region> --max-instances 0
   ```

2. **Branch, don't overwrite.** On Neon, create a branch from the current state
   before touching it, so a botched restore is still reversible:

   ```bash
   neonctl branches create --name pre-restore-$(date -u +%Y%m%dT%H%M)
   ```

3. **Restore into a fresh database**, not the live one:

   ```bash
   psql "<neon-direct-url>?sslmode=require" -c 'CREATE DATABASE lockin_restored;'
   psql "<neon-direct-url-with-lockin_restored>?sslmode=require" \
     --set ON_ERROR_STOP=on -f lockin.sql
   ```

4. **Re-run the step 4 checks** against `lockin_restored`.

5. **Cut over** by updating the `lockin-database-url` secret to point at the
   restored database, then bring the service back:

   ```bash
   printf '%s' 'postgresql+psycopg://<user>:<pass>@<host>/lockin_restored?sslmode=require' \
     | gcloud secrets versions add lockin-database-url --data-file=-
   gcloud run services update lockin --region <region> --max-instances 1
   ```

6. **Verify the product, not just the process.** Sign in, open the dashboard,
   check a member profile, and confirm the audit log and any forfeit
   obligations are present.

## Recovery expectations

- **Recovery point:** up to 7 days of loss from the weekly artifact alone. Neon's
  own point-in-time restore covers the gap on the free plan (7 days of history)
  and should be the first thing tried for recent damage.
- **Recovery time:** roughly 30 minutes end to end for a database this size,
  most of it verification.
- **Single point of failure:** `BACKUP_ENCRYPTION_KEY`. Store it outside GitHub,
  and make sure at least one other person can reach it.
