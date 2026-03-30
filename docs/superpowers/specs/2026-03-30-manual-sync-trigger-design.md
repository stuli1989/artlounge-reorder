# Manual Sync Trigger — Design Spec

## Problem

Admins have no way to trigger a data refresh from the UI. The nightly sync runs at 3:30 AM IST, but if big orders or cancellations happen during the day, the dashboard is stale until the next sync. Running a sync currently requires Railway CLI access or waiting for the cron.

## Design

### Backend

**New endpoint:** `POST /api/sync/trigger` (admin only)
- Starts `run_nightly_sync()` in a background thread
- Returns immediately: `{ "status": "started" }`
- Returns 409 Conflict if a sync is already running

**Extended status endpoint:** `GET /api/sync/status` (already exists)
- Add `is_running: bool` — is a sync currently in progress?
- Add `current_step: string | null` — e.g., "Pulling catalog...", "Running pipeline..."

**Progress tracking:** Module-level dict in `ledger_sync.py` that `run_nightly_sync()` updates at each step. The status endpoint reads it. Simple, no database writes needed for progress.

```python
# Module-level in ledger_sync.py
_sync_progress = {"running": False, "step": None}
```

### Frontend

**Header (Layout.tsx / MobileLayout.tsx):**
- Admin sees a "Sync Now" button near the sync indicator
- While running: spinner + step text, button disabled
- On complete: success/failure toast, auto-refresh queries
- Poll `/api/sync/status` every 3 seconds while running

### Safety

- Admin-only (`require_role("admin")`)
- Mutex: in-memory flag prevents double-triggers (409 if already running)
- Natural timeout: UC API calls have their own timeouts (~5-10 min)

### Files

| File | Change |
|------|--------|
| `src/api/routes/sync_status.py` | Add `POST /sync/trigger`, extend GET response with `is_running`, `current_step` |
| `src/unicommerce/ledger_sync.py` | Add `_sync_progress` dict, update it at each step in `run_nightly_sync()` |
| `src/dashboard/src/components/Layout.tsx` | Add "Sync Now" button for admins |
| `src/dashboard/src/components/mobile/MobileLayout.tsx` | Same for mobile |
| `src/dashboard/src/lib/api.ts` | Add `triggerSync()` function |
| `src/dashboard/src/lib/types.ts` | Extend `SyncStatus` with `is_running`, `current_step` |
