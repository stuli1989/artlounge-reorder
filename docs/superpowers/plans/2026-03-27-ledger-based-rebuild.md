# Ledger-Based Pipeline Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the multi-API Unicommerce data pipeline with a single-source-of-truth transaction ledger pipeline — no snapshots, no reconstruction, pure forward accumulation.

**Architecture:** Nightly Export Job API pulls transaction ledger CSVs per facility. Rows are parsed (INVOICES excluded), deduped, and loaded into a `transactions` table. Pipeline walks forward from day 0 to build positions, then computes velocity/classification/reorder. Smart recompute runs targeted phases on any frontend change.

**Tech Stack:** Python 3, FastAPI, PostgreSQL, psycopg2, Unicommerce REST API (Export Job endpoints)

**Spec:** `docs/superpowers/specs/2026-03-27-ledger-based-rebuild-design.md`

---

## File Map

**Create:**
- `src/db/migrations/uc_002_ledger_rebuild.sql` — schema migration
- `src/unicommerce/ledger_sync.py` — nightly sync orchestrator
- `src/unicommerce/ledger_parser.py` — CSV parsing + channel classification
- `src/api/routes/channel_rules.py` — CRUD for channel rules + recompute trigger
- `tests/test_ledger_parser.py` — parser unit tests
- `tests/test_export_job.py` — Export Job API integration tests
- `tests/test_pipeline_ledger.py` — pipeline with new schema tests
- `tests/test_channel_rules.py` — channel rules API tests

**Modify:**
- `src/unicommerce/client.py` — add Export Job methods (~50 lines)
- `src/engine/pipeline.py` — remove snapshot logic, update transaction fetching, add smart recompute params
- `src/engine/stock_position.py` — update transaction fetching, remove snapshot functions
- `src/engine/classification.py` — ABC revenue uses `stock_items.mrp * quantity` instead of `transactions.amount` (ledger has no amount)
- `src/engine/recalculate_buffers.py` — keep as-is (reads from sku_metrics, not transactions); used for smart recompute phases 5-6
- `src/api/main.py` — register channel_rules router
- `src/api/routes/skus.py` — swap name/sku_code display
- `src/api/routes/overrides.py` — trigger smart recompute on save
- `src/api/routes/suppliers.py` — trigger smart recompute on save (already uses recalculate_all_buffers)
- `src/api/routes/parties.py` — remove import of targeted_recompute, use pipeline smart recompute instead
- `src/api/routes/settings.py` — already uses recalculate_all_buffers, no change needed

**Delete:**
- `src/unicommerce/sync.py`
- `src/unicommerce/inventory.py`
- `src/unicommerce/orders.py`
- `src/unicommerce/returns.py`
- `src/unicommerce/inbound.py`
- `src/unicommerce/backfill.py`
- `src/unicommerce/transaction_loader.py`
- `src/unicommerce/ledger_import.py` (replaced by ledger_parser.py)
- `src/engine/targeted_recompute.py` (replaced by pipeline smart recompute)

---

### Task 1: Database Schema Migration

**Files:**
- Create: `src/db/migrations/uc_002_ledger_rebuild.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- uc_002_ledger_rebuild.sql
-- Ledger-based pipeline rebuild: single source of truth

BEGIN;

-- 1. Drop tables no longer needed
DROP TABLE IF EXISTS facility_inventory CASCADE;
DROP TABLE IF EXISTS daily_inventory_snapshots CASCADE;
DROP TABLE IF EXISTS return_items CASCADE;
DROP TABLE IF EXISTS returns CASCADE;
DROP TABLE IF EXISTS grn_receipts CASCADE;
DROP TABLE IF EXISTS facilities CASCADE;

-- 2. Recreate transactions table with ledger schema
DROP TABLE IF EXISTS transactions CASCADE;
CREATE TABLE transactions (
    id BIGSERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    txn_date DATE NOT NULL,
    entity TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_code TEXT NOT NULL DEFAULT '',
    txn_type TEXT NOT NULL CHECK (txn_type IN ('IN', 'OUT')),
    units NUMERIC NOT NULL DEFAULT 0,
    stock_change NUMERIC NOT NULL DEFAULT 0,
    facility TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'internal',
    is_demand BOOLEAN NOT NULL DEFAULT FALSE,
    sale_order_code TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_code, stock_item_name, txn_type, txn_date, units, facility)
);
CREATE INDEX idx_txn_sku ON transactions(stock_item_name);
CREATE INDEX idx_txn_date ON transactions(txn_date);
CREATE INDEX idx_txn_sku_date ON transactions(stock_item_name, txn_date);

-- 3. Drop snapshot-derived columns from sku_metrics
ALTER TABLE sku_metrics DROP COLUMN IF EXISTS open_purchase;
ALTER TABLE sku_metrics DROP COLUMN IF EXISTS bad_inventory;

-- 4. Update sync_log for ledger-based sync
ALTER TABLE sync_log DROP COLUMN IF EXISTS dispatches_synced;
ALTER TABLE sync_log DROP COLUMN IF EXISTS returns_synced;
ALTER TABLE sync_log DROP COLUMN IF EXISTS grns_synced;
ALTER TABLE sync_log DROP COLUMN IF EXISTS items_synced;
ALTER TABLE sync_log ADD COLUMN IF NOT EXISTS ledger_rows_loaded INT DEFAULT 0;
ALTER TABLE sync_log ADD COLUMN IF NOT EXISTS facilities_synced INT DEFAULT 0;

-- 5. Create channel_rules table
CREATE TABLE IF NOT EXISTS channel_rules (
    id SERIAL PRIMARY KEY,
    rule_type TEXT NOT NULL,
    match_value TEXT NOT NULL,
    facility_filter TEXT,
    channel TEXT NOT NULL,
    priority INT NOT NULL DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Seed default channel rules
INSERT INTO channel_rules (rule_type, match_value, channel, priority) VALUES
    ('entity', 'GRN', 'supplier', 100),
    ('entity', 'INVENTORY_ADJUSTMENT', 'internal', 90),
    ('entity', 'INBOUND_GATEPASS', 'internal', 90),
    ('entity', 'OUTBOUND_GATEPASS', 'internal', 90),
    ('entity', 'PUTAWAY_CANCELLED_ITEM', 'internal', 90),
    ('entity', 'PUTAWAY_PICKLIST_ITEM', 'internal', 90),
    ('entity', 'PUTAWAY_CIR', 'online', 80),
    ('entity', 'PUTAWAY_RTO', 'online', 80);

INSERT INTO channel_rules (rule_type, match_value, channel, priority) VALUES
    ('sale_order_prefix', 'MA-', 'online', 70),
    ('sale_order_prefix', 'B2C-', 'online', 70);

INSERT INTO channel_rules (rule_type, match_value, facility_filter, channel, priority) VALUES
    ('sale_order_prefix', 'SO', 'PPETPLKALAGHODA', 'store', 60),
    ('sale_order_prefix', 'SO', 'ppetpl', 'wholesale', 50);

-- Default fallback for PICKLIST with no matching rule
INSERT INTO channel_rules (rule_type, match_value, channel, priority) VALUES
    ('default', 'PICKLIST', 'wholesale', 0);

-- 7. Truncate positions and metrics for clean rebuild
TRUNCATE daily_stock_positions;
TRUNCATE sku_metrics;
TRUNCATE brand_metrics;

COMMIT;
```

- [ ] **Step 2: Run migration on local DB**

Run: `PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder_uc -f src/db/migrations/uc_002_ledger_rebuild.sql`

Expected: All statements succeed, no errors.

- [ ] **Step 3: Verify schema**

Run: `PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder_uc -c "\dt" -c "\d transactions" -c "\d channel_rules" -c "SELECT * FROM channel_rules ORDER BY priority DESC;"`

Expected: `transactions` has new columns, `channel_rules` has 13 seed rows, old tables gone.

- [ ] **Step 4: Commit**

```bash
git add src/db/migrations/uc_002_ledger_rebuild.sql
git commit -m "feat: schema migration for ledger-based rebuild"
```

---

### Task 2: Export Job API Methods on Client

**Files:**
- Modify: `src/unicommerce/client.py`
- Create: `tests/test_export_job.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_export_job.py
"""Integration test — requires live UC API credentials."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unicommerce.client import UnicommerceClient
from datetime import datetime, timedelta

def test_export_job_lifecycle():
    """Create export job, poll, download CSV."""
    client = UnicommerceClient()
    client.authenticate()
    client.discover_facilities()
    facility = client.facilities[0]

    # 2-day window ending yesterday
    end = datetime.now().replace(hour=23, minute=59, second=59)
    start = end - timedelta(days=2)
    start = start.replace(hour=0, minute=0, second=0)

    job_code = client.create_export_job(
        facility=facility,
        start_date=start,
        end_date=end,
    )
    assert job_code, "Job code should be returned"

    status, file_path = client.poll_export_job(job_code, facility=facility, timeout=120)
    assert status == "COMPLETE", f"Expected COMPLETE, got {status}"
    assert file_path, "File path should be returned"

    csv_text = client.download_export_csv(file_path)
    assert csv_text, "CSV should not be empty"
    lines = csv_text.strip().split('\n')
    assert 'SKU Code' in lines[0], f"Header should contain SKU Code: {lines[0]}"
    print(f"Downloaded {len(lines)-1} rows from {facility}")

if __name__ == "__main__":
    test_export_job_lifecycle()
    print("PASS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python ../tests/test_export_job.py`

Expected: `AttributeError: 'UnicommerceClient' object has no attribute 'create_export_job'`

- [ ] **Step 3: Add Export Job methods to client.py**

Add these methods to `UnicommerceClient` in `src/unicommerce/client.py` after the `iter_grn_codes` method:

```python
    # ------------------------------------------------------------------
    # Export Job API
    # ------------------------------------------------------------------

    # Note: UC API field is "exportColums" (missing 'n') — this is UC's typo, not ours
    _LEDGER_COLUMNS = [
        "skuCode", "skuName", "entity1", "entityType1", "entityCode",
        "entityStatus", "fromFacility", "toFacility", "units1",
        "inventoryUpdatedAt", "putawayCodes", "transactionTypes", "orderCode",
    ]

    def create_export_job(self, facility, start_date, end_date):
        """
        Create a Transaction Ledger export job for a facility.

        Args:
            facility: Facility code
            start_date: datetime — start of date range
            end_date: datetime — end of date range

        Returns:
            str: Job code for polling
        """
        start_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)

        payload = {
            "exportJobTypeName": "Transaction Ledger",
            "exportColums": self._LEDGER_COLUMNS,
            "exportFilters": [
                {"id": "addedOn", "dateRange": {"start": start_ms, "end": end_ms}}
            ],
            "frequency": "ONETIME",
        }

        data = self._request("POST", "/services/rest/v1/export/job/create",
                             json=payload, facility=facility, timeout=60)
        job_code = data.get("jobCode")
        logger.info("Export job created: %s (facility=%s)", job_code, facility)
        return job_code

    def poll_export_job(self, job_code, facility=None, timeout=300, poll_interval=3):
        """
        Poll export job status until COMPLETE or timeout.

        Returns:
            tuple: (status, file_path) — file_path is S3 URL when COMPLETE
        """
        start = time.time()
        while time.time() - start < timeout:
            data = self._request("POST", "/services/rest/v1/export/job/status",
                                 json={"jobCode": job_code}, facility=facility, timeout=60)
            status = data.get("status", "")
            if status == "COMPLETE":
                file_path = data.get("filePath", "")
                logger.info("Export job %s complete: %s", job_code, file_path)
                return status, file_path
            if status in ("FAILED", "ERROR"):
                logger.error("Export job %s failed: %s", job_code, data)
                return status, None
            time.sleep(poll_interval)

        logger.warning("Export job %s timed out after %ds", job_code, timeout)
        return "TIMEOUT", None

    def download_export_csv(self, s3_url):
        """Download CSV file from S3 URL returned by export job."""
        resp = self._session.get(s3_url, timeout=120)
        resp.raise_for_status()
        logger.info("Downloaded export CSV: %d bytes", len(resp.content))
        return resp.text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python ../tests/test_export_job.py`

Expected: `PASS` with "Downloaded N rows from ppetpl"

- [ ] **Step 5: Commit**

```bash
git add src/unicommerce/client.py tests/test_export_job.py
git commit -m "feat: add Export Job API methods to UnicommerceClient"
```

---

### Task 3: Ledger Parser Module

**Files:**
- Create: `src/unicommerce/ledger_parser.py`
- Create: `tests/test_ledger_parser.py`

- [ ] **Step 1: Write parser tests**

```python
# tests/test_ledger_parser.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unicommerce.ledger_parser import parse_ledger_row, is_excluded_entity

def test_picklist_out():
    row = {
        'SKU Code': "'2320617", 'SKU Name': 'WN PAC 60ML SILVER',
        'Entity': 'PICKLIST', 'Entity Type': 'MANUAL', 'Entity Code': 'PK385',
        'Entity Status': 'COMPLETE', 'From Facility': 'PPETPL Bhiwandi',
        'To Facility': '-', 'Units': '12.0000',
        'Inventory Updated At': '2026-03-20 14:30:00',
        'Putaway Codes': '-', 'Transaction Type': 'OUT', 'Sale Order Code': 'SO01234',
    }
    parsed = parse_ledger_row(row)
    assert parsed is not None
    assert parsed['sku_code'] == '2320617'
    assert parsed['stock_change'] == -12.0
    assert parsed['txn_type'] == 'OUT'
    assert parsed['entity'] == 'PICKLIST'
    assert parsed['is_demand'] is True
    assert parsed['facility'] == 'ppetpl'

def test_grn_in():
    row = {
        'SKU Code': "'6312", 'SKU Name': 'Eraser',
        'Entity': 'GRN', 'Entity Type': 'PUTAWAY_GRN_ITEM', 'Entity Code': 'G0719',
        'Entity Status': 'COMPLETE', 'From Facility': '-',
        'To Facility': 'PPETPL Bhiwandi', 'Units': '100.0000',
        'Inventory Updated At': '2026-03-24 15:31:28',
        'Putaway Codes': 'PT1392', 'Transaction Type': 'IN', 'Sale Order Code': '-',
    }
    parsed = parse_ledger_row(row)
    assert parsed['stock_change'] == 100.0
    assert parsed['txn_type'] == 'IN'
    assert parsed['is_demand'] is False

def test_inventory_adjustment_remove():
    row = {
        'SKU Code': "'138", 'SKU Name': 'Eraser',
        'Entity': 'INVENTORY_ADJUSTMENT', 'Entity Type': 'REMOVE', 'Entity Code': '-',
        'Entity Status': '-', 'From Facility': '-',
        'To Facility': 'Art Lounge Bhiwandi', 'Units': '-50.0000',
        'Inventory Updated At': '2026-03-24',
        'Putaway Codes': '-', 'Transaction Type': 'IN', 'Sale Order Code': '-',
    }
    parsed = parse_ledger_row(row)
    assert parsed['stock_change'] == -50.0  # units already negative, preserved
    assert parsed['txn_type'] == 'IN'
    assert parsed['facility'] == 'ALIBHIWANDI'

def test_invoices_excluded():
    assert is_excluded_entity('INVOICES') is True
    assert is_excluded_entity('PICKLIST') is False
    assert is_excluded_entity('GRN') is False

def test_empty_sku_returns_none():
    row = {
        'SKU Code': '', 'SKU Name': '', 'Entity': 'PICKLIST',
        'Entity Type': 'MANUAL', 'Entity Code': 'PK1', 'Entity Status': 'COMPLETE',
        'From Facility': 'PPETPL Bhiwandi', 'To Facility': '-', 'Units': '1',
        'Inventory Updated At': '2026-03-20', 'Putaway Codes': '-',
        'Transaction Type': 'OUT', 'Sale Order Code': '-',
    }
    assert parse_ledger_row(row) is None

def test_putaway_cir_is_not_demand():
    row = {
        'SKU Code': "'100", 'SKU Name': 'Item',
        'Entity': 'PUTAWAY_CIR', 'Entity Type': 'PUTAWAY_RECEIVED_RETURNS',
        'Entity Code': 'RP0029', 'Entity Status': 'COMPLETE',
        'From Facility': '-', 'To Facility': 'PPETPL Bhiwandi',
        'Units': '5.0000', 'Inventory Updated At': '2026-03-20',
        'Putaway Codes': '-', 'Transaction Type': 'IN', 'Sale Order Code': '-',
    }
    parsed = parse_ledger_row(row)
    assert parsed['is_demand'] is False
    assert parsed['stock_change'] == 5.0

if __name__ == "__main__":
    test_picklist_out()
    test_grn_in()
    test_inventory_adjustment_remove()
    test_invoices_excluded()
    test_empty_sku_returns_none()
    test_putaway_cir_is_not_demand()
    print("ALL PASS")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python ../tests/test_ledger_parser.py`

Expected: `ModuleNotFoundError: No module named 'unicommerce.ledger_parser'`

- [ ] **Step 3: Implement ledger_parser.py**

```python
# src/unicommerce/ledger_parser.py
"""
Parse UC Transaction Ledger CSVs into normalized transaction dicts.

Excludes INVOICES (billing documents, not physical movements).
Channel classification uses DB-backed rules table when available,
falls back to hardcoded defaults otherwise.
"""
import csv
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_EXCLUDED_ENTITIES = {"INVOICES"}

_FACILITY_MAP = {
    "PPETPL Bhiwandi": "ppetpl",
    "PPETPL Kala Ghoda": "PPETPLKALAGHODA",
    "Art Lounge Bhiwandi": "ALIBHIWANDI",
}

_DEMAND_ENTITY_TYPES = {"MANUAL", "SALE"}


def is_excluded_entity(entity):
    """Check if an entity type should be excluded from the pipeline."""
    return entity in _EXCLUDED_ENTITIES


def parse_ledger_row(row):
    """Parse a single CSV row into a normalized transaction dict.

    Returns None if the row should be skipped (empty SKU, bad date, excluded entity).
    """
    sku_code = row.get("SKU Code", "").lstrip("'").strip()
    if not sku_code:
        return None

    entity = row.get("Entity", "").strip()
    if is_excluded_entity(entity):
        return None

    entity_type = row.get("Entity Type", "").strip()
    entity_code = row.get("Entity Code", "").strip().rstrip(",")
    txn_type = row.get("Transaction Type", "").strip()  # IN or OUT
    from_facility = row.get("From Facility", "-").strip()
    to_facility = row.get("To Facility", "-").strip()
    sale_order = row.get("Sale Order Code", "-").strip().lstrip("'")

    units = float(row.get("Units", 0) or 0)

    # Parse date
    date_str = row.get("Inventory Updated At", "").strip()
    try:
        if " " in date_str:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date()
        else:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

    # Determine facility
    if txn_type == "OUT":
        facility_raw = from_facility
    else:
        facility_raw = to_facility
    facility = _FACILITY_MAP.get(facility_raw, facility_raw)

    # Compute stock_change (signed)
    if txn_type == "OUT":
        stock_change = -abs(units)
    else:
        stock_change = units  # preserves negative for REMOVE/REPLACE

    # Demand flag: only PICKLIST with MANUAL/SALE entity_type going OUT
    is_demand = (entity == "PICKLIST" and entity_type in _DEMAND_ENTITY_TYPES
                 and txn_type == "OUT")

    return {
        "sku_code": sku_code,
        "sku_name": row.get("SKU Name", "").strip(),
        "txn_date": txn_date,
        "entity": entity,
        "entity_type": entity_type,
        "entity_code": entity_code if entity_code != "-" else "",
        "txn_type": txn_type,
        "units": units,
        "stock_change": stock_change,
        "facility": facility,
        "is_demand": is_demand,
        "sale_order_code": sale_order if sale_order != "-" else None,
    }


def parse_ledger_csv(csv_text):
    """Parse CSV text content into a list of transaction dicts.

    Excludes INVOICES. Returns list sorted by txn_date.
    """
    rows = []
    reader = csv.DictReader(csv_text.splitlines())
    for row in reader:
        parsed = parse_ledger_row(row)
        if parsed:
            rows.append(parsed)
    rows.sort(key=lambda r: r["txn_date"])
    return rows


def parse_ledger_file(file_path):
    """Parse a CSV file from disk into a list of transaction dicts."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return parse_ledger_csv(f.read())


def classify_channel(parsed_row, rules=None):
    """Classify channel for a parsed transaction row.

    If rules are provided (from DB), apply them by priority (highest first).
    Otherwise use hardcoded defaults.

    Args:
        parsed_row: dict from parse_ledger_row()
        rules: list of channel_rules dicts, sorted by priority DESC (optional)

    Returns:
        str: channel name (supplier, wholesale, online, store, internal)
    """
    entity = parsed_row["entity"]
    sale_order = parsed_row.get("sale_order_code") or ""
    facility = parsed_row["facility"]

    if rules:
        for rule in rules:
            if not rule.get("is_active", True):
                continue

            rt = rule["rule_type"]
            mv = rule["match_value"]
            ff = rule.get("facility_filter")

            if rt == "entity" and entity == mv:
                return rule["channel"]
            if rt == "sale_order_prefix" and sale_order.startswith(mv):
                if ff and facility != ff:
                    continue
                return rule["channel"]
            if rt == "default" and entity == mv:
                return rule["channel"]

    # Hardcoded fallback (matches seed data)
    if entity == "GRN":
        return "supplier"
    if entity in ("INVENTORY_ADJUSTMENT", "INBOUND_GATEPASS", "OUTBOUND_GATEPASS",
                  "PUTAWAY_CANCELLED_ITEM", "PUTAWAY_PICKLIST_ITEM"):
        return "internal"
    if entity in ("PUTAWAY_CIR", "PUTAWAY_RTO"):
        return "online"
    if entity == "PICKLIST":
        if sale_order.startswith("MA-") or sale_order.startswith("B2C-"):
            return "online"
        if "KALAGHODA" in facility.upper():
            return "store"
        return "wholesale"
    return "internal"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python ../tests/test_ledger_parser.py`

Expected: `ALL PASS`

- [ ] **Step 5: Commit**

```bash
git add src/unicommerce/ledger_parser.py tests/test_ledger_parser.py
git commit -m "feat: ledger parser module with channel classification"
```

---

### Task 4: Pipeline Refactor — Transaction Fetching & Smart Recompute

**Files:**
- Modify: `src/engine/pipeline.py`
- Modify: `src/engine/stock_position.py`

This task updates the pipeline to read from the new `transactions` schema and adds smart recompute support.

- [ ] **Step 1: Update `fetch_all_transactions()` in pipeline.py**

Replace the existing `fetch_all_transactions` function (around line 380-397) with this exact mapping:

```python
def fetch_all_transactions(db_conn):
    """Read all transactions from ledger-based schema, mapped to pipeline dict format."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT stock_item_name, txn_date, stock_change, txn_type,
                   entity, entity_type, channel, is_demand, facility
            FROM transactions ORDER BY stock_item_name, txn_date
        """)
        by_sku = defaultdict(list)
        for row in cur.fetchall():
            by_sku[row[0]].append({
                "date": row[1],
                "quantity": abs(row[2]),
                "is_inward": row[3] == "IN",
                "channel": row[6],
                "return_type": "CIR" if row[4] == "PUTAWAY_CIR"
                          else "RTO" if row[4] == "PUTAWAY_RTO" else None,
                "voucher_type": row[4],
                "entity": row[4],
                "entity_type": row[5],
                "is_demand": row[7],
                "facility": row[8],
                "amount": None,
            })
        return by_sku
```

**Key mapping:** new `stock_change` (signed) -> `quantity` (abs) + `is_inward` (bool). The position builder and velocity modules expect this format.

- [ ] **Step 2: Replace `fetch_latest_snapshot_bulk()` with position-based current_stock**

Delete `fetch_all_snapshots()` and `fetch_latest_snapshot_bulk()`. Add:

```python
def fetch_current_stock_from_positions(db_conn):
    """Get latest closing_qty per SKU from daily_stock_positions."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (stock_item_name)
                stock_item_name, closing_qty
            FROM daily_stock_positions
            ORDER BY stock_item_name, position_date DESC
        """)
        return {row[0]: float(row[1]) for row in cur.fetchall()}
```

Replace every call to `fetch_latest_snapshot_bulk()` with this function.

- [ ] **Step 3: Fix ABC revenue — use mrp from stock_items**

The ledger has no `amount` column. In `src/engine/classification.py`, update `compute_abc_classification()`:

```python
def compute_abc_classification(metrics_batch, all_txns, a_threshold=0.80, b_threshold=0.95, mrp_lookup=None):
    """F17: Classify SKUs by revenue. Revenue = quantity * mrp (from catalog)."""
    revenue_by_sku = {}
    for m in metrics_batch:
        sku = m["stock_item_name"]
        txns = all_txns.get(sku, [])
        total_rev = 0.0
        mrp = float(mrp_lookup.get(sku, 0)) if mrp_lookup else 0
        for t in txns:
            if t.get("is_demand") and not t.get("is_inward", True):
                total_rev += t.get("quantity", 0) * mrp
        revenue_by_sku[sku] = total_rev
    # ... rest of ABC ranking logic unchanged
```

In pipeline.py, build and pass `mrp_lookup`:
```python
with db_conn.cursor() as cur:
    cur.execute("SELECT sku_code, COALESCE(mrp, 0) FROM stock_items WHERE mrp IS NOT NULL")
    mrp_lookup = {row[0]: float(row[1]) for row in cur.fetchall()}
compute_abc_classification(metrics_batch, all_txns, mrp_lookup=mrp_lookup)
```

- [ ] **Step 4: Remove `open_purchase` and `bad_inventory` from ALL pipeline locations**

Search pipeline.py for these strings. Remove from:
- `_empty_metrics()` dict (2 keys)
- `_SKU_METRICS_DEFAULTS` dict (2 keys)
- `_SKU_METRICS_UPSERT_SQL` — remove from INSERT column list AND ON CONFLICT UPDATE SET clause
- Any `m["open_purchase"] = ...` or `m["bad_inventory"] = ...` assignments

- [ ] **Step 5: Update `detect_import_history()` in reorder.py**

The function reads `t.get("party_name")` for `last_import_supplier`. The ledger has no party name. Change to:
```python
last_import_supplier = ""  # ledger has no vendor name
```

- [ ] **Step 6: Update `fetch_transactions_for_item()` in stock_position.py**

Replace query to read new columns, mapped to the same dict format as `fetch_all_transactions()`. Remove `fetch_snapshot_dates_for_item()`, `build_positions_from_snapshots()`, and `_build_positions_for_date()`.

- [ ] **Step 7: Update position builder to start from 0 (no snapshot anchoring)**

The existing `build_daily_positions_from_snapshots_and_txns()` in stock_position.py uses snapshot as anchor. Pass empty dict `{}` for snapshots. If the function computes `opening = snapshot - net_movements`, modify it to start from 0 when no snapshots exist:
```python
if not snapshot_by_date:
    opening_balance = 0  # ledger starts from zero
```

- [ ] **Step 8: Add smart recompute to pipeline entry point**

Update `run_computation_pipeline` signature:
```python
def run_computation_pipeline(db_conn, incremental=False, phases=None, scope=None):
    """
    phases: list of phase numbers to run, e.g. [5, 6]. None = all phases (1-6).
    scope: dict with optional keys:
        - 'sku': single SKU name to recompute
        - 'brand': brand/category name to recompute
    Phase numbering: 1=positions, 2=flat velocity, 3=ABC/XYZ, 4=WMA+trend, 5=buffer+reorder, 6=rollups
    """
```

Wrap each phase in `if phases is None or N in phases:`. When `scope` is set, filter `stock_items` list before entering the per-SKU loop. For phases 5-6 only (buffer/reorder), the existing `recalculate_all_buffers()` in `recalculate_buffers.py` already handles this — keep it as the fast path for buffer/supplier changes.

- [ ] **Step 9: Test pipeline compiles and runs**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -c "from engine.pipeline import run_computation_pipeline; print('OK')"`

Expected: `OK` (no import errors)

- [ ] **Step 6: Commit**

```bash
git add src/engine/pipeline.py src/engine/stock_position.py
git commit -m "feat: pipeline reads new transaction schema, smart recompute support"
```

---

### Task 5: Ledger Sync Orchestrator

**Files:**
- Create: `src/unicommerce/ledger_sync.py`

- [ ] **Step 1: Implement ledger_sync.py**

```python
# src/unicommerce/ledger_sync.py
"""
Nightly sync orchestrator — pulls transaction ledger via Export Job API,
parses, loads into transactions table, runs pipeline.

Usage:
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --backfill
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --dry-run
"""
import argparse
import logging
import os
import glob
from datetime import datetime, timedelta, date

import psycopg2.extras

from unicommerce.client import UnicommerceClient
from unicommerce.ledger_parser import parse_ledger_csv, parse_ledger_file, classify_channel
from unicommerce.catalog import pull_all_skus, load_catalog
from engine.pipeline import run_computation_pipeline
from extraction.data_loader import get_db_connection
from config.settings import UC_FACILITIES_FALLBACK

logger = logging.getLogger(__name__)

OVERLAP_DAYS = 3
BACKFILL_WINDOW_DAYS = 90  # Export Job API max is 92


def _fetch_channel_rules(db_conn):
    """Load active channel rules from DB, sorted by priority DESC."""
    with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT rule_type, match_value, facility_filter, channel, priority
            FROM channel_rules WHERE is_active = TRUE
            ORDER BY priority DESC
        """)
        return cur.fetchall()


def _load_transactions(db_conn, parsed_rows, rules):
    """Classify channels and upsert parsed rows into transactions table."""
    if not parsed_rows:
        return 0

    for row in parsed_rows:
        row["channel"] = classify_channel(row, rules)

    sql = """
        INSERT INTO transactions
            (stock_item_name, txn_date, entity, entity_type, entity_code,
             txn_type, units, stock_change, facility, channel, is_demand, sale_order_code)
        VALUES
            (%(sku_code)s, %(txn_date)s, %(entity)s, %(entity_type)s, %(entity_code)s,
             %(txn_type)s, %(units)s, %(stock_change)s, %(facility)s, %(channel)s,
             %(is_demand)s, %(sale_order_code)s)
        ON CONFLICT (entity_code, stock_item_name, txn_type, txn_date, units, facility)
        DO NOTHING
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, parsed_rows, page_size=1000)
    db_conn.commit()
    return len(parsed_rows)


def pull_ledger_for_facility(client, facility, start_date, end_date):
    """Pull transaction ledger CSV for one facility via Export Job API.

    Returns parsed rows list, or empty list on failure.
    """
    try:
        job_code = client.create_export_job(facility, start_date, end_date)
        status, file_path = client.poll_export_job(job_code, facility=facility, timeout=300)

        if status != "COMPLETE" or not file_path:
            logger.error("Export job %s for %s: status=%s", job_code, facility, status)
            return []

        csv_text = client.download_export_csv(file_path)
        rows = parse_ledger_csv(csv_text)
        logger.info("Facility %s: %d rows parsed", facility, len(rows))
        return rows

    except Exception as e:
        logger.error("Failed to pull ledger for %s: %s", facility, e)
        return []


def run_nightly_sync(db_conn, days_back=OVERLAP_DAYS, dry_run=False):
    """Main nightly sync: pull ledger, load transactions, run pipeline."""
    print("=== NIGHTLY LEDGER SYNC ===")

    client = UnicommerceClient()
    client.authenticate()
    client.discover_facilities()

    # 1. Pull catalog
    print("Step 1: Pulling catalog...")
    try:
        skus = pull_all_skus(client)
        if skus and not dry_run:
            load_catalog(db_conn, skus)
            print(f"  Catalog: {len(skus)} SKUs loaded")
    except Exception as e:
        print(f"  Catalog pull failed: {e} (continuing)")

    # 2. Pull ledger per facility
    print(f"Step 2: Pulling ledger (last {days_back} days)...")
    end_dt = datetime.now().replace(hour=23, minute=59, second=59)
    start_dt = (end_dt - timedelta(days=days_back)).replace(hour=0, minute=0, second=0)

    rules = _fetch_channel_rules(db_conn)
    total_loaded = 0
    facilities_ok = 0

    for facility in client.facilities:
        rows = pull_ledger_for_facility(client, facility, start_dt, end_dt)
        if rows:
            if not dry_run:
                loaded = _load_transactions(db_conn, rows, rules)
                total_loaded += loaded
            else:
                total_loaded += len(rows)
            facilities_ok += 1
            print(f"  {facility}: {len(rows)} rows")
        else:
            print(f"  {facility}: FAILED or empty")

    print(f"  Total: {total_loaded} rows loaded, {facilities_ok}/{len(client.facilities)} facilities OK")

    # 3. Run pipeline
    if not dry_run:
        print("Step 3: Running pipeline...")
        run_computation_pipeline(db_conn)
        print("  Pipeline complete")

    # 4. Log sync
    if not dry_run:
        with db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sync_log (source, sync_started, sync_completed, status,
                                      ledger_rows_loaded, facilities_synced)
                VALUES ('ledger', NOW() - INTERVAL '1 minute', NOW(), 'completed', %s, %s)
            """, (total_loaded, facilities_ok))
        db_conn.commit()

    # 5. Email notification
    try:
        from config.settings import SMTP_HOST, NOTIFY_EMAIL
        if SMTP_HOST and NOTIFY_EMAIL:
            _send_sync_email(total_loaded, facilities_ok, len(client.facilities))
    except Exception as e:
        logger.warning("Email notification failed: %s", e)

    print("=== SYNC COMPLETE ===")


def run_backfill(db_conn, from_csv_dir=None):
    """Historical backfill — either from API (92-day windows) or from CSV directory."""
    print("=== HISTORICAL BACKFILL ===")

    rules = _fetch_channel_rules(db_conn)

    if from_csv_dir:
        # Load from local CSV files
        files = sorted(glob.glob(os.path.join(from_csv_dir, "**", "*.csv"), recursive=True))
        print(f"Loading {len(files)} CSV files from {from_csv_dir}")
        total = 0
        for f in files:
            rows = parse_ledger_file(f)
            loaded = _load_transactions(db_conn, rows, rules)
            total += loaded
            print(f"  {os.path.basename(f)}: {loaded} rows")
        print(f"Total loaded: {total}")
    else:
        # Pull from API in 90-day windows
        client = UnicommerceClient()
        client.authenticate()
        client.discover_facilities()

        # Jun 7 2025 to today
        start = datetime(2025, 6, 1)
        end = datetime.now()
        total = 0

        window_start = start
        while window_start < end:
            window_end = min(window_start + timedelta(days=BACKFILL_WINDOW_DAYS),
                            end)
            start_dt = window_start.replace(hour=0, minute=0, second=0)
            end_dt = window_end.replace(hour=23, minute=59, second=59)

            print(f"\nWindow: {start_dt.date()} to {end_dt.date()}")
            for facility in client.facilities:
                rows = pull_ledger_for_facility(client, facility, start_dt, end_dt)
                if rows:
                    loaded = _load_transactions(db_conn, rows, rules)
                    total += loaded
                    print(f"  {facility}: {loaded} rows")

            window_start = window_end + timedelta(days=1)

        print(f"\nTotal loaded: {total}")

    # Run full pipeline
    print("\nRunning full pipeline...")
    run_computation_pipeline(db_conn)
    print("=== BACKFILL COMPLETE ===")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="Ledger-based sync")
    parser.add_argument("--backfill", action="store_true", help="Run historical backfill from API")
    parser.add_argument("--backfill-csv", type=str, help="Backfill from local CSV directory")
    parser.add_argument("--dry-run", action="store_true", help="Pull data but don't write to DB")
    parser.add_argument("--days", type=int, default=OVERLAP_DAYS, help="Days to look back (default 3)")
    args = parser.parse_args()

    db_conn = get_db_connection()
    try:
        if args.backfill:
            run_backfill(db_conn)
        elif args.backfill_csv:
            run_backfill(db_conn, from_csv_dir=args.backfill_csv)
        else:
            run_nightly_sync(db_conn, days_back=args.days, dry_run=args.dry_run)
    finally:
        db_conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test dry-run mode**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --dry-run --days 2`

Expected: Authenticates, pulls ledger for 3 facilities, shows row counts, does NOT write to DB.

- [ ] **Step 3: Commit**

```bash
git add src/unicommerce/ledger_sync.py
git commit -m "feat: ledger sync orchestrator with backfill support"
```

---

### Task 6: Channel Rules API

**Files:**
- Create: `src/api/routes/channel_rules.py`
- Modify: `src/api/main.py` — register router

- [ ] **Step 1: Implement channel_rules.py**

Endpoints:
- `GET /api/channel-rules` — list all active rules
- `POST /api/channel-rules` — create rule
- `PUT /api/channel-rules/{rule_id}` — update rule
- `DELETE /api/channel-rules/{rule_id}` — deactivate rule
- `POST /api/channel-rules/recompute` — trigger full pipeline recompute (background)

Each mutation endpoint (POST, PUT, DELETE) triggers a smart recompute after saving:
- Channel rule changes → full pipeline (phases 1-6), run as background task
- Returns immediately with `{"status": "recomputing"}`

- [ ] **Step 2: Register router in main.py**

Add to `src/api/main.py`:
```python
from api.routes.channel_rules import router as channel_rules_router
app.include_router(channel_rules_router, prefix="/api")
```

- [ ] **Step 3: Test via curl**

Run: `curl http://localhost:8000/api/channel-rules`

Expected: JSON list of 13 seed rules.

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/channel_rules.py src/api/main.py
git commit -m "feat: channel rules CRUD API with recompute trigger"
```

---

### Task 7: Smart Recompute on All Frontend Changes

**Files:**
- Modify: `src/api/routes/overrides.py` — trigger phases 5-6 on override save
- Modify: `src/api/routes/suppliers.py` — trigger phases 5-6 on lead time/buffer change

- [ ] **Step 1: Add recompute triggers**

In `overrides.py` POST endpoint, after saving the override, call:
```python
run_computation_pipeline(db_conn, phases=[5, 6], scope={"sku": req.stock_item_name})
```

In `suppliers.py` PUT endpoint, after saving supplier changes, call:
```python
run_computation_pipeline(db_conn, phases=[5, 6], scope={"brand": supplier_name})
```

- [ ] **Step 2: Verify existing app_settings changes also trigger recompute**

Check if there's an existing settings endpoint. If not, note for future — when settings change (buffer matrix, thresholds), phases 2-6 should run.

- [ ] **Step 3: Test override triggers recompute**

Create an override via API, verify sku_metrics updates immediately.

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/overrides.py src/api/routes/suppliers.py
git commit -m "feat: smart recompute triggers on override and supplier changes"
```

---

### Task 8: Delete Old Files

**Files:**
- Delete: 7 unicommerce modules

- [ ] **Step 1: Delete old modules**

```bash
git rm src/unicommerce/sync.py
git rm src/unicommerce/inventory.py
git rm src/unicommerce/orders.py
git rm src/unicommerce/returns.py
git rm src/unicommerce/inbound.py
git rm src/unicommerce/backfill.py
git rm src/unicommerce/transaction_loader.py
git rm src/unicommerce/ledger_import.py
git rm src/engine/targeted_recompute.py
```

- [ ] **Step 2: Remove imports of deleted modules**

Search for any remaining imports of the deleted modules in `src/` and remove them. Key locations:
- `src/api/routes/parties.py` line 87: `from engine.targeted_recompute import recompute_skus_for_party` — remove this import and replace the recompute call with `run_computation_pipeline(db_conn, phases=[1,2,3,4,5,6], scope={"party": party_name})` or just the full pipeline.

- [ ] **Step 3: Verify no broken imports**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -c "from unicommerce.ledger_sync import run_nightly_sync; from engine.pipeline import run_computation_pipeline; from api.main import app; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove old multi-API modules replaced by ledger pipeline"
```

---

### Task 9: End-to-End Integration Test

**Files:**
- Create: `tests/test_integration_ledger.py`

- [ ] **Step 1: Run schema migration** (if not done already)

- [ ] **Step 2: Run historical backfill from existing CSV files**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --backfill-csv ../transactionLedger`

Expected: All 23+ CSV files loaded, pipeline runs, sku_metrics populated.

- [ ] **Step 3: Verify reconciliation**

Run the verify_ledger.py script (from investigation) to confirm ledger-derived closing balances match UC snapshot for test SKUs.

- [ ] **Step 4: Run nightly sync (live API)**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --days 3`

Expected: Pulls 3-day ledger from all 3 facilities, dedup handles overlaps, pipeline recomputes.

- [ ] **Step 5: Start API and verify dashboard**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000`

Verify:
- `http://localhost:8000/api/brands` returns brand metrics
- `http://localhost:8000/api/channel-rules` returns seed rules
- Dashboard shows SKU data with correct names and Part No

- [ ] **Step 6: Test channel rule change triggers recompute**

```bash
# Change a rule
curl -X PUT http://localhost:8000/api/channel-rules/1 -H 'Content-Type: application/json' -d '{"channel": "internal"}'

# Verify metrics updated
curl http://localhost:8000/api/brands | head
```

- [ ] **Step 7: Commit test file**

```bash
git add tests/
git commit -m "test: end-to-end integration tests for ledger pipeline"
```

---

### Task 10: Frontend Updates (SKU Display)

**Files:**
- Modify: `src/api/routes/skus.py` — ensure name shown as title, sku_code as Part No
- Modify: Dashboard components that display SKU info

- [ ] **Step 1: Verify current API response format**

Check what `GET /api/brands/{brand}/skus` returns. Ensure `stock_item_name` contains the SKU code and `part_no` (or `name` from stock_items join) contains the display name.

- [ ] **Step 2: Update API query if needed**

The SKU list query in `skus.py` should join with `stock_items` to return both `sku_code` (as Part No) and `name` (as display title). The frontend then shows `name` prominently and `sku_code` as "Part No".

- [ ] **Step 3: Update frontend components**

In dashboard components (CriticalSkus.tsx, DeadStock.tsx, SKU detail pages):
- Show `name` (display name) as the title
- Show `sku_code` as "Part No" in secondary text

- [ ] **Step 4: Build and test frontend**

Run: `cd src/dashboard && npm run build`

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/skus.py src/dashboard/
git commit -m "feat: show product name as title, SKU code as Part No"
```
