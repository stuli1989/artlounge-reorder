# 00 — Unicommerce Build Overview

## What This Is

Complete implementation plan for migrating the Art Lounge reorder system from Tally Prime to Unicommerce as the data source. This replaces the extraction layer, redesigns the computation engine, and keeps the API/frontend intact.

## How to Resume Work

All work lives on branch `feature/unicommerce`. To resume:

```bash
git checkout feature/unicommerce
cd src && ./venv/Scripts/python  # verify venv works
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder_uc -c "SELECT 1"  # verify UC database exists
```

Check `TASKS.md` in this folder for current progress. Each task has a status (pending/in-progress/done) and references the relevant spec doc.

## Architecture

```
Railway cron (nightly)
  → Authenticate with Unicommerce (OAuth2)
  → Discover facilities dynamically
  → Pull inventory snapshots (all SKUs, all facilities)
  → Pull dispatched shipping packages (since last sync)
  → Pull returns CIR + RTO (since last sync, 30-day windows)
  → Pull GRNs (since last sync)
  → Pull new/updated SKUs
  → Store raw data in PostgreSQL
  → Run computation pipeline (23 formulae)
  → Update sku_metrics, brand_metrics, daily_stock_positions
  → Send email notification
```

## Key Design Decisions

1. **Daily incremental syncs** — pull only data changed since last sync. No full re-pull.
2. **Backfill is a separate one-time module** — when UC provides Transaction Ledger, run once to fill historical data. Then incremental forever.
3. **Inventory snapshot = source of truth for stock levels** — stored daily, not reconstructed.
4. **Dispatch-confirmed quantities for velocity** — not invoices.
5. **Facility-agnostic** — dynamically discover facilities, aggregate across all.
6. **openPurchase excluded from reorder formula** — shown as reference only.
7. **All formulae reviewed and corrected** — see `05-COMPUTATION-ENGINE.md` and `11-UNICOMMERCE-MIGRATION-PLAN.md`.

## What's New vs Tally Build

| Aspect | Tally Build | UC Build |
|---|---|---|
| Data source | XML over HTTP to local Tally | REST/JSON to UC cloud API |
| Extraction | `extraction/` module (7 files) | `unicommerce/` module (7 files) |
| Channel mapping | 5-priority party-name heuristic | Native UC channel codes |
| Stock positions | Backward-reconstructed from closing | Forward from daily snapshots |
| Computation engine | Workarounds for Tally data quality | Clean formulae from first principles |
| Sync architecture | EC2 middleman required | Railway → UC direct |
| Database | `artlounge_reorder` | `artlounge_reorder_uc` (separate) |

## What Carries Over (~60%)

- All API routes (brands, SKUs, suppliers, overrides, PO, search, auth, settings)
- All infrastructure (FastAPI app, DB pool, auth, email notifier)
- Business logic utilities (effective_values, override_drift, recalculate_buffers)
- Entire React frontend (minor label changes only)
- Pipeline orchestration structure (6-phase)
- Sync helpers, email notifier
- DB helper functions (with column renames)

## Document Index

| Doc | Contents |
|---|---|
| `01-INFRASTRUCTURE.md` | Branch, database, config, project scaffolding |
| `02-UC-API-CLIENT.md` | OAuth, REST client, pagination, retry, rate limiting |
| `03-DATA-INGESTION.md` | Pulling catalog, inventory, orders, returns, POs/GRNs |
| `04-DB-SCHEMA.md` | Schema changes from Tally → UC |
| `05-COMPUTATION-ENGINE.md` | All 23 formulae with implementation notes |
| `06-INCREMENTAL-SYNC.md` | Nightly sync orchestrator design |
| `07-BACKFILL.md` | One-time historical data load |
| `08-API-FRONTEND.md` | Dashboard and API adjustments |
| `09-TESTING.md` | Test strategy and reference cases |
| `10-DEPLOYMENT.md` | Railway cutover plan |
| `BUILD-ORDER.md` | Sequenced task list with dependencies |
| `TASKS.md` | Progress tracker |
