# Reorder Status Simplification — Design Spec

## Problem

The current status system has 7 values (`stocked_out`, `out_of_stock`, `critical`, `warning`, `ok`, `no_demand`, `no_data`) that are confusing:

- "Stocked Out" vs "Out of Stock" sound identical
- "OK" implies "no action needed" even for hot sellers that should keep being ordered
- "Critical" / "Warning" describe severity, not what to DO
- The team can't glance at the dashboard and immediately know where to deploy working capital

## Design

### New Status Set (7 statuses, priority-ordered)

| # | Key | Display Label | Color | Condition | Action |
|---|-----|--------------|-------|-----------|--------|
| 1 | `lost_sales` | Lost Sales | Dark red (`red-200/red-800`) | stock <= 0 AND velocity > 0 | Proven demand, no stock. Order ASAP. |
| 2 | `urgent` | Urgent | Red (`red-100/red-700`) | days_to_stockout <= lead_time | Will stock out before shipment arrives. Act today. |
| 3 | `reorder` | Reorder | Amber (`amber-100/amber-700`) | days_to_stockout <= lead_time + buffer | Time to order. Include in next PO. |
| 4 | `healthy` | Healthy | Green (`green-100/green-700`) | days_to_stockout > threshold | Pipeline flowing. Order on normal cycle. |
| 5 | `dead_stock` | Dead Stock | Gray (`gray-100/gray-500`) | stock > 0 AND velocity = 0 | Not moving. Don't order. |
| 6 | `out_of_stock` | Out of Stock | Light gray (`gray-50/gray-400`) | stock <= 0 AND velocity = 0 | Unknown demand (nothing to sell). Investigate. |
| 7 | `no_data` | No Data | Light gray (`gray-50/gray-400`) | No transaction history | Investigate. |

### Capital Priority Stack

1. **Lost Sales** — plug the bleeding (proven demand, zero stock)
2. **Urgent** — prevent the next bleed (will run out before shipment)
3. **Reorder** — keep the pipeline flowing (approaching reorder point)
4. **Healthy** — maintain on normal order cycle
5. **Dead Stock / Out of Stock / No Data** — don't spend here without investigation

### Key Design Decisions

**"Lost Sales" not "Stocked Out":** Communicates business impact (revenue loss), not just inventory state. More actionable — the team understands money language.

**"Urgent" not "Critical":** "Critical" describes severity abstractly. "Urgent" tells you to act NOW. Combined with "Reorder" (the normal action), the pair is clear: urgent = emergency, reorder = planned.

**"Reorder" not "Warning" or "Reorder Soon":** "Warning" is vague. "Reorder Soon" is confusing next to "Reorder Now" — both say order, so what's the difference? Just "Reorder" means "it's time" without implying you should wait.

**"Healthy" not "OK":** "OK" implies "ignore." "Healthy" implies "this item is doing well, keep doing what you're doing." Important distinction for hot sellers with deep stock.

**"Dead Stock" separate from "Out of Stock":** Dead Stock = stock on hand, nobody buying. True dead inventory. Out of Stock = nothing to sell, so velocity is zero by definition — doesn't mean there's no demand. Different actions: dead stock = stop ordering, out of stock = investigate whether to restock.

### Mapping from Old to New

| Old Status | New Status | Notes |
|-----------|-----------|-------|
| `stocked_out` | `lost_sales` | Renamed for clarity |
| `critical` | `urgent` | Renamed for clarity |
| `warning` | `reorder` | Renamed for clarity |
| `ok` | `healthy` | Renamed for clarity |
| `no_demand` | `dead_stock` | Renamed for clarity |
| `out_of_stock` | `out_of_stock` | Key unchanged, kept separate from dead_stock |
| `no_data` | `no_data` | Unchanged |

### Scope of Changes

**Status determination logic and thresholds are unchanged — only the string labels returned change.**

#### Backend

**`src/engine/reorder.py`** — `determine_reorder_status()`:
- Return new status key strings
- Update the `must_stock` override: `status in ("ok",)` becomes `status in ("healthy",)`

**`src/engine/aggregation.py`** — `compute_brand_metrics()`:
- Status comparison strings: `"critical"` → `"urgent"`, `"warning"` → `"reorder"`, `"ok"` → `"healthy"`, `"stocked_out"` → `"lost_sales"`, `"no_demand"` → `"dead_stock"`
- Counter variable names and output dict keys renamed (see Database section)

**`src/engine/pipeline.py`**:
- Any hardcoded status strings (e.g. fallback `"out_of_stock"`, `"no_demand"`)
- `no_data` is assigned at the pipeline level, not inside `determine_reorder_status()`

**`src/api/routes/skus.py`**:
- Status filter query param documentation
- `SkuCounts` dict keys
- `status_thresholds` and `status_reason` format strings
- Default filter values on `list_critical_skus`

**`src/api/routes/po.py`**:
- Hardcoded status filter lists (`["critical", "out_of_stock"]` → `["urgent", "lost_sales"]`, etc.)

**`src/api/routes/brands.py`**:
- SQL `CASE WHEN reorder_status=` strings in dashboard summary query

#### Frontend

**`src/dashboard/src/lib/types.ts`**:
- `ReorderStatus` union type updated
- `SkuCounts` interface: `critical` → `urgent`, `warning` → `reorder`, `ok` → `healthy`

**`src/dashboard/src/components/StatusBadge.tsx`**:
- New status config with updated labels and colors
- All 7 statuses must have explicit entries

**`src/dashboard/src/components/CalculationBreakdown.tsx`**:
- `statusColors`: explicit entries for all 7 statuses (currently missing `stocked_out`, `no_demand`)
- `verdictBgColors`: explicit entries for all 7 statuses (currently missing `lost_sales`, `dead_stock`)
- `generateVerdict()`: `lost_sales` gets its own verdict (not cross-mapped to `critical`/`urgent`)
- Verdict text updated with new action-oriented language

**Dashboard pages with hardcoded status strings:**
- `Home.tsx` — status comparisons and label strings
- `BrandOverview.tsx` — status derivation, sort columns
- `CriticalSkus.tsx` — status filter values, type assertions, urgency tier logic
- `SkuDetail.tsx` — status filter values
- `DeadStock.tsx` — status badge props
- `OverrideReview.tsx` — status badge props
- `UniversalSearch.tsx` — `critical_skus` label display
- `src/dashboard/src/lib/api.ts` — `is_dead_stock` status override logic

**URL routes stay unchanged** — `/critical-skus` etc. are internal routes, not user-facing labels. Display labels on the page change but URLs don't.

#### Database

**Migration (new file `src/db/migrations/uc_004_status_rename.sql`):**

1. Rename `brand_metrics` columns:
   - `critical_skus` → `urgent_skus`
   - `warning_skus` → `reorder_skus`
   - `ok_skus` → `healthy_skus`
   - `stocked_out_skus` → `lost_sales_skus`
   - `no_demand_skus` → `dead_stock_skus`

2. Update `sku_metrics.reorder_status` values:
   ```sql
   UPDATE sku_metrics SET reorder_status = CASE reorder_status
     WHEN 'stocked_out' THEN 'lost_sales'
     WHEN 'critical' THEN 'urgent'
     WHEN 'warning' THEN 'reorder'
     WHEN 'ok' THEN 'healthy'
     WHEN 'no_demand' THEN 'dead_stock'
     ELSE reorder_status
   END;
   ```

Column rename is preferred over keeping old names — a mismatch between column names and status values would be a persistent source of confusion.

#### Tests

All test files asserting status strings need updating:
- `test_reorder.py`
- `test_reorder_edge_cases.py`
- `test_reorder_operations.py`
- `test_reorder_simulations.py`
- `test_formula_consistency.py`
- `test_skus_pagination.py`

#### Color Changes

`out_of_stock` changes from red (`bg-red-50 text-red-600`) to gray (`bg-gray-50 text-gray-400`). This is intentional — it's now a lower-priority "investigate" status, not an alarm. The old red color made sense when "Out of Stock" was confused with "Stocked Out" (now "Lost Sales"). With the distinction clear, `out_of_stock` = unknown demand = gray.

### `is_dead_stock` Boolean — Keep For Now

The existing `is_dead_stock` flag (computed in `skus.py` as `stock > 0 AND no sale in X days`) is related but not identical to the `dead_stock` reorder status (`stock > 0 AND velocity = 0`). An item could have some velocity (from early-period sales) but still be flagged `is_dead_stock` (no RECENT sales). Keep both for now — the Dead Stock page uses `is_dead_stock` for filtering. Can be consolidated in a future cleanup.

### Intent Override Behavior (unchanged logic, new strings)

- `must_stock` with no velocity: force `reorder` (was `warning`)
- `must_stock` with velocity but `healthy`: bump to `reorder` (check: `status in ("healthy",)`)
- `urgent` stays `urgent` (formula agrees)
- `do_not_reorder`: show calculated status, suppress qty

### What Does NOT Change

- Status determination logic (thresholds, conditions)
- Velocity calculation
- Reorder quantity formula
- Lead time / buffer / coverage period logic
- Override system
- API response shape (just different string values in existing fields)
- URL routes (only display labels change)
