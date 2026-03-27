# Ledger-Based Pipeline Rebuild

## Problem

The current Unicommerce integration pulls data from multiple API endpoints (dispatches, returns, GRNs, inventory snapshots) and reconstructs stock positions using snapshot anchoring. This creates multiple sources of truth, reconstruction logic, and data that doesn't reconcile cleanly.

## Solution

Replace everything with a single data source: the **UC Transaction Ledger**. The ledger contains every physical inventory movement since UC was set up (June 2025). We proved through investigation that `sum(all non-INVOICE movements from 0) = UC physical inventory` exactly (14/14 facility-SKU pairs matched at zero diff).

## Key Findings (from investigation)

1. **INVOICES entity must be excluded** — these are billing/order documents, not physical stock movements. Including them causes massive negative balances. Excluding them reconciles perfectly.
2. **The ledger starts from zero** — initial stock loads appear as `INVENTORY_ADJUSTMENT ADD` entries on Jun 7, 2025.
3. **No snapshots needed** — the ledger is the complete source of truth. Snapshot fields like `inventoryBlocked` and `putawayPending` represent transient in-flight states irrelevant to a reorder system operating on 30-90 day lead times.
4. **Export Job API works** — `POST /services/rest/v1/export/job/create` with `exportJobTypeName: "Transaction Ledger"` produces identical CSVs to the manual UI export. ~15 seconds per facility. Note: the API field name `exportColums` is a known typo in UC's API (missing 'n') — this is intentional, not a bug in our code.
5. **Three facilities, no overlap** — monthly files = PPETPL Bhiwandi, 153xxx files = Kala Ghoda, 191xxx files = Ali Bhiwandi. Cross-facility transfer counterparts (INBOUND/OUTBOUND_GATEPASS) net to zero when aggregated.

## Architecture

```
Nightly: UC Export Job API (per facility, last 3 days)
    |
    v
Transaction Ledger CSV (downloaded from S3)
    |
    v
Parse -> exclude INVOICES -> dedup -> transactions table
    |
    v
Walk forward from day 0 -> daily_stock_positions
    |
    v
Velocity, ABC/XYZ, reorder -> sku_metrics
    |
    v
Brand rollups -> brand_metrics
    |
    v
FastAPI -> React dashboard
```

One data source. One pipeline. No reconstruction, no anchoring, no snapshots.

## Export Job API

**Create job:** `POST /services/rest/v1/export/job/create`

```json
{
  "exportJobTypeName": "Transaction Ledger",
  "exportColums": [
    "skuCode", "skuName", "entity1", "entityType1", "entityCode",
    "entityStatus", "fromFacility", "toFacility", "units1",
    "inventoryUpdatedAt", "putawayCodes", "transactionTypes", "orderCode"
  ],
  "exportFilters": [
    {
      "id": "addedOn",
      "dateRange": {
        "start": <epoch_ms>,
        "end": <epoch_ms>
      }
    }
  ],
  "frequency": "ONETIME"
}
```

- Requires `Facility` header per request (one job per facility)
- Max 92 days per request
- Date values in epoch milliseconds

**Poll status:** `POST /services/rest/v1/export/job/status` with `{"jobCode": "..."}`. Status goes SCHEDULED -> COMPLETE. Response includes `filePath` (S3 URL to download CSV).

## Nightly Sync Flow

`run_nightly_sync()` in `ledger_sync.py`:

1. **Authenticate** with UC API
2. **Pull catalog** via `catalog.py` (keeps `stock_items` and `stock_categories` current)
3. **Pull transaction ledger** for each of 3 facilities:
   - Create Export Job (last 3 days window for overlap safety)
   - Poll until COMPLETE (max 5 min timeout)
   - Download CSV from S3
   - Parse rows, exclude INVOICES, load into `transactions` with dedup
4. **Run pipeline** (full recompute, phases 1-6)
5. **Log result** to `sync_log`
6. **Send email notification** on success/failure

**Historical backfill** (one-time): Pull full history via Export Job API (92-day windows, ~4 requests per facility = 12 total, ~3 minutes). Same parse -> dedup -> load path as nightly. No manual CSV files involved.

**Day 0 definition:** The pipeline starts positions from the earliest transaction date in the DB (Jun 7, 2025 — when UC was set up and initial stock loads occurred). Days before the first transaction for any SKU have no positions. There is no configurable FY start date for positions — the ledger defines the start.

## Database Schema

### Tables retained (modified)

**transactions** — all physical movements from ledger

| Column | Type | Notes |
|--------|------|-------|
| id | BIGSERIAL | Primary key |
| stock_item_name | TEXT | SKU code (e.g., "2320617") |
| txn_date | DATE | Date of movement |
| entity | TEXT | GRN, PICKLIST, INVENTORY_ADJUSTMENT, etc. |
| entity_type | TEXT | MANUAL, SALE, PUTAWAY_GRN_ITEM, etc. |
| entity_code | TEXT | PK385, G0719, etc. |
| txn_type | TEXT | IN or OUT |
| units | NUMERIC | Raw quantity from CSV (always positive except REMOVE/REPLACE) |
| stock_change | NUMERIC | Signed: for OUT → -abs(units); for IN → units (preserves negative for REMOVE) |
| facility | TEXT | ppetpl, PPETPLKALAGHODA, ALIBHIWANDI |
| channel | TEXT | supplier, wholesale, online, store, internal |
| is_demand | BOOLEAN | True for PICKLIST (MANUAL/SALE entity_type) OUT only |
| sale_order_code | TEXT | SO*, MA-*, B2C-* (nullable) |
| created_at | TIMESTAMPTZ | DEFAULT NOW() — when row was loaded |

Dedup key: `UNIQUE(entity_code, stock_item_name, txn_type, txn_date, units, facility)` — adding `facility` prevents false dedup when the same entity_code appears at multiple facilities (e.g., GATEPASS counterparts).

**stock_change truth table:**

| txn_type | entity_type | units | stock_change | Example |
|----------|------------|-------|-------------|---------|
| OUT | MANUAL | 12 | -12 | PICKLIST pick |
| IN | PUTAWAY_GRN_ITEM | 100 | +100 | GRN receipt |
| IN | ADD | 500 | +500 | Initial stock load |
| IN | REMOVE | -50 | -50 | Stock correction (units already negative in CSV) |
| IN | REPLACE | -10 | -10 | Stock replacement correction |
| IN | PUTAWAY_RECEIVED_RETURNS | 5 | +5 | CIR/RTO return inward |

**daily_stock_positions** — no schema change, built by forward walk from transactions

**sku_metrics** — drop `open_purchase` and `bad_inventory` columns (were snapshot-derived, migration `uc_002` handles this). `current_stock` now comes from latest `daily_stock_positions.closing_qty`.

**brand_metrics** — no change

**stock_items** — no schema change. `name` = display name (shown as title in UI), `sku_code` = part number (shown as "Part No" in UI)

**stock_categories**, **suppliers**, **overrides**, **override_audit_log**, **app_settings**, **users** — no change

**sync_log** — drop old columns `dispatches_synced`, `returns_synced`, `grns_synced` (from multi-API era). Replace with `ledger_rows_loaded` (total rows across facilities) and `facilities_synced` (count of successful facility pulls).

**parties** — retained but no longer connected to the core pipeline (ledger transactions have no party/customer name). Kept for reference and potential future use.

### Tables dropped

| Table | Reason |
|-------|--------|
| daily_inventory_snapshots | No longer pulling snapshots |
| facility_inventory | Per-facility snapshot data |
| grn_receipts | GRN data comes through transactions |
| returns | Return data comes through transactions |
| return_items | Return detail not needed |
| facilities | Facility codes from env/config |

### Channel classification rules table (new)

```sql
CREATE TABLE channel_rules (
    id SERIAL PRIMARY KEY,
    rule_type TEXT NOT NULL,         -- 'entity', 'sale_order_prefix', 'override'
    match_value TEXT NOT NULL,        -- e.g., 'GRN', 'MA-', 'SO'
    facility_filter TEXT,            -- nullable: if set, rule only applies to this facility (for compound rules like SO + Kala Ghoda = store)
    channel TEXT NOT NULL,           -- supplier, wholesale, online, store, internal
    priority INT NOT NULL DEFAULT 0, -- higher = applied first
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

`facility_filter` enables compound rules: "sale_order_prefix=SO + facility=PPETPLKALAGHODA -> store" vs "sale_order_prefix=SO + facility=ppetpl -> wholesale".

Default rules seeded, editable from dashboard. Changes trigger pipeline recompute.

## Channel Classification

Entities and their channels:

| Entity | Channel | Velocity? |
|--------|---------|-----------|
| PICKLIST (MANUAL/SALE, OUT) | wholesale/online/store (by rule) | Yes — demand |
| GRN (IN) | supplier | No |
| PUTAWAY_CIR (IN) | online | Reduces demand |
| PUTAWAY_RTO (IN) | online | Reduces demand |
| INVENTORY_ADJUSTMENT (IN) | internal | No |
| INBOUND/OUTBOUND_GATEPASS | internal | No |
| PUTAWAY_CANCELLED_ITEM (IN) | internal | No |
| PUTAWAY_PICKLIST_ITEM (IN) | internal | No |
| INVOICES | **EXCLUDED** | N/A — billing document |

**PICKLIST channel rules (default, editable via UI):**

| Rule | Channel |
|------|---------|
| Sale order starts with `MA-` | online |
| Sale order starts with `B2C-` | online |
| Sale order starts with `SO` + facility Kala Ghoda | store |
| Sale order starts with `SO` + facility Bhiwandi | wholesale |
| No sale order (default) | wholesale |

Team can add/edit/delete rules and override individual transactions from the channel rules page. Saving triggers pipeline recompute.

## Pipeline Computation

Six phases, run sequentially on every sync and on classification changes:

**Phase 1: Build daily positions**
- Read all transactions from DB, grouped by SKU
- Per SKU: start at 0, walk forward day by day
- `closing_qty = opening + inward - outward`
- `is_in_stock = closing_qty > 0 OR had_demand`
- Track `wholesale_out`, `online_out`, `store_out`
- Upsert into `daily_stock_positions`

**Phase 2: Flat velocity**
- `velocity = net_demand / in_stock_days` (min 14 days required)
- Per-channel velocities, clamped at 0
- `net_demand = PICKLIST_out - CIR_returns - RTO_returns`
- Returns are identified by `entity` column: `PUTAWAY_CIR` and `PUTAWAY_RTO` with `txn_type=IN`. These are inward movements that reduce net demand in the online channel.

**Phase 3: ABC/XYZ classification**
- ABC: revenue-based Pareto (A: top 80%, B: 80-95%, C: rest)
- XYZ: weekly demand variability (CV-based, min 4 qualifying weeks)

**Phase 4: WMA velocity + trend**
- 90-day weighted moving average per channel
- Trend: up (WMA > flat x 1.2), down (WMA < flat x 0.8), flat

**Phase 5: Safety buffer + reorder**
- Buffer from ABC x XYZ matrix, multiplied by supplier override
- `reorder_qty = velocity x (lead_time + coverage) x buffer - current_stock`
- `current_stock` = latest `daily_stock_positions.closing_qty`
- Status: critical/warning/ok/stocked_out/out_of_stock/no_demand

**Phase 6: Brand rollups**
- Aggregate per brand: dead stock count, slow movers, avg/min days to stockout

## Smart Recompute

The pipeline recomputes on **any** frontend change — not just channel classification. But it only runs the phases that are actually affected, making most changes near-instant.

| Frontend Change | Phases Run | Scope | Speed |
|----------------|------------|-------|-------|
| Buffer matrix change | 5 (reorder) + 6 (rollups) | All SKUs | Fast (~seconds) |
| Supplier lead time change | 5 + 6 | SKUs in affected brand | Fast |
| Override change (qty, velocity, status) | 5 + 6 | Single SKU + its brand | Instant |
| Reorder intent change (must_stock, do_not_reorder) | 5 + 6 | Single SKU + its brand | Instant |
| Channel classification rule change | 1-6 (full) | Affected SKUs | ~1-2 min |
| App settings change (thresholds, WMA window) | 2-6 | All SKUs | ~30s |

**Nightly sync respects frontend changes:** The nightly sync runs a full phase 1-6 recompute, but it reads channel rules, overrides, buffer settings, supplier lead times, and reorder intents from the DB. Since frontend changes persist to these tables, the nightly recompute incorporates them automatically — nothing gets overwritten.

Each API endpoint that accepts a user change calls `run_pipeline(phases=[5,6], scope='brand:WINSOR & NEWTON')` (or whatever subset is needed) before returning. The pipeline function accepts optional `phases` and `scope` parameters to skip unnecessary work.

## SKU Display Names

- `stock_items.name` = human-readable display name ("WN PAC 60ML SILVER") — shown as title in UI
- `stock_items.sku_code` = part number ("2320617") — shown as "Part No" in UI
- Internal joins use `sku_code` (stable, unique)
- Ledger `SKU Code` column maps to `sku_code`; `SKU Name` maps to `name` (via catalog sync)

## File Structure

```
src/
  unicommerce/
    client.py          -- UC auth + Export Job methods (create, poll, download)
    catalog.py         -- Pull SKU master (unchanged)
    ledger_sync.py     -- NEW: nightly orchestrator
    ledger_parser.py   -- RENAMED: parse CSV, exclude INVOICES, classify channels
  engine/
    pipeline.py        -- Simplified: pure forward walk, no snapshot logic. Reads new transaction schema columns (entity, entity_type, txn_type, stock_change instead of old voucher_type, is_inward, quantity, return_type). ABC classification and import history functions updated to use new columns.
    stock_position.py  -- Build positions from transactions (updated for new schema)
    velocity.py        -- Flat + WMA velocity (interface unchanged, reads from positions)
    classification.py  -- ABC/XYZ + safety buffer (interface unchanged, reads from positions/metrics)
    reorder.py         -- Reorder status + qty (interface unchanged)
    aggregation.py     -- Brand rollups (interface unchanged)
  api/
    routes/
      channel_rules.py -- NEW: CRUD for channel rules + trigger recompute
      skus.py          -- Update: name as title, sku_code as Part No
      (all other routes unchanged)
  db/
    migrations/
      uc_002_ledger_rebuild.sql -- Drop old tables, modify transactions schema
  dashboard/
    (minor updates: name/part_no display swap, channel rules page)
```

**Deleted:** `sync.py` (replaced by `ledger_sync.py`), `inventory.py`, `orders.py`, `returns.py`, `inbound.py`, `backfill.py`, `transaction_loader.py`

## Error Handling

| Failure | Recovery |
|---------|----------|
| UC auth fails | Retry once, then log + email alert. Previous data stays valid. |
| Export Job fails for 1 facility | Log, continue others. 3-day overlap catches it next night. |
| Export Job timeout (>5 min) | Move to next facility. |
| S3 download fails | Retry once, then treat as facility failure. |
| Malformed CSV row | Log and skip row, continue parsing. |
| Pipeline fails | Log + email. Previous metrics stay in DB. |
| DB connection lost | Transaction-level commits. Re-run is safe (dedup). |
| Any frontend change (buffer, lead time, override, channel rule, intent, settings) | API saves change to DB, triggers smart recompute (only affected phases/scope). Most changes return in seconds. Channel rule changes run as background task (~1-2 min) with dashboard polling. |

**Periodic validation (optional, weekly):** Pull snapshot for ~50 random SKUs, compare `inventory` field against ledger-derived closing balance. Log warnings if any diverge. Monitoring only, never modifies data.
