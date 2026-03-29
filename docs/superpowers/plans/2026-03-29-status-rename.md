# Reorder Status Simplification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename 7 confusing reorder status labels to actionable, capital-priority-ordered names.

**Architecture:** Pure rename — status determination logic and thresholds are unchanged. Only string values, display labels, colors, DB column names, and test assertions change. The mapping is: `stocked_out` → `lost_sales`, `critical` → `urgent`, `warning` → `reorder`, `ok` → `healthy`, `no_demand` → `dead_stock`. `out_of_stock` and `no_data` keep their keys.

**Tech Stack:** Python/FastAPI backend, React/TypeScript/shadcn frontend, PostgreSQL

**Spec:** `docs/superpowers/specs/2026-03-29-reorder-status-simplification-design.md`

---

### File Map

| File | Change |
|------|--------|
| `src/db/migrations/uc_004_status_rename.sql` | **Create** — rename brand_metrics columns + update sku_metrics values |
| `src/engine/reorder.py` | Modify — status string returns |
| `src/engine/aggregation.py` | Modify — status comparisons + dict keys |
| `src/engine/pipeline.py:743-782,833-851` | Modify — `_BRAND_METRICS_UPSERT_SQL` column names + `_empty_metrics()` status strings |
| `src/api/routes/skus.py` | Modify — query param docs, status filter defaults, SkuCounts keys, status_reason text |
| `src/api/routes/brands.py` | Modify — SQL status strings, ORDER BY column names |
| `src/api/routes/po.py:168-172` | Modify — status filter lists |
| `src/api/routes/search.py` | Modify — if any status strings referenced |
| `src/dashboard/src/lib/types.ts` | Modify — ReorderStatus union, SkuCounts, BrandMetrics, BrandSummary, DashboardSummary, DashboardSummaryBrand, SearchBrandResult |
| `src/dashboard/src/lib/api.ts:42-63` | Modify — EMPTY_SKU_COUNTS keys |
| `src/dashboard/src/components/StatusBadge.tsx` | Modify — config map keys, labels, colors |
| `src/dashboard/src/components/CalculationBreakdown.tsx` | Modify — statusColors, verdictBgColors, generateVerdict() |
| `src/dashboard/src/pages/Home.tsx` | Modify — status labels, card text |
| `src/dashboard/src/pages/BrandOverview.tsx` | Modify — sort options, filter logic, column references |
| `src/dashboard/src/pages/CriticalSkus.tsx` | Modify — tierOf() status checks, filter values/labels |
| `src/dashboard/src/pages/SkuDetail.tsx` | Modify — status filter references |
| `src/dashboard/src/pages/DeadStock.tsx` | Modify — StatusBadge status props |
| `src/dashboard/src/pages/OverrideReview.tsx` | Modify — StatusBadge status props |
| `src/dashboard/src/components/UniversalSearch.tsx` | Modify — `critical_skus` label |
| `src/dashboard/src/components/mobile/MobileListRow.tsx` | Modify — STATUS_BORDER and STATUS_BADGE maps |
| `src/dashboard/src/components/mobile/MobileLayout.tsx` | Check — any status references |
| `src/dashboard/src/lib/tour-steps.ts` | Check — any status text |
| `src/dashboard/src/lib/mobile-tour-steps.ts` | Check — any status text |
| `start.sh` | Modify — add uc_004 migration check |
| `src/tests/test_reorder.py` | Modify — all status assertions |
| `src/tests/test_reorder_edge_cases.py` | Modify — all status assertions |
| `src/tests/test_reorder_operations.py` | Modify — all status assertions |
| `src/tests/test_reorder_simulations.py` | Modify — all status assertions |
| `src/tests/test_formula_consistency.py` | Modify — status assertions |
| `src/tests/test_skus_pagination.py` | Modify — status strings in test data |

---

### Task 1: Database Migration

**Files:**
- Create: `src/db/migrations/uc_004_status_rename.sql`
- Modify: `start.sh`

- [ ] **Step 1: Write the migration SQL**

**Important:** `no_demand_skus` is NOT renamed because `dead_stock_skus` already exists (F19 date-based metric). The column keeps its old name — the aggregation code writes `dead_stock` status counts to it.

```sql
-- uc_004_status_rename.sql
-- Rename reorder status values and brand_metrics columns for clarity.
-- NOTE: no_demand_skus is NOT renamed — dead_stock_skus already exists (F19 metric).

-- 1. Rename brand_metrics columns (4 of 5 — no_demand_skus stays)
DO $$ BEGIN
  ALTER TABLE brand_metrics RENAME COLUMN critical_skus TO urgent_skus;
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE brand_metrics RENAME COLUMN warning_skus TO reorder_skus;
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE brand_metrics RENAME COLUMN ok_skus TO healthy_skus;
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE brand_metrics RENAME COLUMN stocked_out_skus TO lost_sales_skus;
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

-- 2. Update sku_metrics.reorder_status values
UPDATE sku_metrics SET reorder_status = CASE reorder_status
  WHEN 'stocked_out' THEN 'lost_sales'
  WHEN 'critical' THEN 'urgent'
  WHEN 'warning' THEN 'reorder'
  WHEN 'ok' THEN 'healthy'
  WHEN 'no_demand' THEN 'dead_stock'
  ELSE reorder_status
END
WHERE reorder_status IN ('stocked_out', 'critical', 'warning', 'ok', 'no_demand');
```

Save to `src/db/migrations/uc_004_status_rename.sql`. The `DO $$ ... EXCEPTION` blocks make the migration safe to re-run and handle environments where columns may not exist.

- [ ] **Step 2: Update start.sh to run uc_004 on deploy**

In `start.sh`, after the uc_003 check block (around line 39-45), add a check for uc_004. The migration is idempotent — checking if the `urgent_skus` column exists tells us if uc_004 was applied:

```python
# Check if uc_004 needs applying (urgent_skus column indicates it was applied)
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='brand_metrics' AND column_name='urgent_skus')\")
if not cur.fetchone()[0]:
    print('Running uc_004 migration (status rename)...')
    with open('db/migrations/uc_004_status_rename.sql') as f:
        cur.execute(f.read())
    conn.commit()
    print('uc_004 applied.')
else:
    print('uc_004 already applied.')
```

- [ ] **Step 3: Run migration locally**

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -f src/db/migrations/uc_004_status_rename.sql
```

Verify:
```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "SELECT DISTINCT reorder_status FROM sku_metrics ORDER BY 1"
```

Expected: `dead_stock`, `healthy`, `lost_sales`, `no_data`, `out_of_stock`, `reorder`, `urgent` — NO `critical`, `warning`, `ok`, `stocked_out`, `no_demand`.

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "\d brand_metrics" | grep -E "urgent_skus|reorder_skus|healthy_skus|lost_sales_skus"
```

Expected: 4 renamed columns present. (`no_demand_skus` kept as-is, `dead_stock_skus` already exists for F19.)

- [ ] **Step 4: Commit**

```bash
git add src/db/migrations/uc_004_status_rename.sql start.sh
git commit -m "feat: add uc_004 migration for status rename"
```

---

### Task 2: Backend Engine — Status Strings

**Files:**
- Modify: `src/engine/reorder.py`
- Modify: `src/engine/aggregation.py`
- Modify: `src/engine/pipeline.py`

- [ ] **Step 1: Update `reorder.py` — `determine_reorder_status()`**

In `src/engine/reorder.py`, function `determine_reorder_status()` (lines 80-159), change all status string literals:

```python
# Line 118: "stocked_out" → "lost_sales"
raw_status = "lost_sales"

# Line 120: "out_of_stock" stays
raw_status = "out_of_stock"

# Line 122: "no_demand" → "dead_stock"
raw_status = "dead_stock"

# Line 124: "critical" → "urgent"
raw_status = "urgent"

# Line 126: "warning" → "reorder"
raw_status = "reorder"

# Line 128: "ok" → "healthy"
raw_status = "healthy"
```

In the `must_stock` override block:

```python
# Line 145: "warning" → "reorder"
status = "reorder"

# Line 148: ("ok",) → ("healthy",)
elif status in ("healthy",):
    status = "reorder"
```

Also update the docstring (lines 102-108) to match new names.

- [ ] **Step 2: Update `aggregation.py` — `compute_brand_metrics()`**

In `src/engine/aggregation.py`, rename counter variables and status comparisons.

**Note:** `dead_stock` variable already exists (line 36) for F19 date-based dead stock. Use `no_demand_count` for the status counter since the DB column stays `no_demand_skus`.

Lines 30-35 — rename counter variables:
```python
critical = 0      →  urgent = 0
warning = 0       →  reorder_count = 0
ok = 0            →  healthy = 0
stocked_out = 0   →  lost_sales = 0
no_demand = 0     →  no_demand_count = 0   # column stays no_demand_skus
```

Lines 67-78 — update status comparisons:
```python
if status == "urgent":
    urgent += 1
elif status == "reorder":
    reorder_count += 1
elif status == "healthy":
    healthy += 1
elif status == "lost_sales":
    lost_sales += 1
elif status == "dead_stock":
    no_demand_count += 1   # dead_stock status → no_demand_skus column
elif status in ("no_data", "out_of_stock"):
    no_data += 1
```

Lines 109-114 — update dict keys (must match DB column names):
```python
"urgent_skus": urgent,
"reorder_skus": reorder_count,
"healthy_skus": healthy,
"lost_sales_skus": lost_sales,
"no_demand_skus": no_demand_count,   # column NOT renamed (dead_stock_skus already exists)
```

- [ ] **Step 3: Update `pipeline.py` — `_BRAND_METRICS_UPSERT_SQL` + `_empty_metrics()`**

**CRITICAL:** `_BRAND_METRICS_UPSERT_SQL` (lines 743-782) has hardcoded column names that MUST match the DB after migration. Update:

In the INSERT column list (line 746-747):
```python
critical_skus   →  urgent_skus
warning_skus    →  reorder_skus
ok_skus         →  healthy_skus
stocked_out_skus → lost_sales_skus
# no_demand_skus stays unchanged
```

In the VALUES parameters (lines 754-755):
```python
%(critical_skus)s    →  %(urgent_skus)s
%(warning_skus)s     →  %(reorder_skus)s
%(ok_skus)s          →  %(healthy_skus)s
%(stocked_out_skus)s →  %(lost_sales_skus)s
# %(no_demand_skus)s stays unchanged
```

In the ON CONFLICT DO UPDATE SET (lines 765-770):
```python
critical_skus = EXCLUDED.critical_skus     →  urgent_skus = EXCLUDED.urgent_skus
warning_skus = EXCLUDED.warning_skus       →  reorder_skus = EXCLUDED.reorder_skus
ok_skus = EXCLUDED.ok_skus                 →  healthy_skus = EXCLUDED.healthy_skus
stocked_out_skus = EXCLUDED.stocked_out_skus → lost_sales_skus = EXCLUDED.lost_sales_skus
# no_demand_skus stays unchanged
```

Also update `_empty_metrics()` (line 835):
```python
status = "out_of_stock" if current_stock <= 0 else "dead_stock"
```
(Changed `"no_demand"` to `"dead_stock"`.)

- [ ] **Step 5: Run tests to see current failures**

```bash
cd src && ./venv/Scripts/python -m pytest tests/test_reorder.py -v --tb=short 2>&1 | head -60
```

Expected: Tests fail because engine now returns new status strings but tests expect old ones.

- [ ] **Step 6: Commit backend engine changes**

```bash
git add src/engine/reorder.py src/engine/aggregation.py src/engine/pipeline.py src/db/migrations/uc_004_status_rename.sql
git commit -m "feat: rename status strings in engine (lost_sales, urgent, reorder, healthy, dead_stock)"
```

---

### Task 3: Backend API Routes

**Files:**
- Modify: `src/api/routes/skus.py`
- Modify: `src/api/routes/brands.py`
- Modify: `src/api/routes/po.py`
- Modify: `src/api/routes/search.py` (check only)

- [ ] **Step 1: Update `skus.py`**

Line 63 — query param description:
```python
status: str = Query(None, description="Comma-separated: urgent,reorder,healthy,out_of_stock,lost_sales,dead_stock,no_data"),
```

Find all hardcoded status strings in the file and update:
- `"critical"` → `"urgent"`
- `"warning"` → `"reorder"`
- `"ok"` → `"healthy"`
- `"stocked_out"` → `"lost_sales"`
- `"no_demand"` → `"dead_stock"`

Specific locations to update:
- **Line ~301** (list_critical_skus default): `"critical,warning"` → `"urgent,reorder"`
- **Line ~470** (update_xyz_buffer intent override): `status = "critical"` → `status = "urgent"`
- **Lines ~915-919** (status_reason comparisons): `status == "ok"` → `"healthy"`, `"warning"` → `"reorder"`, `"critical"` → `"urgent"`
- **Line ~941** (status_thresholds format string): `"critical: <={lead_time}d | warning: <={threshold}d | ok: >{threshold}d"` → `"urgent: <={lead_time}d | reorder: <={threshold}d | healthy: >{threshold}d"`
- **SkuCounts dict** (lines ~272-278): rename keys `critical` → `urgent`, `warning` → `reorder`, `ok` → `healthy`

- [ ] **Step 2: Update `brands.py`**

Line 21 — ORDER BY:
```python
sql += " ORDER BY urgent_skus DESC, reorder_skus DESC, avg_days_to_stockout ASC NULLS LAST"
```

Lines 31-33 — summary query column references:
```python
SUM(CASE WHEN urgent_skus > 0 THEN 1 ELSE 0 END) AS brands_with_urgent,
SUM(CASE WHEN reorder_skus > 0 THEN 1 ELSE 0 END) AS brands_with_reorder,
```

Note: `brands_with_critical` and `brands_with_warning` are returned in the API response — these field names change to `brands_with_urgent` and `brands_with_reorder`. This cascades to the frontend types.

Lines 65-84 — dashboard_summary SQL:
Replace all `reorder_status='critical'` with `reorder_status='urgent'`, `'warning'` with `'reorder'`, `'ok'` with `'healthy'`, `'out_of_stock'` stays.

Update the response dict keys:
- `a_critical` → `a_urgent`
- `a_warning` → `a_reorder`
- `b_critical` → `b_urgent`
- `b_warning` → `b_reorder`
- `c_critical` → `c_urgent`
- `c_warning` → `c_reorder`
- `total_critical` → `total_urgent`
- `total_warning` → `total_reorder`
- `total_ok` → `total_healthy`

Lines 88-102 — top_brands query:
- `bm.critical_skus` → `bm.urgent_skus`
- `bm.warning_skus` → `bm.reorder_skus`
- `reorder_status = 'critical'` → `reorder_status = 'urgent'`
- `a_critical_skus` alias stays as a computed name but the WHERE changes

- [ ] **Step 3: Update `po.py`**

Line 168:
```python
statuses = ["urgent", "lost_sales"]
```

Line 170:
```python
statuses.append("reorder")
```

Line 172:
```python
statuses.append("healthy")
```

- [ ] **Step 4: Check `search.py`**

Read `src/api/routes/search.py` and check if any status strings are hardcoded. Update if needed.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/skus.py src/api/routes/brands.py src/api/routes/po.py src/api/routes/search.py
git commit -m "feat: update API routes for new status names"
```

---

### Task 4: Frontend Core — Types, StatusBadge, CalculationBreakdown, API

**Files:**
- Modify: `src/dashboard/src/lib/types.ts`
- Modify: `src/dashboard/src/lib/api.ts`
- Modify: `src/dashboard/src/components/StatusBadge.tsx`
- Modify: `src/dashboard/src/components/CalculationBreakdown.tsx`

- [ ] **Step 1: Update `types.ts`**

Line 1 — ReorderStatus:
```typescript
export type ReorderStatus = 'urgent' | 'reorder' | 'healthy' | 'out_of_stock' | 'lost_sales' | 'dead_stock' | 'no_data'
```

Lines 8-27 — BrandMetrics interface:
```typescript
urgent_skus: number        // was critical_skus
reorder_skus: number       // was warning_skus
healthy_skus: number       // was ok_skus
```

Lines 29-40 — BrandSummary:
```typescript
brands_with_urgent: number     // was brands_with_critical
brands_with_reorder: number    // was brands_with_warning
```

Lines 98-105 — SkuCounts:
```typescript
export interface SkuCounts {
  urgent: number
  reorder: number
  healthy: number
  out_of_stock: number
  no_data: number
  dead_stock: number
}
```

Lines 309-350 — DashboardSummary:
```typescript
// ABC x Status
a_urgent: number       // was a_critical
a_reorder: number      // was a_warning
b_urgent: number
b_reorder: number
c_urgent: number
c_reorder: number
// Status totals
total_urgent: number
total_reorder: number
total_healthy: number
total_out_of_stock: number
// Brand summary
brands_with_urgent: number
brands_with_reorder: number
```

Lines 309-317 — DashboardSummaryBrand:
```typescript
urgent_skus: number        // was critical_skus
reorder_skus: number       // was warning_skus
a_urgent_skus: number      // was a_critical_skus
```

Lines 432-436 — SearchBrandResult:
```typescript
urgent_skus: number        // was critical_skus
```

- [ ] **Step 2: Update `api.ts`**

Lines 42-49 — EMPTY_SKU_COUNTS:
```typescript
const EMPTY_SKU_COUNTS: SkuCounts = {
  urgent: 0,
  reorder: 0,
  healthy: 0,
  out_of_stock: 0,
  no_data: 0,
  dead_stock: 0,
}
```

- [ ] **Step 3: Update `StatusBadge.tsx`**

Replace the entire `statusConfig`:
```typescript
const statusConfig: Record<ReorderStatus, { label: string; className: string }> = {
  lost_sales: { label: 'Lost Sales', className: 'bg-red-200 text-red-800 hover:bg-red-200' },
  urgent: { label: 'Urgent', className: 'bg-red-100 text-red-700 hover:bg-red-100' },
  reorder: { label: 'Reorder', className: 'bg-amber-100 text-amber-700 hover:bg-amber-100' },
  healthy: { label: 'Healthy', className: 'bg-green-100 text-green-700 hover:bg-green-100' },
  dead_stock: { label: 'Dead Stock', className: 'bg-gray-100 text-gray-500 hover:bg-gray-100' },
  out_of_stock: { label: 'Out of Stock', className: 'bg-gray-50 text-gray-400 hover:bg-gray-50' },
  no_data: { label: 'No Data', className: 'bg-gray-50 text-gray-400 hover:bg-gray-50' },
}
```

- [ ] **Step 4: Update `CalculationBreakdown.tsx`**

Lines 29-35 — statusColors:
```typescript
const statusColors: Record<string, string> = {
  healthy: 'bg-green-100 text-green-700 border-green-200',
  reorder: 'bg-amber-100 text-amber-700 border-amber-200',
  urgent: 'bg-red-100 text-red-700 border-red-200',
  lost_sales: 'bg-red-200 text-red-800 border-red-300',
  dead_stock: 'bg-gray-100 text-gray-500 border-gray-200',
  out_of_stock: 'bg-gray-50 text-gray-400 border-gray-200',
  no_data: 'bg-gray-100 text-gray-500 border-gray-200',
}
```

Lines 37-43 — verdictBgColors:
```typescript
const verdictBgColors: Record<string, string> = {
  healthy: 'bg-green-50 border-green-300',
  reorder: 'bg-amber-50 border-amber-300',
  urgent: 'bg-red-50 border-red-300',
  lost_sales: 'bg-red-100 border-red-400',
  dead_stock: 'bg-gray-50 border-gray-300',
  out_of_stock: 'bg-gray-50 border-gray-300',
  no_data: 'bg-gray-50 border-gray-300',
}
```

Lines 383-421 — `generateVerdict()` switch cases:
```typescript
case 'urgent':
  return {
    text: `Order ${qty ?? '?'} units now. ${dominantChannel ? `${dominantChannel} is driving demand at ${monthlyVel}/mo.` : `Demand is ${monthlyVel}/mo.`} At current velocity you have ~${days ?? 0} days of stock, but with ${leadTime}-day lead time you need to act today.`,
    status,
  }
case 'reorder':
  return {
    text: `Time to order ${qty ?? '?'} units. You have ~${days ?? 0} days of stock — include this in your next PO.`,
    status,
  }
case 'healthy':
  return {
    text: `Pipeline is flowing. You have ~${days ?? '?'} days of stock, well above the ${leadTime}-day lead time. Keep ordering on your normal cycle.`,
    status,
  }
case 'lost_sales':
  return {
    text: `You're losing sales — proven demand at ${(effective_values.total_velocity * 30).toFixed(1)}/mo but zero stock. Order ${qty ?? '?'} units immediately.`,
    status,
  }
case 'dead_stock':
  return {
    text: `Stock on hand but no recent demand detected. Monitor or mark as do-not-reorder if intentional.`,
    status,
  }
case 'out_of_stock':
  return {
    text: `Out of stock with no measured demand. Investigate whether to restock — demand may exist but can't be measured without inventory.`,
    status,
  }
case 'no_data':
default:
  return {
    text: 'Insufficient data to make a recommendation. No velocity data available.',
    status: 'no_data',
  }
```

- [ ] **Step 5: Build frontend to check for type errors**

```bash
cd src/dashboard && npm run build 2>&1 | head -40
```

Expected: Type errors in pages that still reference old field names (Home.tsx, BrandOverview.tsx, etc.). That's expected — those are Task 5.

- [ ] **Step 6: Commit**

```bash
git add src/dashboard/src/lib/types.ts src/dashboard/src/lib/api.ts src/dashboard/src/components/StatusBadge.tsx src/dashboard/src/components/CalculationBreakdown.tsx
git commit -m "feat: update frontend core types, StatusBadge, and CalculationBreakdown for new statuses"
```

---

### Task 5: Frontend Pages

**Files:**
- Modify: `src/dashboard/src/pages/Home.tsx`
- Modify: `src/dashboard/src/pages/BrandOverview.tsx`
- Modify: `src/dashboard/src/pages/CriticalSkus.tsx`
- Modify: `src/dashboard/src/pages/SkuDetail.tsx`
- Modify: `src/dashboard/src/pages/DeadStock.tsx`
- Modify: `src/dashboard/src/pages/OverrideReview.tsx`
- Modify: `src/dashboard/src/components/UniversalSearch.tsx`

- [ ] **Step 1: Update `Home.tsx`**

Key changes:
- Line 58: `s.a_critical + s.b_critical + s.c_critical` → `s.a_urgent + s.b_urgent + s.c_urgent`
- Line 81-84: "Critical SKUs" label → "Urgent SKUs"
- Line 87: `s.brands_with_critical` → `s.brands_with_urgent`
- Line 98: `s.brands_with_critical` → `s.brands_with_urgent`
- Line 126: `brand.critical_skus` → `brand.urgent_skus`, `brand.warning_skus` → `brand.reorder_skus`
- Status derivation: `'critical'` → `'urgent'`, `'warning'` → `'reorder'`, `'ok'` → `'healthy'`
- Status labels: `"critical"` → `"urgent"`, `"warning"` → `"reorder"`
- MobileListRow metrics labels: "Critical" → "Urgent", "Warning" → "Reorder"
- Desktop table headers: "Critical" → "Urgent", "Warning" → "Reorder"

- [ ] **Step 2: Update `BrandOverview.tsx`**

Key changes:
- BRAND_SORT_OPTIONS: `'critical_skus'` → `'urgent_skus'`, label "Critical SKUs" → "Urgent SKUs"
- Default sort: `'critical_skus'` → `'urgent_skus'`
- Filter: `b.critical_skus` → `b.urgent_skus`, `b.warning_skus` → `b.reorder_skus`
- All display text: "critical" → "urgent", "warning" → "reorder"

- [ ] **Step 3: Update `CriticalSkus.tsx`**

Key changes:
- `tierOf()` function: `status === 'critical'` → `status === 'urgent'`
- Page title: "Critical SKUs — Triage" → "Priority SKUs — Triage" (or keep as-is, since the URL doesn't change)
- Default status filter: `'critical,warning'` → `'urgent,reorder'`
- Filter options:
  ```
  { value: 'urgent,reorder', label: 'Urgent & Reorder' }
  { value: 'urgent', label: 'Urgent Only' }
  { value: 'reorder', label: 'Reorder Only' }
  { value: 'out_of_stock', label: 'Out of Stock' }
  ```
- StatusBadge type assertion: update union to new status values
- Tier descriptions: update any references to "critical" → "urgent"

- [ ] **Step 4: Update remaining pages**

**`SkuDetail.tsx`**: Search for any hardcoded `"critical"`, `"warning"`, `"ok"` strings and replace.

**`DeadStock.tsx`**: Update any StatusBadge status props from old to new values.

**`OverrideReview.tsx`**: Update StatusBadge status props.

**`UniversalSearch.tsx`**: `critical_skus` → `urgent_skus` in display label.

- [ ] **Step 5: Update `MobileListRow.tsx`**

Lines 4-10 — STATUS_BORDER map:
```typescript
const STATUS_BORDER: Record<string, string> = {
  urgent: 'border-l-red-500',
  reorder: 'border-l-amber-500',
  healthy: 'border-l-green-500',
  lost_sales: 'border-l-red-600',
  dead_stock: 'border-l-gray-400',
  out_of_stock: 'border-l-gray-400',
  no_data: 'border-l-gray-400',
}
```

Lines 12-18 — STATUS_BADGE map:
```typescript
const STATUS_BADGE: Record<string, string> = {
  urgent: 'bg-red-900/60 text-red-300',
  reorder: 'bg-amber-900/60 text-amber-300',
  healthy: 'bg-green-900/60 text-green-300',
  lost_sales: 'bg-red-900/80 text-red-200',
  dead_stock: 'bg-gray-800 text-gray-400',
  out_of_stock: 'bg-gray-800 text-gray-400',
  no_data: 'bg-gray-800 text-gray-400',
}
```

- [ ] **Step 6: Update tour-step text**

Check `src/dashboard/src/lib/tour-steps.ts` and `mobile-tour-steps.ts` for references to "critical" or "warning" in user-facing text. Replace with "urgent" and "reorder" as appropriate.

- [ ] **Step 7: Build frontend — verify zero errors**

```bash
cd src/dashboard && npm run build 2>&1
```

Expected: Clean build with no TypeScript errors.

- [ ] **Step 8: Commit**

```bash
git add src/dashboard/src/pages/ src/dashboard/src/components/UniversalSearch.tsx src/dashboard/src/components/mobile/MobileListRow.tsx src/dashboard/src/lib/tour-steps.ts src/dashboard/src/lib/mobile-tour-steps.ts
git commit -m "feat: update all frontend pages for new status labels"
```

---

### Task 6: Tests

**Files:**
- Modify: `src/tests/test_reorder.py`
- Modify: `src/tests/test_reorder_edge_cases.py`
- Modify: `src/tests/test_reorder_operations.py`
- Modify: `src/tests/test_reorder_simulations.py`
- Modify: `src/tests/test_formula_consistency.py`
- Modify: `src/tests/test_skus_pagination.py`

- [ ] **Step 1: Global search-and-replace in test files**

In ALL test files, replace status assertion strings:
- `"stocked_out"` → `"lost_sales"`
- `"critical"` → `"urgent"`
- `"warning"` → `"reorder"`
- `"ok"` → `"healthy"`
- `"no_demand"` → `"dead_stock"`

Be careful: only replace status VALUE strings, not other uses of these words (e.g. comments, variable names). The status values appear inside assert statements and test data dicts like `"reorder_status": "critical"`.

- [ ] **Step 2: Run all tests**

```bash
cd src && ./venv/Scripts/python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/tests/
git commit -m "test: update all status assertions for new status names"
```

---

### Task 7: Verify End-to-End Locally

- [ ] **Step 1: Start API server**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000
```

- [ ] **Step 2: Hit the API and verify new status strings**

```bash
curl -s http://localhost:8000/api/brands | python -m json.tool | head -20
```

Verify: column names include `urgent_skus`, `reorder_skus`, `healthy_skus`, `lost_sales_skus`. (`no_demand_skus` kept as-is.)

```bash
curl -s "http://localhost:8000/api/brands/DALER%20ROWNEY/skus?paginated=true&limit=5" | python -m json.tool | grep reorder_status
```

Verify: status values are from the new set.

- [ ] **Step 3: Build and test frontend**

```bash
cd src/dashboard && npm run build
```

Open browser at `http://localhost:8000` (or dev server) and verify:
- StatusBadges show new labels (Urgent, Reorder, Healthy, Lost Sales, Dead Stock)
- Home page cards show "Urgent SKUs" not "Critical SKUs"
- Brand overview sorts by `urgent_skus`
- CriticalSkus page filter options show new labels
- CalculationBreakdown verdict text uses new language

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix: address any remaining status rename issues"
```

---

### Task 8: Push and Deploy

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

This triggers Railway auto-deploy. The `start.sh` migration runner will apply `uc_004_status_rename.sql` on Railway automatically.

- [ ] **Step 2: Verify Railway deployment**

After deploy completes (~2 min), verify at `https://reorder.artlounge.in`:
- Dashboard loads with new status labels
- SKU detail pages show new status badges
- No console errors
