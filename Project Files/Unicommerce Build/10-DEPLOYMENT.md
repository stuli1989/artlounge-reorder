# 10 — Deployment & Railway Cutover

## Overview

When the UC build is complete and validated, merge to main and switch Railway to the UC pipeline. Since the system isn't live yet, this is low-risk.

## Pre-Cutover Checklist

- [ ] All tests passing on `feature/unicommerce` branch
- [ ] Full sync runs successfully against production UC API
- [ ] Backfill completed (transactions + positions)
- [ ] Velocity, reorder, and classification metrics look reasonable
- [ ] Comparison with Tally data shows UC is more accurate (or at least equivalent)
- [ ] Frontend displays correctly with new status names and fields
- [ ] Team has reviewed sample PO builder output

## Railway Setup

### 1. Spin up second Postgres instance

In Railway dashboard:
- Add new PostgreSQL service to the artlounge-reorder project
- Name it: `postgres-unicommerce`
- Note the connection string

### 2. Run schema migration

```bash
# Against the new Railway Postgres
PGPASSWORD=<railway_password> "/c/Program Files/PostgreSQL/17/bin/psql" \
  -h <railway_host> -p <railway_port> -U <railway_user> -d <railway_db> \
  -f src/db/migrations/uc_001_schema.sql
```

### 3. Run initial sync + backfill

```bash
# Set Railway UC database as target
export DATABASE_URL=<railway_uc_connection_string>
export UC_TENANT=ppetpl
export UC_USERNAME=<username>
export UC_PASSWORD=<password>

# Full sync (first run)
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.sync --full

# Backfill historical data
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.backfill --full
```

### 4. Merge branch

```bash
git checkout main
git merge feature/unicommerce
git push origin main
```

This triggers Railway auto-deploy.

### 5. Switch connection string

In Railway dashboard:
- Update `DATABASE_URL` env var on the app service to point to `postgres-unicommerce`
- Add UC env vars: `UC_TENANT`, `UC_USERNAME`, `UC_PASSWORD`
- Remove Tally env vars (if any)

### 6. Verify

- Check Railway logs for successful startup
- Hit the public URL and verify dashboard loads
- Trigger a manual sync and verify it completes

## Rollback Plan

Since the system isn't live:
1. Revert the merge: `git revert <merge_commit>` and push
2. Switch `DATABASE_URL` back to original Postgres
3. Railway auto-deploys the Tally version

Keep the old Postgres instance alive for at least 2 weeks after cutover.

## Nightly Sync on Railway

Set up a Railway cron job:
- Command: `cd src && PYTHONPATH=. python -m unicommerce.sync`
- Schedule: `30 20 * * *` (2 AM IST daily; Railway cron is UTC)
- Timeout: 10 minutes

## Environment Variables (Railway)

```
DATABASE_URL=<railway_uc_postgres_url>
UC_TENANT=ppetpl
UC_USERNAME=<username>
UC_PASSWORD=<password>
JWT_SECRET=<existing>
SMTP_HOST=<existing>
SMTP_PORT=<existing>
SMTP_USER=<existing>
SMTP_PASSWORD=<existing>
NOTIFICATION_EMAIL=<existing>
```

## Post-Cutover

- [ ] Verify nightly sync runs for 3 consecutive days
- [ ] Check email notifications arriving
- [ ] Review dashboard data with team
- [ ] Delete old Tally Postgres instance (after 2 weeks)
- [ ] Archive `src/extraction/` directory (remove from imports)
- [ ] Update CLAUDE.md: remove Tally API rules, add UC notes
