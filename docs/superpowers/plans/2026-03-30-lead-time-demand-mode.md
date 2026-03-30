# Lead Time Demand Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-supplier toggle to control whether lead time demand is included in suggested reorder quantities.

**Architecture:** New `lead_time_demand_mode` column on `suppliers` table. Engine's `determine_reorder_status()` gets an `include_lead_demand` boolean param. All callers (pipeline, targeted_recompute, PO builder, SKU list, effective_values) look up the supplier's mode and pass it through. After deploy, force a pipeline re-run on both local and Railway.

**Tech Stack:** Python/FastAPI, PostgreSQL, React/TypeScript

**Spec:** `docs/superpowers/specs/2026-03-30-lead-time-demand-mode-design.md`

---

## File Map

| File | Change |
|------|--------|
| `src/db/migrations/uc_005_lead_time_demand_mode.sql` | Create — add column to suppliers |
| `src/engine/reorder.py` | Modify — add `include_lead_demand` param |
| `src/engine/effective_values.py` | Modify — pass through param |
| `src/engine/pipeline.py` | Modify — look up mode from supplier, pass to reorder |
| `src/engine/targeted_recompute.py` | Modify — same |
| `src/api/routes/suppliers.py` | Modify — accept/return new field |
| `src/api/routes/po.py` | Modify — look up mode, allow override |
| `src/api/routes/skus.py` | Modify — look up mode for effective recalc |
| `src/dashboard/src/pages/SupplierManagement.tsx` | Modify — add dropdown |
| `src/dashboard/src/pages/PoBuilder.tsx` | Modify — show mode, allow override |
| `src/dashboard/src/components/CalculationBreakdown.tsx` | Modify — show correct formula |
| `src/dashboard/src/pages/docs/Calculations.tsx` | Modify — document both modes |
| `src/tests/test_reorder.py` | Modify — add coverage_only tests |
| `start.sh` | Modify — add uc_005 migration check |

---

### Task 1: Database Migration + Engine Core

**Files:**
- Create: `src/db/migrations/uc_005_lead_time_demand_mode.sql`
- Modify: `src/engine/reorder.py`
- Modify: `src/engine/effective_values.py`
- Modify: `src/tests/test_reorder.py`
- Modify: `start.sh`

- [ ] **Step 1: Create migration**

```sql
-- uc_005_lead_time_demand_mode.sql
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS lead_time_demand_mode TEXT NOT NULL DEFAULT 'full';
```

Run locally:
```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -f src/db/migrations/uc_005_lead_time_demand_mode.sql
```

- [ ] **Step 2: Update start.sh**

Add uc_005 check after uc_004 block. Check for the column:
```python
cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='suppliers' AND column_name='lead_time_demand_mode')")
if not cur.fetchone()[0]:
    print('Running uc_005 migration...')
    with open('db/migrations/uc_005_lead_time_demand_mode.sql') as f:
        cur.execute(f.read())
    conn.commit()
    print('uc_005 applied.')
else:
    print('uc_005 already applied.')
```

- [ ] **Step 3: Add `include_lead_demand` param to `determine_reorder_status()`**

In `src/engine/reorder.py`, add the parameter:

```python
def determine_reorder_status(
    current_stock: float,
    days_to_stockout: float | None,
    supplier_lead_time: int,
    total_velocity: float,
    safety_buffer: float = 1.3,
    coverage_period: int = 0,
    reorder_intent: str = "normal",
    open_purchase: float = 0,
    include_lead_demand: bool = True,  # NEW
) -> tuple[str, float | None]:
```

Modify the suggested qty calculation (lines ~132-137):
```python
    # Compute suggested quantity
    suggested_qty = None
    if total_velocity > 0:
        order_for_coverage = total_velocity * coverage_period * safety_buffer
        if include_lead_demand:
            demand_during_lead = total_velocity * supplier_lead_time
            suggested_qty = max(0, round(demand_during_lead + order_for_coverage - effective_stock))
        else:
            suggested_qty = max(0, round(order_for_coverage - effective_stock))
        if suggested_qty == 0:
            suggested_qty = None
```

Update the docstring to document both modes.

**Status logic is NOT changed** — only the suggested_qty calculation.

- [ ] **Step 4: Update `compute_effective_status()` in effective_values.py**

Add `include_lead_demand` param and pass through:

```python
def compute_effective_status(
    eff_stock: float,
    eff_total: float,
    lead_time: int = DEFAULT_LEAD_TIME,
    safety_buffer: float = 1.3,
    coverage_period: int = 90,
    include_lead_demand: bool = True,  # NEW
) -> dict:
    eff_days = calculate_days_to_stockout(eff_stock, eff_total)
    eff_status, eff_suggested = determine_reorder_status(
        eff_stock, eff_days, lead_time, eff_total,
        safety_buffer=safety_buffer, coverage_period=coverage_period,
        include_lead_demand=include_lead_demand,  # NEW
    )
    ...
```

- [ ] **Step 5: Write tests for coverage_only mode**

In `src/tests/test_reorder.py`, add:

```python
def test_coverage_only_mode_zero_stock():
    """Coverage-only mode: stock=0 should not include lead demand."""
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=False,
    )
    # order_for_coverage = 3.88 * 90 * 1.3 = 454
    # suggested = max(0, 454 - 0) = 454
    assert qty == 454
    assert status == "lost_sales"

def test_coverage_only_mode_with_stock():
    """Coverage-only with stock: stock offsets coverage demand."""
    status, qty = determine_reorder_status(
        current_stock=100, days_to_stockout=25.8, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=False,
    )
    # order_for_coverage = 3.88 * 90 * 1.3 = 454
    # suggested = max(0, 454 - 100) = 354
    assert qty == 354

def test_full_mode_unchanged():
    """Full mode (default): same as before."""
    status, qty = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=True,
    )
    # demand_lead = 3.88 * 90 = 349.2
    # order_cov = 3.88 * 90 * 1.3 = 454
    # suggested = max(0, 349 + 454 - 0) = 803
    assert qty == 803

def test_default_is_full_mode():
    """Default param should be True (full mode)."""
    _, qty_default = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
    )
    _, qty_full = determine_reorder_status(
        current_stock=0, days_to_stockout=0, supplier_lead_time=90,
        total_velocity=3.88, safety_buffer=1.3, coverage_period=90,
        include_lead_demand=True,
    )
    assert qty_default == qty_full
```

Run tests:
```bash
cd src && ./venv/Scripts/python -m pytest tests/test_reorder.py -v --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add src/db/migrations/uc_005_lead_time_demand_mode.sql src/engine/reorder.py src/engine/effective_values.py src/tests/test_reorder.py start.sh
git commit -m "feat: add include_lead_demand param to reorder formula

Per-supplier toggle: 'full' (default) includes lead time demand,
'coverage_only' excludes it from suggested qty. Status unchanged.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Pipeline + Targeted Recompute Integration

**Files:**
- Modify: `src/engine/pipeline.py`
- Modify: `src/engine/targeted_recompute.py`

- [ ] **Step 1: Update `fetch_all_supplier_mappings()` in pipeline.py**

Add `lead_time_demand_mode` to the SELECT and the mapping dict:

In the SQL query (~line 502), add `s.lead_time_demand_mode` to the SELECT.

In the dict construction (~line 509-516), add:
```python
"lead_time_demand_mode": row[7] if len(row) > 7 else "full",
```

Actually, read the file first and use the correct row index based on the column order in the SELECT.

- [ ] **Step 2: Pass `include_lead_demand` to both `determine_reorder_status` calls in pipeline.py**

There are two call sites (~lines 207 and 386). At each, compute:
```python
include_lead = supplier.get("lead_time_demand_mode", "full") != "coverage_only" if supplier else True
```

Then add `include_lead_demand=include_lead` to the `determine_reorder_status()` call.

- [ ] **Step 3: Update targeted_recompute.py**

Read the file. Find where supplier info is looked up and where `determine_reorder_status` is called. Add the same `include_lead_demand` passthrough.

The supplier lookup in targeted_recompute.py may need to include `lead_time_demand_mode` — check the query that fetches supplier data and add the column if needed.

- [ ] **Step 4: Run tests**

```bash
cd src && ./venv/Scripts/python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
git add src/engine/pipeline.py src/engine/targeted_recompute.py
git commit -m "feat: pipeline and targeted_recompute pass lead_time_demand_mode through

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Backend API Updates

**Files:**
- Modify: `src/api/routes/suppliers.py`
- Modify: `src/api/routes/po.py`
- Modify: `src/api/routes/skus.py`

- [ ] **Step 1: Update suppliers.py**

Add `lead_time_demand_mode` to `SupplierCreate` and `SupplierUpdate` models:

```python
class SupplierCreate(BaseModel):
    ...
    lead_time_demand_mode: str = "full"

    @field_validator('lead_time_demand_mode')
    @classmethod
    def validate_demand_mode(cls, v):
        if v not in ('full', 'coverage_only'):
            raise ValueError('lead_time_demand_mode must be "full" or "coverage_only"')
        return v
```

Add `lead_time_demand_mode` to `ALLOWED_SUPPLIER_COLUMNS` in `update_supplier`.

Add it to the `recalc_fields` set so changing it triggers recalculation.

Add `lead_time_demand_mode` to the INSERT column list in `create_supplier`.

- [ ] **Step 2: Update po.py**

Add a query param `demand_mode` to the `po_data` endpoint:
```python
demand_mode: str = Query(None, description="Override: 'full' or 'coverage_only'. Defaults to supplier setting.")
```

Look up the supplier's `lead_time_demand_mode` if not overridden. Pass `include_lead_demand` to the qty calculation in `_compute_po_items()`.

Add `include_lead_demand` param to `_compute_po_items()` and use it in the suggested qty calculation (~line 88-92).

- [ ] **Step 3: Update skus.py**

In the `list_skus` function, where `compute_effective_status()` is called (~line 210), look up the supplier's mode and pass `include_lead_demand`:

```python
include_lead = supplier_mode != "coverage_only"
st = compute_effective_status(vals["eff_stock"], vals["eff_total"], lead_time,
    float(d["safety_buffer"] or 1.3), coverage_period=coverage_period,
    include_lead_demand=include_lead)
```

The supplier mode lookup should happen once before the loop (like the coverage_period lookup already does).

Also update the breakdown endpoint if it exists — the calculation breakdown should reflect the correct mode.

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/suppliers.py src/api/routes/po.py src/api/routes/skus.py
git commit -m "feat: API routes pass lead_time_demand_mode through

- Suppliers API: accept/validate/return new field, trigger recalc on change
- PO builder: look up supplier mode, allow per-order override
- SKU list: pass mode to effective status recalc

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Frontend — Supplier UI + PO Builder

**Files:**
- Modify: `src/dashboard/src/pages/SupplierManagement.tsx`
- Modify: `src/dashboard/src/pages/PoBuilder.tsx`
- Modify: `src/dashboard/src/components/CalculationBreakdown.tsx`

- [ ] **Step 1: Add dropdown to SupplierManagement.tsx**

Read the file. Find where supplier fields are edited (lead_time_default, lead_time_sea, etc.). Add a Select dropdown:

```tsx
<Select
  value={supplier.lead_time_demand_mode || 'full'}
  onValueChange={(v) => updateSupplier(supplier.id, { lead_time_demand_mode: v })}
>
  <SelectTrigger>
    <SelectValue />
  </SelectTrigger>
  <SelectContent>
    <SelectItem value="full">Full (lead + coverage)</SelectItem>
    <SelectItem value="coverage_only">Coverage only</SelectItem>
  </SelectContent>
</Select>
```

Add a label like "Order Quantity Mode" with a HelpTip explaining the difference.

- [ ] **Step 2: Add toggle to PoBuilder.tsx**

Read the file. Find where lead_time and coverage_days controls are. Add a toggle/select for demand mode:

- Show the supplier's default mode
- Allow per-order override
- Add state: `const [demandMode, setDemandMode] = useState<string | null>(null)` (null = use supplier default)
- Pass to the API call as `demand_mode` query param

- [ ] **Step 3: Update CalculationBreakdown.tsx**

Read the file. The breakdown endpoint may already return formula text. If the breakdown response includes the mode, adjust the display. Otherwise, check if the formula text from the API already reflects the mode.

At minimum: if the formula shows "demand_during_lead" but the supplier is coverage_only, the display should match.

- [ ] **Step 4: Build frontend**

```bash
cd src/dashboard && npm run build 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/src/pages/SupplierManagement.tsx src/dashboard/src/pages/PoBuilder.tsx src/dashboard/src/components/CalculationBreakdown.tsx
git commit -m "feat: frontend UI for lead time demand mode

- Supplier page: dropdown to set mode per supplier
- PO builder: shows mode, allows per-order override
- CalculationBreakdown: displays correct formula

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Update Docs + Tests

**Files:**
- Modify: `src/dashboard/src/pages/docs/Calculations.tsx`
- Modify: `src/tests/test_reorder.py` (if not already done in Task 1)

- [ ] **Step 1: Update Calculations.tsx**

In the "Reorder Formula" section, add a note about the two modes:

After the formula block, add a CalloutBox:
```
Two modes are available per supplier (set on the Suppliers page):

**Full (default):** suggested = demand_lead + order_coverage − stock
Orders enough for lead time wait + coverage period. Larger orders, less frequent reordering.

**Coverage only:** suggested = order_coverage − stock
Orders only for the coverage period. Smaller orders, but you may need to reorder sooner.
```

- [ ] **Step 2: Verify all tests pass**

```bash
cd src && ./venv/Scripts/python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/docs/Calculations.tsx src/tests/
git commit -m "feat: document lead time demand modes in docs + verify tests

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Pipeline Re-run + Push + Deploy

- [ ] **Step 1: Re-run pipeline locally**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -c "
from extraction.data_loader import get_db_connection
from engine.pipeline import run_computation_pipeline
db_conn = get_db_connection()
run_computation_pipeline(db_conn)
db_conn.close()
print('Pipeline complete.')
"
```

This recomputes all sku_metrics and brand_metrics with the latest formula (all suppliers default to 'full', so numbers should be unchanged).

- [ ] **Step 2: Verify locally**

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "
SELECT reorder_status, COUNT(*), ROUND(AVG(reorder_qty_suggested)) AS avg_qty
FROM sku_metrics
WHERE reorder_qty_suggested IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC
"
```

- [ ] **Step 3: Push to main**

```bash
cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject"
git push origin main
```

- [ ] **Step 4: Force pipeline rebuild on Railway**

The deploy will run start.sh which applies uc_005 migration. To force a pipeline rebuild, we need positions to be recalculated. The simplest way: after deploy, trigger via the sync endpoint or set the positions count check to trigger.

Actually, the cleanest approach: update start.sh to force a pipeline run after uc_005 is applied. Add inside the uc_005 block:

```python
print('Rebuilding pipeline with new formula...')
from engine.pipeline import run_computation_pipeline
db_conn2 = get_db_connection()
run_computation_pipeline(db_conn2)
db_conn2.close()
print('Pipeline rebuild complete.')
```

Wait — start.sh runs Python inline. The pipeline import may not work in that context. Instead, add a flag file approach or just ensure the positions check triggers. Actually, the simplest: after uc_005 is applied, truncate brand_metrics so the positions check sees "0 positions" isn't quite right either...

Better approach: In start.sh, after uc_005 migration, run the pipeline rebuild as a separate Python command:

```bash
# After uc_005 applied, force pipeline rebuild
echo "Rebuilding pipeline..."
PYTHONPATH=. python -c "
from extraction.data_loader import get_db_connection
from engine.pipeline import run_computation_pipeline
db = get_db_connection()
run_computation_pipeline(db)
db.close()
"
echo "Pipeline rebuild complete."
```

Add this ONLY inside the uc_005 block so it runs once.

- [ ] **Step 5: Verify on Railway**

After deploy (~5-10 min with pipeline rebuild), verify at https://reorder.artlounge.in:
- Supplier page shows "Order Quantity Mode" dropdown
- Changing a supplier to "coverage_only" triggers recalculation
- SKU suggested quantities update accordingly
- PO builder shows mode toggle

- [ ] **Step 6: Test the toggle end-to-end**

1. Pick a supplier (e.g., KOH-I-NOOR)
2. Note the suggested qty for SKU 6312
3. Switch KOH-I-NOOR to "coverage_only"
4. Wait for recalculation (~5 seconds)
5. Verify 6312's suggested qty DECREASED (coverage only = smaller order)
6. Switch back to "full"
7. Verify qty restored to original

This validates the entire chain: UI → API → recalculation → updated metrics.
