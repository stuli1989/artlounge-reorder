# Manual Sync Trigger — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only "Sync Now" button that triggers a full UC data refresh with live progress feedback.

**Architecture:** New `POST /api/sync/trigger` endpoint starts `run_nightly_sync()` in a background thread. A module-level progress dict in `ledger_sync.py` tracks the current step. The existing `GET /api/sync/status` endpoint is extended to return `is_running` and `current_step`. Frontend polls during sync and shows progress.

**Tech Stack:** Python/FastAPI (threading), React/TypeScript

**Spec:** `docs/superpowers/specs/2026-03-30-manual-sync-trigger-design.md`

---

## File Map

| File | Change |
|------|--------|
| `src/unicommerce/ledger_sync.py` | Add `_sync_progress` dict + `update_progress()` calls in `run_nightly_sync()` |
| `src/api/routes/sync_status.py` | Add `POST /sync/trigger`, extend GET response |
| `src/dashboard/src/lib/api.ts` | Add `triggerSync()` function |
| `src/dashboard/src/lib/types.ts` | Extend `SyncStatus` type |
| `src/dashboard/src/components/Layout.tsx` | Add "Sync Now" button for admins |
| `src/dashboard/src/components/mobile/MobileLayout.tsx` | Same for mobile |

---

### Task 1: Backend — Progress Tracking + Trigger Endpoint

**Files:**
- Modify: `src/unicommerce/ledger_sync.py`
- Modify: `src/api/routes/sync_status.py`

- [ ] **Step 1: Add progress tracking to `ledger_sync.py`**

Read the file. At the module level (near the top, after imports), add:

```python
import threading

# In-memory sync progress — read by the status endpoint
_sync_progress = {
    "running": False,
    "step": None,
    "error": None,
}
_sync_lock = threading.Lock()

def get_sync_progress() -> dict:
    """Read current sync progress (thread-safe)."""
    with _sync_lock:
        return dict(_sync_progress)

def _set_progress(step: str | None, running: bool = True, error: str | None = None):
    """Update sync progress (called from run_nightly_sync)."""
    with _sync_lock:
        _sync_progress["running"] = running
        _sync_progress["step"] = step
        _sync_progress["error"] = error
```

Then in `run_nightly_sync()` (~line 327), add `_set_progress()` calls at each step:

- Before Step 1 (line ~336): `_set_progress("Pulling catalog...")`
- Before Step 2 (line ~346): `_set_progress("Pulling transaction ledger...")`
- Before Step 3 (line ~371): `_set_progress("Pulling KG shipping packages...")`
- Before Step 4 (line ~379): `_set_progress("Pulling inventory snapshots...")`
- Before Step 5 (line ~389): `_set_progress("Running computation pipeline...")`
- Before Step 6 (line ~394): `_set_progress("Logging sync results...")`
- At the end (line ~416, after "SYNC COMPLETE"): `_set_progress(None, running=False)`
- In a try/except wrapper around the whole function, on exception: `_set_progress(None, running=False, error=str(e))`

Wrap the ENTIRE body of `run_nightly_sync` in try/finally to ensure progress is cleared on error:

```python
def run_nightly_sync(db_conn, days_back=OVERLAP_DAYS, dry_run=False):
    """Main nightly sync: pull ledger, load transactions, run pipeline."""
    try:
        _set_progress("Starting sync...")
        print("=== NIGHTLY LEDGER SYNC ===")
        # ... existing code with _set_progress calls at each step ...
        _set_progress(None, running=False)
    except Exception as e:
        _set_progress(None, running=False, error=str(e))
        raise
```

- [ ] **Step 2: Add trigger endpoint and extend status in `sync_status.py`**

Read the file. Add imports and the trigger endpoint:

```python
import threading
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from api.auth import get_current_user, require_role
from api.database import get_db
from unicommerce.ledger_sync import run_nightly_sync, get_sync_progress

@router.post("/sync/trigger")
def trigger_sync(user: dict = Depends(require_role("admin"))):
    """Manually trigger a full data sync. Admin only."""
    progress = get_sync_progress()
    if progress["running"]:
        raise HTTPException(409, "A sync is already running")

    def _run_sync():
        try:
            from extraction.data_loader import get_db_connection
            conn = get_db_connection()
            run_nightly_sync(conn)
            conn.close()
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Manual sync failed: %s", e)

    thread = threading.Thread(target=_run_sync, daemon=True)
    thread.start()

    return {"status": "started"}
```

Extend the existing `sync_status` GET endpoint response to include progress:

At the end of the function, before the return statement, add:

```python
    progress = get_sync_progress()
    result = {
        # ... existing fields ...
        "is_running": progress["running"],
        "current_step": progress["step"],
        "sync_error": progress["error"],
    }
    return result
```

Merge the progress fields into both the "never synced" and "has synced" return paths.

- [ ] **Step 3: Commit**

```bash
cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject"
git add src/unicommerce/ledger_sync.py src/api/routes/sync_status.py
git commit -m "feat: add manual sync trigger endpoint with progress tracking

POST /api/sync/trigger starts a full UC sync in background thread.
GET /api/sync/status now returns is_running and current_step.
Thread-safe progress dict in ledger_sync.py.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Frontend — Sync Now Button

**Files:**
- Modify: `src/dashboard/src/lib/types.ts`
- Modify: `src/dashboard/src/lib/api.ts`
- Modify: `src/dashboard/src/components/Layout.tsx`
- Modify: `src/dashboard/src/components/mobile/MobileLayout.tsx`

- [ ] **Step 1: Update types**

In `src/dashboard/src/lib/types.ts`, find `SyncStatus` interface and add:

```typescript
export interface SyncStatus {
  // ... existing fields ...
  is_running: boolean
  current_step: string | null
  sync_error: string | null
}
```

- [ ] **Step 2: Add triggerSync API call**

In `src/dashboard/src/lib/api.ts`, add:

```typescript
export const triggerSync = (): Promise<{ status: string }> =>
  api.post('/api/sync/trigger').then(r => r.data)
```

- [ ] **Step 3: Add Sync Now button to Layout.tsx**

Read the file. Find the header area where the sync indicator is (~line 94-98). Add a "Sync Now" button next to the sync indicator, visible only to admins.

```tsx
// Inside the header, near the sync indicator
{user?.role === 'admin' && sync && !sync.is_running && (
  <Button
    variant="ghost"
    size="sm"
    className="text-xs h-7 px-2"
    onClick={async () => {
      try {
        await triggerSync()
        queryClient.invalidateQueries({ queryKey: ['syncStatus'] })
      } catch (e: any) {
        if (e.response?.status === 409) {
          // already running, ignore
        }
      }
    }}
  >
    <RefreshCw className="h-3 w-3 mr-1" />
    Sync Now
  </Button>
)}
{sync?.is_running && (
  <div className="flex items-center gap-1.5 text-xs text-amber-600">
    <Loader2 className="h-3 w-3 animate-spin" />
    <span className="truncate max-w-[150px]">{sync.current_step || 'Syncing...'}</span>
  </div>
)}
```

Import `RefreshCw, Loader2` from lucide-react. Import `triggerSync` from api. Import `Button` from shadcn.

When sync is running, increase the poll frequency of the syncStatus query to 3 seconds:

Find the existing `useQuery` for syncStatus and make `refetchInterval` dynamic:

```typescript
const { data: sync } = useQuery({
  queryKey: ['syncStatus'],
  queryFn: fetchSyncStatus,
  refetchInterval: sync?.is_running ? 3000 : 60000,
  refetchIntervalInBackground: false,
})
```

Wait — this creates a circular reference (sync used in its own query config). Instead, use a state variable:

```typescript
const [syncRunning, setSyncRunning] = useState(false)

const { data: sync } = useQuery({
  queryKey: ['syncStatus'],
  queryFn: fetchSyncStatus,
  refetchInterval: syncRunning ? 3000 : 60000,
})

// Update syncRunning when data changes
useEffect(() => {
  if (sync) setSyncRunning(sync.is_running)
}, [sync?.is_running])
```

When sync transitions from running to not-running, invalidate all dashboard queries to refresh the data:

```typescript
useEffect(() => {
  if (sync && !sync.is_running && syncRunning) {
    // Sync just finished — refresh all data
    queryClient.invalidateQueries()
    setSyncRunning(false)
  }
}, [sync?.is_running])
```

- [ ] **Step 4: Add to MobileLayout.tsx**

Read the file. Add the same Sync Now button/progress indicator in the mobile header or drawer. Follow the same pattern as Layout.tsx but adapt for mobile layout.

- [ ] **Step 5: Build**

```bash
cd src/dashboard && npm run build 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject"
git add src/dashboard/src/lib/types.ts src/dashboard/src/lib/api.ts src/dashboard/src/components/Layout.tsx src/dashboard/src/components/mobile/MobileLayout.tsx
git commit -m "feat: Sync Now button in dashboard header for admins

Shows spinner + current step while syncing. Polls every 3s during sync.
Auto-refreshes all data when sync completes.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Push, Deploy, and Verify

- [ ] **Step 1: Push**

```bash
git push origin main
```

- [ ] **Step 2: Verify on Railway**

After deploy (~2 min):
1. Log in as admin at https://reorder.artlounge.in
2. See "Sync Now" button in the header
3. Click it — button should be replaced by spinner with step text
4. Wait for sync to complete (~5-10 min)
5. Dashboard data should refresh automatically
6. Sync indicator should update to "Synced [today's date]"

- [ ] **Step 3: Also import the latest Railway DB to local**

After the sync completes on Railway, pull the data locally:

```bash
# Same approach as earlier — COPY table by table from Railway to local
for table in app_settings stock_categories suppliers users channel_rules stock_items sync_log overrides override_audit_log transactions sku_metrics brand_metrics inventory_snapshots kg_demand drift_log; do
  echo "Copying $table..."
  PGPASSWORD=vASLgwlzeBzWIKCneufLWxQScFUJFjWE "/c/Program Files/PostgreSQL/17/bin/psql" \
    -h switchyard.proxy.rlwy.net -p 21840 -U postgres -d railway \
    -c "\COPY $table TO '/tmp/railway_${table}.csv' WITH CSV HEADER"
  PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" \
    -U reorder_app -d artlounge_reorder \
    -c "TRUNCATE $table CASCADE"
  PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" \
    -U reorder_app -d artlounge_reorder \
    -c "\COPY $table FROM '/tmp/railway_${table}.csv' WITH CSV HEADER"
  echo "  Done."
done

# Then daily_stock_positions (large table)
echo "Copying daily_stock_positions..."
PGPASSWORD=vASLgwlzeBzWIKCneufLWxQScFUJFjWE "/c/Program Files/PostgreSQL/17/bin/psql" \
  -h switchyard.proxy.rlwy.net -p 21840 -U postgres -d railway \
  -c "\COPY daily_stock_positions TO '/tmp/railway_positions.csv' WITH CSV HEADER"
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" \
  -U reorder_app -d artlounge_reorder \
  -c "TRUNCATE daily_stock_positions"
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" \
  -U reorder_app -d artlounge_reorder \
  -c "\COPY daily_stock_positions FROM '/tmp/railway_positions.csv' WITH CSV HEADER"
echo "Done."
```
