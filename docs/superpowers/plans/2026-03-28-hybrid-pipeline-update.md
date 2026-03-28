# Hybrid Pipeline Update — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the pipeline to use the proven hybrid formula: Transaction Ledger for supply + BHW demand (PICKLIST), Shipping Package API for KG demand, Inventory Snapshot for current sellable stock + drift monitoring. Forward walk from Day 0.

**Architecture:** Nightly sync pulls 4 data sources (Ledger, KG Shipping Packages, Inventory Snapshot, Catalog). Ledger transactions are loaded excluding INVOICES. KG PICKLIST is excluded from ledger (KG demand comes from SP instead). Pipeline forward-walks positions from Day 0. Current sellable stock uses snapshot `inventory` field. Drift check compares forward-walked closing vs snapshot and logs differences.

**Tech Stack:** Python 3, FastAPI, PostgreSQL, psycopg2, Unicommerce REST API

**Spec:** `docs/final-data-architecture.md`

---

## File Map

**Create:**
- `src/db/migrations/uc_003_hybrid_pipeline.sql` — new tables for snapshots + KG demand
- `tests/test_hybrid_reconciliation.py` — reconciliation tests for 13 proven SKUs

**Modify:**
- `src/unicommerce/client.py` — add inventory snapshot pull method
- `src/unicommerce/ledger_sync.py` — add snapshot + KG SP pulls to nightly sync, update backfill
- `src/unicommerce/ledger_parser.py` — exclude KG PICKLIST from ledger transactions
- `src/engine/pipeline.py` — current_stock from snapshot, merge KG demand, drift logging
- `src/engine/stock_position.py` — no change (forward walk stays)

---

### Task 1: Database Migration

**Files:**
- Create: `src/db/migrations/uc_003_hybrid_pipeline.sql`

- [ ] **Step 1: Write migration SQL**

```sql
BEGIN;

-- 1. Inventory snapshots from UC Snapshot API (nightly pull)
CREATE TABLE IF NOT EXISTS inventory_snapshots (
    id BIGSERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    inventory NUMERIC NOT NULL DEFAULT 0,
    inventory_blocked NUMERIC NOT NULL DEFAULT 0,
    bad_inventory NUMERIC NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_item_name, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_snap_sku ON inventory_snapshots(stock_item_name);

-- 2. KG demand from Shipping Package API
CREATE TABLE IF NOT EXISTS kg_demand (
    id BIGSERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    txn_date DATE NOT NULL,
    quantity NUMERIC NOT NULL,
    channel TEXT NOT NULL,
    shipping_package_code TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_item_name, shipping_package_code)
);
CREATE INDEX IF NOT EXISTS idx_kg_sku_date ON kg_demand(stock_item_name, txn_date);

-- 3. Drift log for monitoring
CREATE TABLE IF NOT EXISTS drift_log (
    id BIGSERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    check_date DATE NOT NULL,
    forward_walk_stock NUMERIC,
    snapshot_stock NUMERIC,
    drift NUMERIC,
    inventory_blocked NUMERIC,
    bad_inventory NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMIT;
```

- [ ] **Step 2: Run on local DB**

Run: `PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder_uc -f src/db/migrations/uc_003_hybrid_pipeline.sql`

- [ ] **Step 3: Commit**

---

### Task 2: UC Client — Inventory Snapshot Pull

**Files:**
- Modify: `src/unicommerce/client.py` — add method after `download_export_csv()`

- [ ] **Step 1: Add `pull_inventory_snapshots()` method**

Uses existing `_request()` to call `/services/rest/v1/inventory/inventorySnapshot/get`. Chunks SKU list into batches of 1000 (UC limit). Returns aggregated dict: `{sku: {inventory, blocked, bad}}`.

This method already exists as standalone code in `inventory.py` (now deleted) — reimplementing as a client method. Use the same chunking pattern.

- [ ] **Step 2: Test against live API**

Run a quick test pulling snapshot for 3 known SKUs, verify quantities match UC screenshots.

- [ ] **Step 3: Commit**

---

### Task 3: Sync — Add KG Shipping Package Pull

**Files:**
- Modify: `src/unicommerce/ledger_sync.py` — add `pull_and_load_kg_demand()` function

- [ ] **Step 1: Implement KG SP pull**

Pull ALL dispatched shipping packages from `PPETPLKALAGHODA` using existing `_request()` with `/services/rest/v1/oms/shippingPackage/search` (already proven working — 810 packages).

For each package: extract SKU, quantity, dispatch date (from `dispatched` epoch ms), channel (from `channel` field). Map UC channel to our taxonomy: CUSTOM_SHOP→store, CUSTOM→wholesale, MAGENTO2→online, etc.

Upsert into `kg_demand` table with `ON CONFLICT (stock_item_name, shipping_package_code) DO NOTHING`.

- [ ] **Step 2: Implement snapshot pull and store**

Pull inventory snapshot for all active SKUs across all facilities. Aggregate per SKU (sum across facilities). Upsert into `inventory_snapshots` table.

- [ ] **Step 3: Wire into nightly sync**

In `run_nightly_sync()`, after ledger pull (step 2) and before pipeline (step 3), add:
1. `pull_and_load_kg_demand(client, db_conn)`
2. `pull_and_store_snapshots(client, db_conn)`

Also wire into `run_backfill()` — pull full history of KG SP (updatedSinceInMinutes=525600) and current snapshot.

- [ ] **Step 4: Test locally**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --dry-run --days 3`

Verify KG SP and snapshot pulls succeed.

- [ ] **Step 5: Commit**

---

### Task 4: Ledger Parser — Exclude KG PICKLIST

**Files:**
- Modify: `src/unicommerce/ledger_parser.py`
- Modify: `src/unicommerce/ledger_sync.py` — update `_load_transactions()` to skip KG PICKLIST

- [ ] **Step 1: Update transaction loading**

In `_load_transactions()`, before inserting each row, skip if:
- `facility == 'PPETPLKALAGHODA'` AND `entity == 'PICKLIST'`

KG PICKLIST is incomplete (misses counter sales). KG demand comes from the `kg_demand` table instead.

Note: KG INVOICES are already excluded (all INVOICES excluded). KG non-demand entities (INBOUND_GATEPASS, INVENTORY_ADJUSTMENT) still load normally.

- [ ] **Step 2: Commit**

---

### Task 5: Pipeline — Use Snapshot for Current Stock + Merge KG Demand

**Files:**
- Modify: `src/engine/pipeline.py`

- [ ] **Step 1: Add helper functions**

```python
def fetch_latest_snapshot(db_conn):
    """Get latest inventory (sellable stock) per SKU from inventory_snapshots."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (stock_item_name)
                stock_item_name, inventory, inventory_blocked, bad_inventory
            FROM inventory_snapshots
            ORDER BY stock_item_name, snapshot_date DESC
        """)
        return {row[0]: {'inventory': float(row[1]), 'blocked': float(row[2]), 'bad': float(row[3])}
                for row in cur.fetchall()}

def fetch_kg_demand(db_conn):
    """Load KG shipping package demand, formatted as transaction dicts."""
    result = defaultdict(list)
    with db_conn.cursor() as cur:
        cur.execute("SELECT stock_item_name, txn_date, quantity, channel FROM kg_demand ORDER BY stock_item_name, txn_date")
        for row in cur.fetchall():
            result[row[0]].append({
                "date": row[1], "quantity": float(row[2]), "stock_change": -float(row[2]),
                "is_inward": False, "channel": row[3], "is_demand": True,
                "entity": "SHIPPING_PACKAGE", "entity_type": "KG_DISPATCH",
                "return_type": None, "facility": "PPETPLKALAGHODA", "amount": None,
            })
    return dict(result)
```

- [ ] **Step 2: Update `run_computation_pipeline()`**

Before the main SKU loop:
1. `snapshot_map = fetch_latest_snapshot(db_conn)` — for current sellable stock
2. `kg_demand_map = fetch_kg_demand(db_conn)` — for KG demand transactions

In the per-SKU loop:
1. Merge KG demand into transaction list: `txns = all_txns.get(sku) + kg_demand_map.get(sku, [])`, sorted by date
2. Forward walk positions as before (no change to position builder)
3. Set `current_stock` from snapshot: `m["current_stock"] = snapshot_map.get(sku, {}).get('inventory', forward_walked_stock)`

- [ ] **Step 3: Add drift logging**

After position building and before metrics upsert, for each SKU:
```python
fw_stock = positions[-1]["closing_qty"] if positions else 0
snap = snapshot_map.get(sku_name, {})
snap_physical = snap.get('inventory', 0) + snap.get('blocked', 0) + snap.get('bad', 0)
drift = fw_stock - snap_physical
if abs(drift) > 0.01:
    # Log to drift_log table
    log_drift(db_conn, sku_name, today, fw_stock, snap_physical, drift, snap.get('blocked', 0), snap.get('bad', 0))
```

Print drift summary after pipeline completes: total SKUs checked, matches, drifts, max drift.

- [ ] **Step 4: Test pipeline locally**

Run against local DB with existing data. Verify:
1. KG demand merges correctly
2. Current stock comes from snapshot
3. Drift log captures any differences

- [ ] **Step 5: Commit**

---

### Task 6: Historical Backfill — KG SP + Snapshots

**Files:**
- Modify: `src/unicommerce/ledger_sync.py` — update `run_backfill()`

- [ ] **Step 1: Add full KG SP backfill**

In `run_backfill()`, after loading ledger transactions:
1. Pull ALL KG shipping packages (updatedSinceInMinutes=525600, DISPATCHED)
2. Load into `kg_demand` table
3. Pull current inventory snapshot
4. Load into `inventory_snapshots` table

- [ ] **Step 2: Test backfill locally**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --backfill`

Verify: kg_demand table populated, inventory_snapshots has current data, pipeline runs with hybrid formula.

- [ ] **Step 3: Commit**

---

### Task 7: Integration Test — 13 SKU Reconciliation

**Files:**
- Create: `tests/test_hybrid_reconciliation.py`

- [ ] **Step 1: Write reconciliation test**

For each of the 13 proven SKUs, verify:
1. Forward-walked closing balance matches snapshot physical (within tolerance)
2. KG demand captured (SP quantities correct)
3. Current stock comes from snapshot `inventory` field
4. Drift logged for any differences

- [ ] **Step 2: Run locally and verify**

Expected: 12/13 exact matches, 1414644 drift of ~3 logged.

- [ ] **Step 3: Commit**

---

### Task 8: Deploy to Railway

- [ ] **Step 1: Run migration on Railway DB**
- [ ] **Step 2: Push to main (triggers Railway deploy)**
- [ ] **Step 3: Verify startup + first sync**
- [ ] **Step 4: Check drift log after first nightly sync**
- [ ] **Step 5: Monitor for 3 days**
