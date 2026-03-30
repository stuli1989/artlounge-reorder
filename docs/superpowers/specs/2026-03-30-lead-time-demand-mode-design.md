# Lead Time Demand Mode — Design Spec

## Problem

The reorder formula always includes `demand_during_lead` in the suggested quantity: `suggested = demand_lead + order_coverage - stock`. When stock is 0, this means ordering for a period where you can't sell anything (no stock during the wait). For suppliers with short lead times or when capital is tight, users want the option to order only for the coverage period: `suggested = order_coverage - max(0, stock)`.

## Design

### New Per-Supplier Setting

Column: `lead_time_demand_mode TEXT NOT NULL DEFAULT 'full'` on the `suppliers` table.

Two modes:
- `"full"` (default) — `suggested = demand_lead + order_coverage - stock`
- `"coverage_only"` — `suggested = max(0, order_coverage - stock)`

### What Changes / What Doesn't

**Changes:** Suggested reorder quantity only.

**Does NOT change:** Status thresholds. Urgent/Reorder/Healthy are based on `days_to_stockout` vs `lead_time` — time-based urgency, independent of order size.

### Formula

```
Full mode:
  demand_during_lead = velocity × lead_time
  order_for_coverage = velocity × coverage × buffer
  suggested_qty = max(0, demand_lead + order_coverage - stock)

Coverage-only mode:
  order_for_coverage = velocity × coverage × buffer
  suggested_qty = max(0, order_coverage - stock)
```

### Touchpoints

#### Database
- Add column `lead_time_demand_mode` to `suppliers` table (migration)

#### Backend Engine
- `src/engine/reorder.py` — `determine_reorder_status()` gets `include_lead_demand: bool = True`. When False, omits `demand_during_lead` from suggested_qty calc. Status logic unchanged.
- `src/engine/effective_values.py` — `compute_effective_status()` passes through the param.
- `src/engine/pipeline.py` — looks up supplier mode per brand, passes to reorder calculation.
- `src/engine/targeted_recompute.py` — same lookup.

#### Backend API
- `src/api/routes/suppliers.py` — accept `lead_time_demand_mode` in create/update, validate values, include in response. Changing this field triggers recalculation.
- `src/api/routes/po.py` — look up supplier mode, apply to PO qty calculation. Allow per-order override via query param.
- `src/api/routes/skus.py` — look up supplier mode for effective status recalc.

#### Frontend
- `src/dashboard/src/pages/SupplierManagement.tsx` — add dropdown: "Full (lead + coverage)" / "Coverage only".
- `src/dashboard/src/pages/PoBuilder.tsx` — show current mode, allow per-order override toggle.
- `src/dashboard/src/components/CalculationBreakdown.tsx` — display correct formula based on mode.

#### Docs
- `src/dashboard/src/pages/docs/Calculations.tsx` — add note about the two modes.

#### Tests
- New test cases for coverage_only mode in `test_reorder.py`.
- Verify switching a supplier's mode triggers recalculation and changes suggested_qty.

### Pipeline Re-run

After deployment:
1. Run pipeline locally to update all metrics
2. On Railway, trigger a pipeline rebuild via start.sh (positions check) or manual API call

### Default Behavior

All 172 existing suppliers default to `"full"` — no change in behavior until explicitly switched. This makes the migration safe and backward-compatible.
