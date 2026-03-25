# BUILD-ORDER — Step-by-Step Development Sequence

## How to Use This Document

Follow these phases in order. Each phase validates assumptions the next phase depends on. Tasks within a phase can be parallelized. Check off tasks as completed. Reference the relevant spec doc for details.

---

## Phase 1: Infrastructure (Day 1)

### T01: Create branch and database
**Doc:** `01-INFRASTRUCTURE.md`
- [ ] Create `feature/unicommerce` branch
- [ ] Create `artlounge_reorder_uc` database
- [ ] Verify connection with reorder_app user
- [ ] Copy `src/config/settings.py` and add UC settings (remove Tally vars)
- [ ] Create `.env` file with UC credentials
- [ ] Create `src/unicommerce/__init__.py`

### T02: Create UC database schema
**Doc:** `04-DB-SCHEMA.md`
- [ ] Write `db/migrations/uc_001_schema.sql`
- [ ] Rename `tally_*` columns in all tables
- [ ] Drop Tally-specific columns (`phys_stock_diff`, `backdate_physical_stock`)
- [ ] Create new tables: `daily_inventory_snapshots`, `facilities`, `grn_receipts`, `returns`, `return_items`
- [ ] Add new columns to `stock_items`, `transactions`, `sku_metrics`
- [ ] Update CHECK constraints (new status values: `stocked_out`, `no_demand`)
- [ ] Run migration, verify all tables created

**STOP: Verify DB schema is clean before proceeding.**

---

## Phase 2: UC API Client (Days 2-3)

### T03: Build Unicommerce REST client
**Doc:** `02-UC-API-CLIENT.md`
- [ ] Implement `UnicommerceClient` class with OAuth2 auth
- [ ] Token auto-refresh logic
- [ ] Request helper with retry, backoff, 401 re-auth
- [ ] Facility discovery (dynamic)
- [ ] Pagination helper
- [ ] Error handling (UC error envelope parsing)
- [ ] Test: authenticate against production, verify token
- [ ] Test: discover facilities, verify 3 returned

### T04: Build catalog ingestion
**Doc:** `03-DATA-INGESTION.md` (Section 1)
- [ ] `unicommerce/catalog.py` — `pull_all_skus()`, `pull_updated_skus()`
- [ ] Extract: skuCode, name, categoryCode, brand, costPrice, mrp, ean, hsnCode, enabled
- [ ] Load into `stock_items` and `stock_categories` tables
- [ ] Test: pull all 23,362 SKUs, load into DB
- [ ] Test: incremental pull (updatedSinceInHour)

**STOP: Verify SKU data in DB matches UC dashboard. Spot-check 10 SKUs.**

---

## Phase 3: Data Ingestion (Days 3-5)

### T05: Build inventory snapshot ingestion
**Doc:** `03-DATA-INGESTION.md` (Section 2)
- [ ] `unicommerce/inventory.py` — `pull_inventory_snapshot()`
- [ ] Chunk SKUs into conservative 1K batches per facility (make configurable)
- [ ] Aggregate across all facilities
- [ ] Compute available_stock = inventory - blocked + putaway (F1)
- [ ] Store in `daily_inventory_snapshots` and optionally `facility_inventory`
- [ ] Test: pull snapshot, verify SpeedBall SP009405 = inventory:20, blocked:1, putaway:10
- [ ] Test: available_stock = 20 - 1 + 10 = 29

### T06: Build dispatch ingestion
**Doc:** `03-DATA-INGESTION.md` (Section 3)
- [ ] `unicommerce/orders.py` — `pull_dispatched_since()`
- [ ] Transform shipping packages → transaction rows (outward)
- [ ] Channel mapping: CUSTOM→wholesale, CUSTOM_SHOP→store, MAGENTO2/FLIPKART/AMAZON→online
- [ ] Load into `transactions` table with dedup
- [ ] Test: pull last 7 days dispatches, verify counts match UC dashboard
- [ ] Test: channel mapping correct for known packages

### T07: Build returns ingestion
**Doc:** `03-DATA-INGESTION.md` (Section 4)
- [ ] `unicommerce/returns.py` — `pull_returns_since()`
- [ ] 30-day window looping for date ranges > 30 days (using updated timestamps)
- [ ] Fetch detail for each return (reversePickupCode)
- [ ] Map return channel to original sale channel and aggregate same-SKU quantities
- [ ] Transform to inward transactions with return_type (CIR/RTO)
- [ ] Store in `returns` + `return_items` tables
- [ ] Load into `transactions` table
- [ ] Test: pull Feb returns, verify 48 CIR + 41 RTO
- [ ] Test: return detail includes SKU, saleOrderCode

### T08: Build GRN/PO ingestion
**Doc:** `03-DATA-INGESTION.md` (Section 5)
- [ ] `unicommerce/inbound.py` — `pull_grns_since()`
- [ ] Use bounded date windows + pagination (never unbounded empty-body pull)
- [ ] Fetch GRN detail with PO linkage
- [ ] Transform to inward transactions (supplier channel)
- [ ] Store in `grn_receipts` table
- [ ] Compute lead_time = grn.created - po.created
- [ ] Load into `transactions` table
- [ ] Test: verify 665 GRN codes returned
- [ ] Test: GRN G0665 detail matches known data (PO0852, artloungeindia vendor)

**STOP: All raw data in DB. Spot-check transactions table — dispatches, returns, GRNs all present with correct channels.**

---

## Phase 4: Computation Engine (Days 5-8)

### T09: Rewrite stock position module
**Doc:** `05-COMPUTATION-ENGINE.md`
- [ ] `store_daily_snapshot()` — store UC inventory data as daily position
- [ ] `compute_is_in_stock()` — F4: available > 0 OR had_demand
- [ ] Remove all Physical Stock / backward-reconstruction / negative-balance code
- [ ] Test: is_in_stock correct for sell-to-zero day

### T10: Rewrite velocity module
**Doc:** `05-COMPUTATION-ENGINE.md`
- [ ] `calculate_velocity()` — F7: net_demand / in_stock_days
- [ ] Min 14 in-stock-day guard
- [ ] Per-channel velocity clamped at 0 (F8)
- [ ] `calculate_recent_velocity()` — F9: trailing 90-day window
- [ ] `detect_trend()` — F10: fixed edge case (flat=0, recent>0 → UP)
- [ ] Net demand = dispatched - CIR - RTO (F6)
- [ ] Test: velocity with min sample guard
- [ ] Test: negative channel velocity clamped
- [ ] Test: trend detection edge cases

### T11: Rewrite reorder module
**Doc:** `05-COMPUTATION-ENGINE.md`
- [ ] `compute_effective_stock()` — F2: available_stock only (no openPurchase)
- [ ] `calculate_days_to_stockout()` — F11: uses recent_velocity
- [ ] `determine_reorder_status()` — F15+F16: buffer on coverage only
- [ ] New status values: STOCKED_OUT, NO_DEMAND
- [ ] must_stock → min WARNING (F16 override)
- [ ] do_not_reorder → show calculated + suppressed flag
- [ ] `compute_coverage_days()` — F13: keep as-is
- [ ] Test: buffer NOT applied to lead time demand
- [ ] Test: must_stock with plenty of stock → WARNING not CRITICAL
- [ ] Test: do_not_reorder shows real status

### T12: Update classification module
**Doc:** `05-COMPUTATION-ENGINE.md`
- [ ] ABC — verify sellingPrice is net (F17)
- [ ] XYZ — rewrite to calendar weeks (F18)
- [ ] Safety buffer — supplier override as multiplier (F14)
- [ ] Test: XYZ with stockout gap uses calendar weeks
- [ ] Test: supplier override multiplies matrix value

### T13: Update pipeline and aggregation
**Doc:** `05-COMPUTATION-ENGINE.md`
- [ ] Remove `backdate_physical_stock` calls from pipeline
- [ ] Remove double reorder computation
- [ ] Update `tally_name` → `name` references
- [ ] Add `min_days_to_stockout` to brand rollups (F23)
- [ ] Add dead stock (F19), slow mover (F20, ABC-aware), zero_activity_ratio (F22)
- [ ] Test: full pipeline run produces valid metrics for all SKUs
- [ ] Test: brand rollups include min_days_to_stockout

**STOP: Run full pipeline. Verify sku_metrics populated for all 23K SKUs. Spot-check 20 SKUs for reasonable values.**

---

## Phase 5: Sync Orchestrator (Days 8-9)

### T14: Build nightly sync orchestrator
**Doc:** `06-INCREMENTAL-SYNC.md`
- [ ] `unicommerce/sync.py` — `run_nightly_sync()`
- [ ] Wire together: catalog → snapshot → dispatches → returns → GRNs → pipeline
- [ ] Incremental logic: compute `since_date` from last successful sync
- [ ] Use stable transaction idempotency key + `ON CONFLICT DO UPDATE`
- [ ] Sync log integration (create, update, stats)
- [ ] Email notification on success/failure
- [ ] CLI: `--full`, `--dry-run` flags
- [ ] Test: run full sync end-to-end
- [ ] Test: run incremental sync (second run, only new data pulled)
- [ ] Test: sync log correctly updated

### T15: Build backfill module
**Doc:** `07-BACKFILL.md`
- [ ] `unicommerce/backfill.py`
- [ ] Phase 1: backfill transactions (dispatches, returns, GRNs from FY start)
- [ ] Phase 2: backfill stock positions (Option B — from transactions + anchor snapshot)
- [ ] Phase 3: full pipeline recompute
- [ ] CLI: `--transactions`, `--positions`, `--full` flags
- [ ] Placeholder for Phase 2 Option A (Transaction Ledger — implement when available)
- [ ] Test: backfill produces historical data from FY start
- [ ] Test: idempotent — running twice produces same result

**STOP: Run nightly sync for 3 consecutive days. Verify incremental data growing correctly.**

---

## Phase 6: API & Frontend (Days 9-10)

### T16: Update API routes
**Doc:** `08-API-FRONTEND.md`
- [ ] `routes/parties.py` — rename tally_name → name in SQL
- [ ] `routes/settings.py` — remove Tally-specific setting keys
- [ ] `routes/sync_status.py` — update source label, add UC stats
- [ ] Add new fields to SKU response: open_purchase, bad_inventory, zero_activity_ratio, min_sample_met
- [ ] Add new status values to valid responses
- [ ] Test: all API routes return valid JSON

### T17: Update frontend
**Doc:** `08-API-FRONTEND.md`
- [ ] Rename labels: Tally Name → Name, No Data → No Demand
- [ ] Add "Stocked Out" status badge
- [ ] Show open_purchase as info badge on SKU detail
- [ ] Show bad_inventory if > 0
- [ ] Show "Insufficient data" warning for min_sample_met = false
- [ ] Show "reorder suppressed" for do_not_reorder items
- [ ] Add min_days_to_stockout to brand overview
- [ ] Build frontend: `cd src/dashboard && npm run build`

---

## Phase 7: Testing & Validation (Days 10-12)

### T18: Write and run tests
**Doc:** `09-TESTING.md`
- [ ] UC API integration tests
- [ ] Computation engine unit tests (velocity, reorder, classification)
- [ ] End-to-end sync test
- [ ] All tests passing

### T19: Comparison validation
**Doc:** `09-TESTING.md`
- [ ] Pick 20 SKUs across different profiles
- [ ] Compare UC velocity vs Tally velocity
- [ ] Compare stock levels vs Tally
- [ ] Document discrepancies and reasons
- [ ] Team review of comparison results

---

## Phase 8: Deployment (Days 12-13)

### T20: Deploy to Railway
**Doc:** `10-DEPLOYMENT.md`
- [ ] Spin up second Railway Postgres
- [ ] Run schema migration on Railway
- [ ] Run full sync + backfill against Railway UC DB
- [ ] Merge `feature/unicommerce` → `main`
- [ ] Switch Railway DATABASE_URL to UC Postgres
- [ ] Add UC env vars to Railway
- [ ] Verify dashboard loads correctly
- [ ] Set up Railway cron for nightly sync
- [ ] Monitor 3 consecutive nightly syncs

---

## Total Estimated Timeline: ~13 working days

| Phase | Tasks | Days |
|---|---|---|
| 1. Infrastructure | T01-T02 | 1 |
| 2. API Client | T03-T04 | 2 |
| 3. Data Ingestion | T05-T08 | 3 |
| 4. Computation Engine | T09-T13 | 3 |
| 5. Sync Orchestrator | T14-T15 | 1.5 |
| 6. API & Frontend | T16-T17 | 1.5 |
| 7. Testing & Validation | T18-T19 | 2 |
| 8. Deployment | T20 | 1 |
