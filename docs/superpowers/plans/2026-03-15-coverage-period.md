# Coverage Period Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reorder formula so it orders enough stock for a configurable coverage period (not just the lead time), with smart auto-defaults based on turns-per-year logic, and a PO Builder control to adjust per-order.

**Architecture:** The existing `typical_order_months` column in the `suppliers` table (default 6, currently unused in formulas) becomes the source for coverage period. A new helper `compute_coverage_days(lead_time, typical_order_months)` computes the coverage in days, with auto-calculation from lead time when not set. The reorder formula changes from `velocity × lead_time × buffer` to `velocity × (lead_time + coverage_days) × buffer`. The PO Builder gets a coverage days input that defaults to the supplier setting but can be adjusted per-PO for working capital or strategic reasons.

**Tech Stack:** Python/FastAPI backend, React/TypeScript frontend, PostgreSQL

**Key insight from user:** "If a supplier takes 120 days by ship, max you can do is 3 turns in a financial year. The system should pre-emptively decide this. But in the PO Builder, you should be able to change coverage days if you have more/less capital."

---

## Chunk 1: Backend Engine & Pipeline

### Task 1: Add coverage_days helper to reorder.py

**Files:**
- Modify: `src/engine/reorder.py`
- Test: `src/tests/test_reorder.py`

- [ ] **Step 1: Write tests for compute_coverage_days**

```python
# src/tests/test_reorder.py — append to existing file

from engine.reorder import compute_coverage_days

def test_coverage_days_from_typical_months():
    """When supplier has typical_order_months set, use it."""
    assert compute_coverage_days(lead_time=120, typical_order_months=6) == 180

def test_coverage_days_from_typical_months_3():
    assert compute_coverage_days(lead_time=90, typical_order_months=3) == 90

def test_coverage_days_auto_from_lead_time():
    """When typical_order_months is None, auto-calculate from turns logic."""
    # 120-day lead time: 365//120 = 3 turns, 365//3 = 121 days per cycle
    result = compute_coverage_days(lead_time=120, typical_order_months=None)
    assert result == 121

def test_coverage_days_auto_90():
    # 90-day lead time: 365//90 = 4 turns, 365//4 = 91
    result = compute_coverage_days(lead_time=90, typical_order_months=None)
    assert result == 91

def test_coverage_days_auto_180():
    # 180-day lead time: 365//180 = 2 turns, 365//2 = 182
    result = compute_coverage_days(lead_time=180, typical_order_months=None)
    assert result == 182

def test_coverage_days_auto_30():
    # 30-day lead time: 365//30 = 12, but cap at 6 turns → 365//6 = 60
    result = compute_coverage_days(lead_time=30, typical_order_months=None)
    assert result == 60

def test_coverage_days_auto_very_long():
    # 300-day lead time: 365//300 = 1 turn, 365//1 = 365
    result = compute_coverage_days(lead_time=300, typical_order_months=None)
    assert result == 365
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_reorder.py -v -k "coverage_days"`
Expected: FAIL — `ImportError: cannot import name 'compute_coverage_days'`

- [ ] **Step 3: Implement compute_coverage_days**

Add to `src/engine/reorder.py` after the `DEFAULT_LEAD_TIME` constant:

```python
def compute_coverage_days(lead_time: int, typical_order_months: int | None = None) -> int:
    """Compute coverage period in days for the reorder formula.

    If typical_order_months is set (per-supplier config), use it directly.
    Otherwise, auto-calculate from lead time using turns-per-year logic:
    the number of order cycles that fit in a financial year, capped at 6.
    """
    if typical_order_months is not None:
        return typical_order_months * 30

    # Auto-calculate: how many turns fit in a year?
    fy_days = 365
    max_turns = max(1, fy_days // lead_time)
    # Cap at 6 turns — ordering more than every 2 months is impractical
    # for an import business with min order quantities
    turns = min(max_turns, 6)
    return fy_days // turns
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_reorder.py -v -k "coverage_days"`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/engine/reorder.py src/tests/test_reorder.py
git commit -m "feat: add compute_coverage_days helper for reorder formula"
```

---

### Task 2: Update determine_reorder_status to use coverage_period

**Files:**
- Modify: `src/engine/reorder.py:47-84`
- Test: `src/tests/test_reorder.py`

- [ ] **Step 1: Write tests for updated formula**

```python
# src/tests/test_reorder.py — append

from engine.reorder import determine_reorder_status

def test_reorder_qty_includes_coverage():
    """Suggested qty should cover lead_time + coverage_period, not just lead_time."""
    # velocity=2, lead_time=120, coverage=180, buffer=1.3, stock=240
    # raw_need = 2 * (120 + 180) * 1.3 = 2 * 300 * 1.3 = 780
    # suggested = 780 - 240 = 540
    status, qty = determine_reorder_status(
        current_stock=240, days_to_stockout=120.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "critical"
    assert qty == 540

def test_reorder_qty_zero_coverage_matches_old():
    """With coverage_period=0, formula matches the old behavior."""
    # velocity=2, lead_time=120, buffer=1.3, stock=240
    # raw_need = 2 * (120 + 0) * 1.3 = 312
    # suggested = 312 - 240 = 72
    status, qty = determine_reorder_status(
        current_stock=240, days_to_stockout=120.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=0,
    )
    assert status == "critical"
    assert qty == 72

def test_warning_thresholds_use_lead_time_not_coverage():
    """Warning/critical thresholds should still be based on lead_time only."""
    # 200 days of stock, lead_time=120, warning_buffer=max(30,60)=60
    # 200 > 120+60=180 → OK (even though coverage_period is 180)
    status, qty = determine_reorder_status(
        current_stock=400, days_to_stockout=200.0,
        supplier_lead_time=120, total_velocity=2.0,
        safety_buffer=1.3, coverage_period=180,
    )
    assert status == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_reorder.py -v -k "reorder_qty_includes_coverage or reorder_qty_zero_coverage or warning_thresholds_use"`
Expected: FAIL — `TypeError: unexpected keyword argument 'coverage_period'`

- [ ] **Step 3: Update determine_reorder_status**

In `src/engine/reorder.py`, update the function signature and formula at line 47-65:

```python
def determine_reorder_status(
    current_stock: float,
    days_to_stockout: float | None,
    supplier_lead_time: int,
    total_velocity: float,
    safety_buffer: float = 1.3,
    coverage_period: int = 0,
) -> tuple[str, float | None]:
    """
    Determine reorder status and suggested order quantity.

    coverage_period: additional days of stock beyond lead time. The total
    ordering window is (lead_time + coverage_period). Warning/critical
    thresholds still use lead_time only (they control WHEN to order,
    not HOW MUCH).
    """
    if total_velocity <= 0:
        if current_stock <= 0:
            return ("out_of_stock", None)
        return ("no_data", None)

    raw_need = total_velocity * (supplier_lead_time + coverage_period) * safety_buffer
    suggested_qty = max(0, round(raw_need - max(0, current_stock)))
    if suggested_qty == 0:
        suggested_qty = None
```

The rest of the function (lines 70-84) stays exactly the same — warning/critical thresholds use `supplier_lead_time` only.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_reorder.py -v`
Expected: All tests PASS (new tests + old tests still pass with default coverage_period=0)

- [ ] **Step 5: Commit**

```bash
git add src/engine/reorder.py src/tests/test_reorder.py
git commit -m "feat: add coverage_period to reorder formula (lead_time + coverage)"
```

---

### Task 3: Update pipeline.py to pass coverage_period

**Files:**
- Modify: `src/engine/pipeline.py:100-105, 165-175, 298-340, 421-440`

- [ ] **Step 1: Update fetch_all_supplier_mappings to include typical_order_months**

In `src/engine/pipeline.py`, update `fetch_all_supplier_mappings()` (line ~425):

```python
def fetch_all_supplier_mappings(db_conn) -> dict[str, dict]:
    """Pre-compute supplier info for all categories."""
    mapping = {}
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sc.tally_name AS category_name,
                   s.name, s.lead_time_default, s.lead_time_sea, s.lead_time_air,
                   s.buffer_override, s.typical_order_months
            FROM stock_categories sc
            JOIN suppliers s ON UPPER(s.name) = UPPER(sc.tally_name)
        """)
        for row in cur.fetchall():
            mapping[row[0]] = {
                "name": row[1],
                "lead_time_default": row[2],
                "lead_time_sea": row[3],
                "lead_time_air": row[4],
                "buffer_override": float(row[5]) if row[5] is not None else None,
                "typical_order_months": row[6],
            }
    return mapping
```

- [ ] **Step 2: Add import and compute coverage in Phase 1 (line ~166)**

Add to the imports at the top of pipeline.py:

```python
from engine.reorder import (
    calculate_days_to_stockout,
    detect_import_history,
    determine_reorder_status,
    get_supplier_for_category,
    must_stock_fallback_qty,
    DEFAULT_LEAD_TIME,
    compute_coverage_days,  # ADD THIS
)
```

Then in Phase 1 (around line 166-175), after `lead_time = ...`:

```python
        supplier = supplier_map.get(item["category_name"])
        lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
        coverage = compute_coverage_days(
            lead_time,
            supplier["typical_order_months"] if supplier else None,
        )
```

And pass coverage to `determine_reorder_status`:

```python
        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, velocity["total_velocity"],
            coverage_period=coverage,
        )
```

- [ ] **Step 3: Update Phase 4 recomputation (line ~318-322)**

Same pattern in Phase 4 where reorder status is recomputed with safety buffers:

```python
        supplier = supplier_map.get(m["category_name"])
        lead_time = supplier["lead_time_default"] if supplier else DEFAULT_LEAD_TIME
        coverage = compute_coverage_days(
            lead_time,
            supplier["typical_order_months"] if supplier else None,
        )

        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, total_vel,
            safety_buffer=buf, coverage_period=coverage,
        )
```

- [ ] **Step 4: Run existing pipeline tests**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/ -v --timeout=30`
Expected: All existing tests PASS (coverage_period defaults to 0 for backward compat)

- [ ] **Step 5: Commit**

```bash
git add src/engine/pipeline.py
git commit -m "feat: pipeline computes coverage_days from supplier typical_order_months"
```

---

### Task 4: Update PO Builder API to use coverage_period

**Files:**
- Modify: `src/api/routes/po.py:42-47, 86, 119-177`

- [ ] **Step 1: Update _compute_po_items to accept coverage_period**

In `src/api/routes/po.py`, update the function signature (line 42) and formula (line 86):

```python
def _compute_po_items(
    rows: list[dict],
    lead_time: int,
    coverage_period: int,
    buffer: float | None,
    vel_by_sku: dict,
) -> list[dict]:
```

Update line 86:

```python
        if vals["eff_total"] > 0:
            raw_need = vals["eff_total"] * (lead_time + coverage_period) * effective_buffer
```

Update line 91 (must_stock fallback):

```python
        elif d.get("reorder_intent") == "must_stock":
            suggested = must_stock_fallback_qty(lead_time + coverage_period)
```

Add coverage_period to the returned item dict (after line 103):

```python
            "coverage_period": coverage_period,
```

- [ ] **Step 2: Update po_data endpoint to accept and pass coverage_days**

In the `po_data` endpoint (line 119), add the query parameter:

```python
@router.get("/brands/{category_name}/po-data")
def po_data(
    category_name: str,
    lead_time: int = Query(None),
    coverage_days: int = Query(None, description="Coverage period in days beyond lead time. Defaults to supplier setting."),
    buffer: float = Query(None),
    include_warning: bool = Query(True),
    include_ok: bool = Query(False),
    from_date: str = Query(None, description="Analysis period start (YYYY-MM-DD)"),
    to_date: str = Query(None, description="Analysis period end (YYYY-MM-DD)"),
):
```

After the lead_time lookup (around line 141), add coverage lookup:

```python
            # Get coverage period
            if coverage_days is None:
                cur.execute("""
                    SELECT s.lead_time_default, s.typical_order_months
                    FROM suppliers s
                    WHERE UPPER(s.name) = UPPER(%s)
                """, (category_name,))
                srow = cur.fetchone()
                if srow:
                    from engine.reorder import compute_coverage_days
                    coverage_days = compute_coverage_days(
                        srow["lead_time_default"],
                        srow["typical_order_months"],
                    )
                else:
                    from engine.reorder import compute_coverage_days
                    coverage_days = compute_coverage_days(lead_time, None)
```

Update the _compute_po_items call (line 170):

```python
    result = _compute_po_items(rows, lead_time, coverage_days, buffer, vel_by_sku)
```

- [ ] **Step 3: Update match_and_build_po endpoint similarly**

In `match_and_build_po` (line 279), add coverage_days to SkuMatchRequest:

```python
class SkuMatchRequest(BaseModel):
    sku_names: list[str]
    lead_time: int | None = None
    coverage_days: int | None = None
    buffer: float | None = None
    from_date: str | None = None
    to_date: str | None = None
```

Add coverage lookup after lead_time lookup (line 314), then pass to _compute_po_items (line 332):

```python
    coverage_days = req.coverage_days
    if coverage_days is None:
        from engine.reorder import compute_coverage_days
        coverage_days = compute_coverage_days(lead_time, None)

    po_result = _compute_po_items(rows, lead_time, coverage_days, req.buffer, vel_by_sku)
```

- [ ] **Step 4: Update Excel export to show coverage period**

In `export_po` (line 387), update the info line:

```python
    ws["A5"] = f"Lead Time: {req.lead_time} days | Coverage: {getattr(req, 'coverage_days', 'N/A')} days | Buffer: {req.buffer}x"
```

Add `coverage_days` to `PoExportRequest`:

```python
class PoExportRequest(BaseModel):
    category_name: str
    supplier_name: str = ""
    lead_time: int = 180
    coverage_days: int = 180
    buffer: float = 1.3
    items: list[PoItem]
```

- [ ] **Step 5: Run API tests**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/po.py
git commit -m "feat: PO Builder API accepts coverage_days parameter"
```

---

### Task 5: Update SKU breakdown API formula string

**Files:**
- Modify: `src/api/routes/skus.py:648-653, 838-877`

- [ ] **Step 1: Update get_breakdown() supplier query to fetch typical_order_months**

In `src/api/routes/skus.py`, find the supplier lookup in `get_breakdown()` (~line 648). Update the SELECT to include `typical_order_months`:

```python
            cur.execute("""
                SELECT name, lead_time_default, lead_time_sea, lead_time_air,
                       buffer_override, typical_order_months
                FROM suppliers WHERE UPPER(name) = UPPER(%s) LIMIT 1
            """, (category_name,))
```

- [ ] **Step 2: Compute coverage_days and update formula string**

After extracting lead_time (~line 838), compute coverage:

```python
    from engine.reorder import compute_coverage_days
    typical_months = supplier_row["typical_order_months"] if supplier_row else None
    coverage_days = compute_coverage_days(lead_time, typical_months)
    total_coverage = lead_time + coverage_days
```

Update the formula string (line 845):

```python
    if eff_total_vel > 0:
        raw_val = round(eff_total_vel * total_coverage * buffer_multiplier, 1)
        reorder_formula = (
            f"{eff_total_vel} units/day x {total_coverage} days "
            f"({lead_time}d lead time + {coverage_days}d coverage) "
            f"x {buffer_multiplier} safety buffer = {raw_val} "
            f"-> {suggested_qty} units"
        )
```

Update status_thresholds (line 877) to add coverage info:

```python
        "status_thresholds": f"critical: <={lead_time}d | warning: <={threshold_warning}d | ok: >{threshold_warning}d | coverage: {coverage_days}d ({typical_months or 'auto'})",
```

Add coverage fields to the reorder response dict:

```python
        "coverage_days": coverage_days,
        "total_coverage": total_coverage,
        "coverage_source": f"{typical_months} months" if typical_months else f"auto ({365 // max(1, 365 // lead_time)} turns/year)",
```

- [ ] **Step 3: Update the status determination call to pass coverage_period**

The `determine_reorder_status` call in this endpoint also needs updating:

```python
    status, suggested_qty = determine_reorder_status(
        eff_stock, days_to_so, lead_time, eff_total_vel,
        safety_buffer=buffer_multiplier, coverage_period=coverage_days,
    )
```

- [ ] **Step 4: Run tests**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/skus.py
git commit -m "feat: SKU breakdown shows coverage period in formula and returns coverage fields"
```

---

## Chunk 2: Frontend Changes

### Task 6: Add coverage_days control to PO Builder

**Files:**
- Modify: `src/dashboard/src/pages/PoBuilder.tsx`

- [ ] **Step 1: Add coverage_days state**

Near the existing `leadTime` state, add:

```tsx
const [coverageDays, setCoverageDays] = useState<number | null>(null)
const [defaultCoverageDays, setDefaultCoverageDays] = useState<number>(180)
```

- [ ] **Step 2: Compute and display default coverage from supplier data**

When supplier data loads (after lead time is determined), compute the default:

```tsx
// After lead time is set from supplier data:
const autoComputeCoverage = (lt: number, typicalMonths: number | null): number => {
  if (typicalMonths) return typicalMonths * 30
  const fyDays = 365
  const turns = Math.min(Math.max(1, Math.floor(fyDays / lt)), 6)
  return Math.floor(fyDays / turns)
}
```

Call this when the brand loads to set `defaultCoverageDays`.

- [ ] **Step 3: Add coverage input to PO Builder toolbar**

After the Lead Time input in the PO Builder config section, add:

```tsx
<div className="space-y-1">
  <Label className="text-xs">
    Coverage Period (days)
    <HelpTip tip="How many days of stock this order should provide after the shipment arrives. Auto-calculated from supplier's typical ordering cycle. Adjust based on working capital." />
  </Label>
  <div className="flex items-center gap-2">
    <Input
      type="number"
      inputMode="numeric"
      className="w-24 h-8 text-sm"
      value={coverageDays ?? defaultCoverageDays}
      onChange={e => {
        const v = e.target.value ? Number(e.target.value) : null
        setCoverageDays(v)
      }}
    />
    <span className="text-xs text-muted-foreground">
      = {Math.round((coverageDays ?? defaultCoverageDays) / 30)} months
    </span>
    {coverageDays !== null && (
      <Button variant="ghost" size="sm" className="h-6 px-2 text-xs"
        onClick={() => setCoverageDays(null)}>
        Reset
      </Button>
    )}
  </div>
  <div className="text-xs text-muted-foreground">
    Total: {leadTime + (coverageDays ?? defaultCoverageDays)} days
    ({leadTime}d lead + {coverageDays ?? defaultCoverageDays}d coverage)
  </div>
</div>
```

- [ ] **Step 4: Pass coverage_days to API calls**

Update the `fetchPoData` API call to include `coverage_days`:

```tsx
const effectiveCoverage = coverageDays ?? defaultCoverageDays
// Add to query params: coverage_days={effectiveCoverage}
```

Update the export request to include `coverage_days`.

- [ ] **Step 5: Verify visually**

Run dev server: `cd src/dashboard && npm run dev`
Open PO Builder for any brand. Verify:
- Coverage input appears with auto-calculated default
- Changing coverage recalculates suggested quantities
- "Reset" button returns to default
- Export Excel shows coverage info

- [ ] **Step 6: Commit**

```bash
git add src/dashboard/src/pages/PoBuilder.tsx
git commit -m "feat: PO Builder coverage period input with auto-default and per-PO override"
```

---

### Task 7: Update SupplierManagement to make typical_order_months prominent

**Files:**
- Modify: `src/dashboard/src/pages/SupplierManagement.tsx`

- [ ] **Step 1: Improve the typical_order_months field label**

Find the form field for `typical_order_months` and update its label and help text:

```tsx
<div className="space-y-1">
  <Label>Order Coverage (months)</Label>
  <Input
    type="number"
    inputMode="numeric"
    value={form.typical_order_months ?? ''}
    onChange={e => updateField('typical_order_months', e.target.value ? Number(e.target.value) : null)}
    placeholder="Auto-calculated"
  />
  <p className="text-xs text-muted-foreground">
    How many months of stock each order should cover. Leave empty for auto-calculation from lead time.
  </p>
</div>
```

- [ ] **Step 2: Add coverage column to supplier table**

Add a table column that shows the effective coverage:

```tsx
<TableHead className="text-right">Coverage</TableHead>
```

And in the row:

```tsx
<TableCell className="text-right">
  {s.typical_order_months
    ? `${s.typical_order_months}mo (${s.typical_order_months * 30}d)`
    : <span className="text-muted-foreground">auto</span>}
</TableCell>
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/SupplierManagement.tsx
git commit -m "feat: supplier management shows coverage period prominently"
```

---

### Task 8: Update Help page formulas

**Files:**
- Modify: `src/dashboard/src/pages/Help.tsx:525-612`

- [ ] **Step 1: Update Lead Time & Buffer formula**

Replace the formula section (line ~531-536):

```tsx
<FormulaBox className="bg-blue-50 text-blue-700">Lead Time (days to arrive)</FormulaBox>
<FormulaOp>+</FormulaOp>
<FormulaBox className="bg-teal-50 text-teal-700">Coverage Period (days of stock after arrival)</FormulaBox>
<FormulaOp>=</FormulaOp>
<FormulaBox className="bg-purple-50 text-purple-700 font-semibold">Total Coverage Days</FormulaBox>
```

- [ ] **Step 2: Update Reorder Quantity formula**

Replace (line ~597-608):

```tsx
<FormulaOp>(</FormulaOp>
<FormulaBox className="bg-emerald-50 text-emerald-700">Velocity</FormulaBox>
<FormulaOp>x</FormulaOp>
<FormulaBox className="bg-purple-50 text-purple-700">Total Coverage Days</FormulaBox>
<FormulaOp>x</FormulaOp>
<FormulaBox className="bg-amber-50 text-amber-700">Safety Buffer</FormulaBox>
<FormulaOp>)</FormulaOp>
<FormulaOp>-</FormulaOp>
<FormulaBox className="bg-blue-50 text-blue-700">Current Stock</FormulaBox>
<FormulaOp>=</FormulaOp>
<FormulaBox className="bg-red-50 text-red-700 font-semibold">Order Qty</FormulaBox>
```

Update the description below:

```tsx
<p className="text-xs text-center text-muted-foreground pb-2">
  How much to order so stock lasts through lead time plus the coverage period. Adjustable per-PO in the PO Builder.
</p>
```

- [ ] **Step 3: Add Coverage Period to glossary**

```tsx
{ term: 'Coverage Period', definition: 'Days of stock an order should provide after arrival. Auto-calculated from lead time (turns per year) or set per supplier. Adjustable per-PO.', anchor: 'lead-time-buffer' },
```

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/pages/Help.tsx
git commit -m "feat: Help page formulas updated with coverage period concept"
```

---

### Task 9: Build frontend and verify end-to-end

- [ ] **Step 1: Build frontend**

Run: `cd src/dashboard && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 2: Start API and test full flow**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000`

Test:
1. Open `/brands/WINSOR%20%26%20NEWTON/po-data` — verify `coverage_period` field in response
2. Open SKU breakdown — verify formula string shows `(Xd lead + Yd coverage)`
3. Open PO Builder — verify coverage input and recalculation
4. Open Supplier Management — verify coverage column

- [ ] **Step 3: Run full test suite**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete coverage period implementation — formula, pipeline, PO Builder, UI"
```
