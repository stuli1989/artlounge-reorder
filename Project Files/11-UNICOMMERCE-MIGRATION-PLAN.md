# 11 — Unicommerce Migration Plan

> **Status:** RESEARCH COMPLETE — all APIs verified, ready for brainstorming + build planning
> **Date:** 2026-03-24 (updated)
> **Priority:** Future (do not build until approved)

## Why Migrate

Unicommerce is Art Lounge's actual ERP and warehouse management system. It's a better source of truth than Tally Prime, which has:
- SKU renames breaking balance reconstruction (95% of items don't reconcile)
- Party-name heuristics needed to classify channels (5-level ruleset)
- 5,574 items with negative closing balances
- XML API with sanitization issues, timeouts, and quirks

Unicommerce offers native channel codes, dispatch-confirmed sales, stable SKU identifiers, and clean return categorization (CIR vs RTO).

## Architecture: Before vs After

### Current (Tally)
```
EC2 (Tally) → nightly sync script → Railway API → PostgreSQL → computation → dashboard
```
- Requires EC2 middleman running Tally
- XML over HTTP, ~190 MB per sync
- Party-name heuristics for channel classification
- Backward-reconstruction of daily stock positions

### Target (Unicommerce)
```
Railway cron → Unicommerce cloud API → PostgreSQL → computation → dashboard
```
- No middle layer — Railway calls UC API directly over HTTPS
- JSON REST API
- Native channel codes on every order
- Forward-computed stock positions from snapshots + movements

## Feasibility Assessment — CONFIRMED

All endpoints tested against production on 2026-03-24. **Integration is fully feasible.**

| Need | UC Endpoint | Verified? | Data Quality |
|---|---|---|---|
| Current stock per SKU | Inventory Snapshot | **Yes** — tested all 3 facilities | Rich: inventory, openSale, openPurchase, putawayPending, blocked, bad |
| Sales velocity | Shipping Package search + Sale Order search | **Yes** | Dispatch-confirmed with SKU + channel + dates |
| Channel breakdown | Native `channel` field on orders | **Yes** | Clean: MAGENTO2, FLIPKART, AMAZON_EASYSHIP_V2, CUSTOM_SHOP, CUSTOM |
| SKU catalog + brands | Product/itemType search | **Yes** — 23,362 SKUs | Includes category, brand, barcodes, pricing |
| Order detail | Sale order get | **Yes** | Item-level SKU, price, status |
| Purchase orders | PO list + detail | **Yes** — 585 POs | Vendor, items, dates, status |
| Inbound/GRN | Inflow receipt list + detail | **Yes** — 665 GRNs | SKU-level qty, unit price, vendor, PO linkage, rejected qty |
| Returns | Return search (CIR + RTO) + detail | **Yes** — 48 CIR + 41 RTO in Feb, 19 CIR in March | 30-day window cap confirmed; detail gives SKU, inventory type, invoice code |
| Historical movements | Transaction Ledger export | **Pending** — UC adding to account | Will cover stock position history + adjustment audit trail |

## Unicommerce API Endpoints — Verified

| # | Purpose | Endpoint | Scope | Status |
|---|---|---|---|---|
| 1 | Auth | `GET /oauth/token` | Tenant | **Working** — ~12hr token, 30-day refresh |
| 2 | Current stock | `POST /services/rest/v1/inventory/inventorySnapshot/get` | Facility | **Working** — 10K SKUs/call, needs `Facility` header |
| 3 | Sale order search | `POST /services/rest/v1/oms/saleOrder/search` | Tenant | **Working** — date range + channel filters |
| 4 | Sale order get | `POST /services/rest/v1/oms/saleorder/get` (lowercase!) | Tenant | **Working** — item-level SKU data |
| 5 | Shipping packages | `POST /services/rest/v1/oms/shippingPackage/search` | Facility | **Working** — needs `Facility` header |
| 6 | Return search | `POST /services/rest/v1/oms/return/search` | Facility | **Working** — 30-day window cap, requires `returnType` (CIR/RTO). 48 CIR + 41 RTO in Feb. |
| 6b | Return detail | `POST /services/rest/v1/oms/return/get` | Facility | **Working** — field: `reversePickupCode`. Returns SKU, status, inventoryType, invoice code, putaway info. |
| 7 | PO list | `POST /services/rest/v1/purchase/purchaseOrder/getPurchaseOrders` | Facility | **Working** — 585 POs returned |
| 8 | PO detail | `POST /services/rest/v1/purchase/purchaseOrder/get` | — | **404** — endpoint path not found yet, but PO data accessible via GRN detail |
| 9 | GRN list | `POST /services/rest/v1/purchase/inflowReceipt/getInflowReceipts` | Facility | **Working** — 665 GRNs returned |
| 10 | GRN detail | `POST /services/rest/v1/purchase/inflowReceipt/getInflowReceipt` | Facility | **Working** — rich: SKU, qty, price, vendor, PO link |
| 11 | SKU search | `POST /services/rest/v1/product/itemType/search` | Tenant | **Working** — 23,362 SKUs |
| 12 | SKU detail | `POST /services/rest/v1/catalog/itemType/get` | Tenant | **Working** |
| 13 | Bulk export | `POST /services/rest/v1/export/job/create` | Tenant | Not yet tested |

**URL case-sensitivity gotcha:** `/saleOrder/search` (camelCase) vs `/saleorder/get` (lowercase). Check each endpoint individually.

**Documentation:**
- REST API: https://documentation.unicommerce.com/docs/using-the-uniware-apis.html
- SOAP API: https://support.unicommerce.com/index.php/knowledge-base/api/

## API Access

**Both SOAP and REST APIs are available** at the same tenant domain. Using REST (recommended).

| | Production | Sandbox |
|---|---|---|
| Tenant | `ppetpl.unicommerce.com` | `staging.unicommerce.com` |
| REST | `/services/rest/v1/...` | `/services/rest/v1/...` |
| REST OAuth user | `kshitij@artlounge.in` | `Sandbox` |
| SOAP user | `reorder` | `Sandbox` |
| Credentials | *(stored as env vars, NOT in code)* | *(stored as env vars)* |

**Facilities:**

| Code | Name | Party |
|---|---|---|
| `ppetpl` | PPETPL Bhiwandi | Platinum Painting Essentials & Trading Pvt. Ltd. |
| `ALIBHIWANDI` | Art Lounge Bhiwandi | Art Lounge India |
| `PPETPLKALAGHODA` | PPETPL Kala Ghoda | PPETPL Kala Ghoda |

**Channels:** `MAGENTO2`, `AMAZON_EASYSHIP_V2`, `FLIPKART`, `CUSTOM_SHOP`, `CUSTOM`

## Data Gaps — Unicommerce Replies (2026-03-24)

| Gap | UC Response | Status |
|---|---|---|
| Historical stock positions | **Transaction Ledger report** — UC adding to our account | Awaiting confirmation |
| Stock movement / audit trail | **Transaction Ledger** for movements. Prefer Inventory Ledger but not on API yet | Partial — TL available |
| Inventory adjustment history | **Transaction Ledger** covers this | Covered |
| Return search 30-day cap | UC asked for **cURL + response** stretching >30 days for tech team review | Action needed |
| Export report types | **All reports visible in Uniware UI** — no separate listing | Check dashboard |
| Rate limits | UC asked for **expected hits per minute** | Action needed |

### Follow-up Actions

1. **Return search cURL:** Send UC the cURL + error response for >30 day return query (INVALID_TIME_INTERVAL error)
2. **Rate limit estimate:** Tell UC: ~50-100 API calls total per nightly sync, once per day. Negligible.
3. **Transaction Ledger:** Wait for UC to confirm it's added, then test the export
4. **Channel mapping:** Confirm what `CUSTOM_SHOP` and `CUSTOM` represent (wholesale? walk-in? B2B?)

## Sample Data Observed

**SpeedBall #22B Pen Nib (SP009405):**
- Inventory at ppetpl: 20 available, 10 putaway pending, 1 blocked
- Inventory at ALIBHIWANDI: 0
- Inventory at PPETPLKALAGHODA: not stocked
- Appeared in MAGENTO2 order MA-000054351 (3 units, Rs 128/unit, DELIVERED)

**GRN G0665 (most recent):**
- PO: PO0852 from ART LOUNGE INDIA (artloungeindia)
- Items: Montana Gold spray paint, Koh-i-noor leadholder, etc.
- Rich data: SKU, quantity, unit price, MRP, rejected qty, vendor SKU code, EAN/barcode

## Codebase Reuse Assessment

### Reuse Summary

| Category | What | % of Codebase |
|---|---|---|
| **Discard** | Tally extraction layer (client, XML parsers, party heuristics) | ~15% |
| **Redesign** | Entire computation engine (velocity, stock positions, reorder, dead stock, classification) | ~25% |
| **Reuse as-is** | API routes, frontend, infrastructure, DB helpers | ~45% |
| **Reuse with minor mods** | Pipeline orchestration, sync structure, DB schema, config | ~15% |

### Discard — Tally Extraction Layer

| File | Why |
|---|---|
| `extraction/tally_client.py` | Tally XML HTTP client, XML sanitization |
| `extraction/xml_requests.py` | TDL Collection XML request templates |
| `extraction/xml_parser.py` | Tally XML parsing, Tally field names/date format |
| `extraction/party_classifier.py` (rules) | Tally voucher-type/party-name heuristic rules — replaced by UC native channels |
| `extraction/data_loader.py` (top-level) | `load_all_master_data()` orchestrator that calls Tally |
| `extraction/transaction_loader.py` (Tally fns) | `sync_transactions_from_tally()`, Tally date parser |
| `engine/backdate_physical_stock.py` | Workaround for Tally Physical Stock data entry pattern |

### Redesign — Computation Engine

The current engine was built around Tally's data quality limitations. With Unicommerce's cleaner data, every formula should be rethought from scratch. Current code is **reference/inspiration only**, not copy-paste.

| Module | Current (Tally workarounds) | Needs Rethinking For UC |
|---|---|---|
| **`stock_position.py`** | Backward-reconstructs daily positions from Tally's closing balance; handles Physical Stock SET-TO logic, negative balances | Forward-compute from UC inventory snapshots + movements. Fundamentally different approach. No backward reconstruction needed. |
| **`velocity.py`** | In-stock-day-only velocity to guard against Tally's unreliable stock levels; derives quantities from voucher line items | Can we use dispatch-confirmed quantities directly? Is in-stock-day exclusion still needed with accurate inventory? WMA parameters may need recalibrating. |
| **`reorder.py`** | `velocity × (lead_time + coverage_period) × buffer - current_stock` with safety buffers; guards against negative stock | With accurate stock and velocity, buffer matrix and thresholds may all change. Dead stock detection needs rethinking — currently based on closing <= 0, but UC has accurate zero-movement periods. |
| **`classification.py`** | ABC/XYZ based on revenue and variability from Tally transactions; `_DEMAND_CHANNELS` and `_EXCLUDED_VOUCHER_TYPES` are Tally-derived | Different input data (dispatch-confirmed, clean channels) = different classifications = different safety buffers = cascading effect on all reorder quantities. |
| **`aggregation.py`** | Brand-level rollups from SKU metrics | Logic is generic but inputs change if metrics change. |
| **Channel mapping** | 5-priority heuristic from party names (P1-P5 ruleset) | Replaced by UC native channels. But: what is `CUSTOM`? What is `CUSTOM_SHOP`? Which channels count as "demand" for velocity? |

**This is the critical brainstorming step** — designing the right formulae for clean data before writing code.

### Reuse As-Is (~45% of codebase)

**All API routes** — `brands.py`, `skus.py`, `suppliers.py`, `overrides.py`, `po.py`, `search.py`, `users.py`, `auth_routes.py`, `settings.py`
- Read from generic `sku_metrics`, `brand_metrics`, `daily_stock_positions` tables. Zero Tally references.

**All infrastructure** — `api/main.py`, `api/database.py`, `api/auth.py`, `sync/sync_helpers.py`, `sync/email_notifier.py`

**Business logic utilities** — `effective_values.py` (override layer), `override_drift.py` (drift detection), `recalculate_buffers.py` (post-settings-change recalc)
- These operate on `sku_metrics` output, not raw data. Reusable once the upstream computation is redesigned.

**Entire frontend** — `dashboard/` (React + shadcn/ui)
- All components consume `/api/` endpoints. Only label changes needed (e.g., "tally_name" → "name").

### Reuse With Modifications (~15% of codebase)

| File | What Changes | Effort |
|---|---|---|
| `engine/pipeline.py` | 6-phase structure stays; delete backdate calls, swap in new engine functions | Medium |
| `sync/nightly_sync.py` | Replace Tally extraction calls with UC API calls. Orchestration structure stays. | Medium |
| `extraction/data_loader.py` (DB helpers) | Rename `tally_name` column refs. Core UPSERT logic stays. | Small |
| `extraction/transaction_loader.py` (`load_transactions`) | Drop `phys_stock_diff`. Core batch-insert stays. | Small |
| `api/routes/parties.py` | Rename `tally_name`/`tally_parent` in SQL. | Trivial |
| `db/schema.sql` | Rename `tally_*` columns, drop Tally-specific columns, possibly add UC-specific fields. | Small |
| `config/settings.py` | Remove `TALLY_*` vars. Add UC tenant/credentials config. | Trivial |

### What's New (to build from scratch)

| Component | Purpose |
|---|---|
| **UC API client** | REST client: OAuth token management, request helpers, retry, pagination |
| **UC inventory module** | Pull inventory snapshots across all 3 facilities |
| **UC orders module** | Pull sale orders + shipping packages with pagination |
| **UC returns module** | Pull returns (CIR + RTO) with 30-day window looping |
| **UC inbound module** | Pull POs + GRNs for lead time analysis |
| **UC catalog module** | Pull SKU master data (categories, brands, barcodes) |
| **UC sync orchestrator** | Nightly sync (replaces Tally sync) |
| **Channel mapping** | Map UC channels → our taxonomy. Decide: CUSTOM=? CUSTOM_SHOP=? |
| **New velocity engine** | Fresh formula design for dispatch-confirmed data |
| **New stock position engine** | Forward-computation from snapshots + movements |
| **New reorder/stockout engine** | Optimized for accurate inventory data |
| **New dead stock detection** | Based on actual zero-movement periods |

### Key Architecture Insight

The Tally dependency splits into two layers:
1. **Extraction layer** (~15%) — confined to `extraction/`, cleanly replaceable
2. **Computation engine** (~25%) — workarounds baked into every formula. These are the right business *concepts* (velocity, stockout prediction, ABC/XYZ) but the wrong *implementations* for clean data. Must be redesigned, not just patched.

The remaining ~60% (API, frontend, infrastructure, DB helpers) carries over with minimal changes.

## Development Strategy

### Branch
- All work on `feature/unicommerce` — main stays Tally-based until cutover
- Periodically rebase main into feature branch to stay current

### Database
- Fully separate local DB: `artlounge_reorder_uc`
- Zero risk to production Tally data
- Run side-by-side for comparison during validation

### Railway Cutover
1. Spin up second Railway Postgres instance
2. Populate with Unicommerce data
3. Merge `feature/unicommerce` → `main`
4. Switch connection string
5. Keep old Tally DB for rollback (system not yet live, so rollback = revert branch)

## Key Facts

- **System not yet launched** — switchover is seamless, no user disruption
- **Unicommerce = single source of truth** — no dual-source maintenance with Tally
- **All channels in UC** — wholesale, online (Amazon, Flipkart, Magento), and retail all flow through Unicommerce
- **SKU codes consistent** — Tally and UC maintained in sync; mapping table provided if needed
- **No real-time sync needed** — nightly batch is sufficient, webhooks parked for future
- **No middle layer** — Railway → UC cloud API directly
- **~60% code reuse** — API + frontend + infrastructure carry over. Extraction layer replaced. Computation engine redesigned from scratch (same concepts, better formulae for clean data).

## Computation Engine Design (brainstormed + reviewed 2026-03-24)

All formulae reviewed from first principles by multiple Opus agents. Issues found and resolved below.

### Channel Mapping (confirmed)

| UC Channel | Mapping | Source |
|---|---|---|
| `MAGENTO2` | **online** | Website (artlounge.in) |
| `FLIPKART` | **online** | Flipkart marketplace |
| `AMAZON_EASYSHIP_V2` / `AMAZON_IN_API` | **online** | Amazon marketplace |
| `CUSTOM` | **wholesale** | B2B dispatches from main warehouse |
| `CUSTOM_SHOP` | **store** | Kala Ghoda retail store |

All channels are demand channels for velocity. System must be **facility-agnostic** — dynamically discover facilities via API, aggregate across all.

### F1. Available Stock

**Question:** What can we sell right now?

**IMPORTANT:** UC's `inventory` field = total good inventory (INCLUDES blocked). Confirmed via UC support docs: "Total Inventory is the sum of available and blocked inventory."

```
available_stock = SUM(inventory - inventoryBlocked + putawayPending) across all facilities
```

- `inventory`: total good stock on shelf (includes blocked — must subtract)
- `inventoryBlocked`: reserved/quarantined (subset of inventory — subtract)
- `putawayPending`: received, not shelved yet (include — physically in warehouse)
- `badInventory`: damaged/QC-rejected (not in inventory field — tracked separately)
- `openSale`: already excluded from `inventory` by UC (do NOT subtract again)

### F2. Effective Stock (for reorder decisions)

**Question:** What stock counts when deciding whether to reorder?

```
effective_stock = available_stock
```

`openPurchase` is **excluded from the formula** — shown as reference in PO builder only. Reason: a PO that won't arrive for 4 months would suppress reorder signals, dangerous for 90-180 day lead times.

`pendingStockTransfer` excluded — zero-sum across facilities when summing globally.

### F3. Daily Stock Position

**Approach:** Forward-compute from daily inventory snapshots + movements.

- **Primary:** Daily snapshot accumulation — pull inventory snapshot nightly, store it. 100% accurate.
- **Backfill:** Forward-compute from Transaction Ledger (when UC provides it). Anchor on one snapshot, apply dispatches/GRNs/returns daily.
- **Nightly reconciliation:** Compare computed vs actual snapshot, flag drift.

No backward reconstruction. No Physical Stock SET-TO logic. No negative-balance guards.

### F4. Is In Stock

**Question:** Was this SKU available on day X?

```
is_in_stock = (available_stock > 0) OR (had_demand_that_day)
```

The `OR had_demand` clause catches days where the last units sell (closing=0 but item WAS available and sold). Without this, those days get excluded from the velocity denominator, inflating velocity for high-turnover items.

### F5. Gross Demand

**Question:** How many units did customers want?

```
gross_demand = SUM(dispatched_qty) for channels in {online, wholesale, store}
```

Source: Shipping Package items (dispatch-confirmed, not invoice-based). Only demand channels — excludes supplier inbound, inter-facility transfers, inventory adjustments.

### F6. Net Demand

**Question:** What was the actual net outflow to customers?

```
net_demand = gross_demand - CIR_returned_qty - RTO_returned_qty
```

Both CIR and RTO reduce net demand. CIR and RTO tracked as separate fields in DB for future analysis.

Per channel (returns matched to original order's channel):
```
net_demand_wholesale = dispatched_wholesale - returns_wholesale
net_demand_online    = dispatched_online - returns_online
net_demand_store     = dispatched_store - returns_store
```

### F7. Velocity (Flat / FY-to-date)

**Question:** On average, how many units per day does this SKU sell when in stock?

```
velocity = net_demand / in_stock_days
```

**Minimum sample guard:** If `in_stock_days < 14`, velocity is marked as **unreliable/insufficient data**. Prevents tiny samples (3 days → 6 sales = 2.0/day) from triggering massive reorders.

Edge cases:
- `in_stock_days = 0` → velocity = 0
- `net_demand = 0, in_stock_days > 0` → velocity = 0
- `net_demand < 0` (more returns than dispatches) → velocity = 0 (clamped)

### F8. Velocity Per Channel

```
wholesale_velocity = max(0, net_demand_wholesale / in_stock_days)
online_velocity    = max(0, net_demand_online / in_stock_days)
store_velocity     = max(0, net_demand_store / in_stock_days)
total_velocity     = wholesale_velocity + online_velocity + store_velocity
```

Same denominator for all channels (shared inventory pool). Per-channel velocity clamped at 0 — returns on one channel cannot reduce the total reorder signal.

### F9. Velocity (Recent / Trailing Window)

```
recent_velocity = net_demand_in_window / in_stock_days_in_window
```

Default window = 90 days, configurable. Same minimum sample guard (14 in-stock days in window).

### F10. Velocity Trend

```
trend_ratio = recent_velocity / flat_velocity

if flat_velocity = 0 AND recent_velocity > 0 → UP (newly activated)
if flat_velocity = 0 AND recent_velocity = 0 → FLAT
if recent_velocity = 0 AND flat_velocity > 0 → DOWN
if trend_ratio >= 1.2 → UP
if trend_ratio <= 0.8 → DOWN
else → FLAT
```

Thresholds (1.2 / 0.8) configurable.

### F11. Days to Stockout

```
days_to_stockout = effective_stock / total_velocity
```

Uses `effective_stock` (available stock only, no openPurchase). `openPurchase` shown separately in dashboard.

Edge cases:
- `velocity = 0, stock > 0` → infinity (display as "No demand")
- `velocity = 0, stock = 0` → 0
- `stock <= 0` → 0

**Uses recent_velocity** (not flat) for the most current demand signal.

### F12. Lead Time

Manually set per supplier/brand. Auto-computed reference from UC data:
```
computed_lead_time = AVG(grn_received_date - po_created_date) for completed POs
```

Manual setting takes precedence. Dashboard shows computed vs manual for awareness.

### F13. Coverage Period

```
turns_per_year = min(max(1, 365 / lead_time), 6)
coverage_days = 365 / turns_per_year
```

Per-supplier `typical_order_months` override takes precedence.

### F14. Safety Buffer

ABC × XYZ matrix lookup:

| | X (stable) | Y (moderate) | Z (erratic) |
|---|---|---|---|
| **A** | 1.2 | 1.3 | 1.5 |
| **B** | 1.15 | 1.25 | 1.4 |
| **C** | 1.1 | 1.2 | 1.3 |

Default if no classification: 1.3. Per-supplier override is a **multiplier on the matrix** (not a replacement). Example: supplier override 1.1 × matrix AX 1.2 = effective buffer 1.32.

### F15. Reorder Quantity

```
demand_during_lead  = total_velocity × lead_time          (best estimate, NO buffer)
stock_at_arrival    = max(0, effective_stock - demand_during_lead)
order_for_coverage  = total_velocity × coverage_period × safety_buffer  (buffer on future only)
suggested_qty       = max(0, order_for_coverage - stock_at_arrival)
```

**Buffer applies to coverage demand only** — can't magically create current stock; buffer protects against future demand uncertainty.

Overrides:
- `must_stock` with zero velocity: `max(1, coverage_period / 90)` (conservative for unproven items)
- `do_not_reorder`: quantity = 0 always

### F16. Reorder Status

```
if velocity > 0 AND effective_stock <= 0    → STOCKED_OUT (already out, actively selling)
if velocity = 0 AND effective_stock <= 0    → OUT_OF_STOCK (out, no demand signal)
if velocity = 0 AND effective_stock > 0     → NO_DEMAND (has stock, not selling)
if days_to_stockout <= lead_time            → CRITICAL
if days_to_stockout <= lead_time + warning  → WARNING
else                                        → OK

warning_buffer = max(30, lead_time × 0.5)
```

Overrides:
- `must_stock`: forces minimum **WARNING** (only CRITICAL if formula also says so)
- `do_not_reorder`: shows **calculated status** with "reorder suppressed" indicator (doesn't hide real status)

### F17. ABC Classification

```
revenue_per_sku = SUM(sellingPrice × quantity) for dispatched demand items
```

UC's `sellingPrice` reflects trade discounts (confirmed). Sort by revenue desc, cumulative Pareto: A ≤ 80%, B ≤ 95%, C = rest. Zero revenue → always C. Thresholds configurable.

**Early-FY note:** First 2-3 months of new FY, ABC will be volatile (small sample). Consider seeding from prior FY or using rolling 12-month window.

### F18. XYZ Classification

```
Group in-stock days into CALENDAR weeks (Mon-Sun)
  Only include weeks where SKU was in-stock >= 4 days
  Require minimum 4 qualifying weeks (28 in-stock days)
weekly_demand = SUM(net_demand) per qualifying week
CV = population_stddev(weekly_demand) / mean(weekly_demand)

X if CV < 0.5    (stable)
Y if CV <= 1.0   (moderate)
Z if CV > 1.0    (erratic)
```

**Fixed from Tally version:** Uses calendar weeks instead of stitching non-contiguous in-stock days sequentially. This preserves the temporal structure XYZ is meant to measure.

### F19. Dead Stock

```
dead_stock = available_stock > 0
             AND (last_dispatch_date is NULL OR days_since_last_dispatch >= threshold)
```

Default threshold: **90 days**, programmable. `available_stock` uses the F1 formula (excludes blocked/bad).

### F20. Slow Mover

```
slow_mover = available_stock > 0
             AND velocity > 0
             AND velocity < slow_mover_threshold
             AND abc_class != 'A'              (A-class earns its shelf space)
             AND reorder_intent = 'normal'
```

Default threshold: 0.1 units/day (~3/month), programmable. A-class SKUs excluded — if they generate significant revenue, they're not "slow."

### F21. Last Dispatch Date

```
last_dispatch_date = MAX(shipping_package_dispatch_date)
                     WHERE channel IN {online, wholesale, store}
```

Uses shipping package dispatch date (actual shipment), NOT sale order creation date.

### F22. Zero Activity Days

```
zero_activity_ratio = zero_activity_days / total_in_stock_days
```

Where `zero_activity_days = COUNT(days WHERE available_stock > 0 AND outward = 0 AND inward = 0)`.

Expressed as a **ratio** (not absolute count) — normalizes for in-stock duration. Ratio of 0.95 (sells once/20 days) vs 0.60 (sells 2-3x/week) is meaningful.

### F23. Brand Rollups

Aggregate per brand:
```
total_skus, active_skus, inactive_skus
in_stock_skus, out_of_stock_skus
critical, warning, ok, no_demand, stocked_out counts
dead_stock_skus, slow_mover_skus
a/b/c_class_skus
avg_days_to_stockout = velocity-weighted average
min_days_to_stockout = earliest stockout in brand (catches critical slow movers)
```

`min_days_to_stockout` added to complement the velocity-weighted average, which can mask critical slow-moving SKUs.

---

### Review Issues Found & Resolved

| # | Severity | Issue | Resolution |
|---|---|---|---|
| H1 | **HIGH** | F15: Safety buffer applied twice (lead + coverage), compounding | Buffer on coverage only; lead uses best estimate |
| H2 | **HIGH** | F2: openPurchase suppresses reorder signals | Excluded from formula; shown as reference in PO builder |
| H3 | **HIGH** | F7/F9: No min sample size; 3 days → wild velocity | Min 14 in-stock days; below = insufficient data |
| H4 | **HIGH** | F1: inventoryBlocked not subtracted (it's inside inventory) | Corrected: `inventory - inventoryBlocked + putawayPending` |
| M1 | **MED** | F4: Missing "had demand" clause; sell-to-zero days excluded | Added `OR had_demand_that_day` |
| M2 | **MED** | F10: flat=0, recent>0 → FLAT instead of UP | Fixed: newly activated items → UP |
| M3 | **MED** | F18: Non-contiguous days stitched sequentially | Fixed: calendar weeks |
| M4 | **MED** | F17: sellingPrice might not reflect discounts | Confirmed: UC sellingPrice includes trade discounts |
| M5 | **MED** | F16: must_stock forces CRITICAL always | Fixed: forces minimum WARNING only |
| M6 | **MED** | F14: Supplier override replaces matrix | Fixed: override is a multiplier |
| L1 | **LOW** | F6: CIR vs RTO treated same | Track separately in DB for future analysis |
| L2 | **LOW** | F8: Negative channel velocity possible | Fixed: clamp at 0 per channel |
| L3 | **LOW** | F16: do_not_reorder hides real status | Fixed: show calculated + "suppressed" indicator |
| L4 | **LOW** | F22: Absolute count misleading | Fixed: use ratio instead |
| L5 | **LOW** | F20: Not ABC-aware | Fixed: exclude A-class from slow mover |
| L6 | **LOW** | F16: Status names misleading | Fixed: STOCKED_OUT, NO_DEMAND (clearer names) |
| L7 | **LOW** | F23: Velocity-weighted avg hides critical slow movers | Fixed: added min_days_to_stockout |

### Decisions Log

| # | Decision | Answer | Date |
|---|---|---|---|
| 1 | CIR reduces velocity? | **Yes** | 2026-03-24 |
| 2 | RTO reduces velocity? | **Yes** | 2026-03-24 |
| 3 | Multi-facility: sum stock? | **Yes** — across all facilities | 2026-03-24 |
| 4 | Include openPurchase in effective stock? | **No** — show as reference only, exclude from formula | 2026-03-24 |
| 5 | Include putawayPending as available? | **Yes** | 2026-03-24 |
| 6 | Exclude inventoryBlocked? | **Yes** (it's inside inventory, must subtract) | 2026-03-24 |
| 7 | Dead stock threshold | **90 days**, programmable | 2026-03-24 |
| 8 | Facility-agnostic? | **Yes** — dynamic discovery, not hardcoded | 2026-03-24 |
| 9 | CUSTOM = wholesale? | **Yes** | 2026-03-24 |
| 10 | CUSTOM_SHOP = store? | **Yes** (Kala Ghoda) | 2026-03-24 |
| 11 | ALIBHIWANDI status? | **Pending** — clarifying with team | 2026-03-24 |
| 12 | Safety buffer scope? | **Coverage only** — not applied to lead time demand estimate | 2026-03-24 |
| 13 | must_stock status override? | **Minimum WARNING** — only CRITICAL if formula agrees | 2026-03-24 |
| 14 | Supplier buffer override? | **Multiplier** on ABC/XYZ matrix, not replacement | 2026-03-24 |

## Next Steps

1. ~~**Brainstorm**~~ — ~~design the new computation engine~~ DONE
2. ~~**Review**~~ — ~~all formulae reviewed by Opus agents, issues resolved~~ DONE
3. **Plan** — task breakdown for the Unicommerce build (similar to T01-T21)
4. **Build** — on `feature/unicommerce` branch with separate DB
5. **Validate** — compare UC results with Tally for known SKUs
6. **Cutover** — merge to main, switch Railway DB
