# 05 — Computation Engine

## Overview

23 formulae, all reviewed and corrected. Full specifications in `11-UNICOMMERCE-MIGRATION-PLAN.md` (section "Computation Engine Design"). This doc covers **implementation notes** — what to build, not what the formula is.

## Implementation Map

| Formula | File | Function | Status |
|---|---|---|---|
| F1. Available Stock | `inventory.py` | computed during snapshot pull | New |
| F2. Effective Stock | `reorder.py` | `compute_effective_stock()` | Rewrite |
| F3. Daily Stock Position | `stock_position.py` | `store_daily_snapshot()` | Rewrite |
| F4. Is In Stock | `stock_position.py` | part of position computation | Rewrite |
| F5. Gross Demand | `velocity.py` | input from transactions table | Rewrite |
| F6. Net Demand | `velocity.py` | `compute_net_demand()` | Rewrite |
| F7. Velocity (Flat) | `velocity.py` | `calculate_velocity()` | Rewrite |
| F8. Velocity Per Channel | `velocity.py` | part of `calculate_velocity()` | Rewrite |
| F9. Velocity (Recent) | `velocity.py` | `calculate_recent_velocity()` | Rewrite |
| F10. Velocity Trend | `velocity.py` | `detect_trend()` | Modify |
| F11. Days to Stockout | `reorder.py` | `calculate_days_to_stockout()` | Modify |
| F12. Lead Time | `reorder.py` + `inbound.py` | manual + computed reference | Modify |
| F13. Coverage Period | `reorder.py` | `compute_coverage_days()` | Keep |
| F14. Safety Buffer | `classification.py` | `compute_safety_buffer()` | Modify (multiplier) |
| F15. Reorder Quantity | `reorder.py` | `determine_reorder_status()` | Rewrite |
| F16. Reorder Status | `reorder.py` | `determine_reorder_status()` | Rewrite |
| F17. ABC Classification | `classification.py` | `compute_abc_classification()` | Minor modify |
| F18. XYZ Classification | `classification.py` | `compute_xyz_classification()` | Rewrite (calendar weeks) |
| F19. Dead Stock | `pipeline.py` | `compute_dead_stock()` | Modify |
| F20. Slow Mover | `pipeline.py` | `compute_slow_mover()` | Modify (ABC-aware) |
| F21. Last Dispatch Date | `pipeline.py` | `compute_last_dispatch_date()` | Rename + keep |
| F22. Zero Activity Ratio | `pipeline.py` | `compute_zero_activity_ratio()` | Rewrite (ratio) |
| F23. Brand Rollups | `aggregation.py` | `compute_brand_metrics()` | Modify (+min_dts) |

## Key Implementation Notes

### stock_position.py — Complete Rewrite

**Old:** Forward-walk from Tally opening balance with Physical Stock SET-TO logic.
**New:** Store daily inventory snapshot directly from UC API pull.

```python
def store_daily_snapshot(db_conn, snapshot_date, inventory_data):
    """Store today's inventory snapshot from UC.
    inventory_data = {sku: {inventory, blocked, putaway, openSale, openPurchase, bad}}
    """
    # Bulk upsert into daily_inventory_snapshots
    # Compute available_stock = inventory - blocked + putaway (or use generated column)
    pass

def compute_is_in_stock(db_conn, sku, date):
    """F4: is_in_stock = available_stock > 0 OR had_demand_that_day"""
    pass
```

No reconstruction needed. The snapshot IS the position.

### velocity.py — Rewrite

**Old:** Reads from `daily_stock_positions` table (Tally-reconstructed).
**New:** Reads from `daily_inventory_snapshots` + `transactions`.

```python
def calculate_velocity(db_conn, sku, start_date, end_date):
    """F7: velocity = net_demand / in_stock_days
    Min 14 in-stock days required. Below → insufficient data.
    Per-channel velocities clamped at 0."""
    pass
```

Key changes:
- Min 14 in-stock-day guard
- Per-channel velocity clamped at `max(0, ...)`
- `net_demand = dispatched - CIR - RTO` (from transactions table)
- `in_stock_days` from `daily_inventory_snapshots.available_stock > 0` OR had demand

### reorder.py — Rewrite

**Old:** Double-applies buffer, includes openPurchase in effective stock.
**New:** Buffer on coverage only, effective_stock = available_stock only.

```python
def determine_reorder_status(velocity, effective_stock, lead_time, coverage_period,
                              safety_buffer, reorder_intent, open_purchase=0):
    """F15+F16: Compute reorder qty and status.
    Buffer applies to coverage demand only.
    open_purchase is stored for display but NOT used in formula."""

    demand_during_lead = velocity * lead_time  # NO buffer
    order_for_coverage = velocity * coverage_period * safety_buffer  # buffer HERE only
    # Include lead-time deficits (if already short, suggested qty must cover that gap too).
    suggested_qty = max(0, (demand_during_lead + order_for_coverage) - effective_stock)
    ...
```

Status mapping:
```python
STOCKED_OUT  = velocity > 0 and stock <= 0
OUT_OF_STOCK = velocity == 0 and stock <= 0
NO_DEMAND    = velocity == 0 and stock > 0
CRITICAL     = dts <= lead_time
WARNING      = dts <= lead_time + warning_buffer
OK           = otherwise
```

Override logic:
- `must_stock` → minimum WARNING (CRITICAL only if formula agrees)
- `do_not_reorder` → show calculated status + "suppressed" flag

### classification.py — Partial Rewrite

**ABC:** Minor change — verify `sellingPrice` is net-of-discount (confirmed yes).

**XYZ:** Rewrite to use **calendar weeks**:
```python
def compute_xyz_classification(positions, net_demand_by_date):
    """F18: Group into calendar weeks (Mon-Sun).
    Only include weeks where in-stock >= 4 days.
    Require minimum 4 qualifying weeks."""
    # Build weekly demand dict keyed by ISO week number
    # Filter to weeks with >= 4 in-stock days
    # Compute CV = population_stddev / mean
    pass
```

**Safety buffer:** Supplier override is now a **multiplier** on the matrix:
```python
def compute_safety_buffer(abc, xyz, supplier_override=None):
    base = BUFFER_MATRIX[abc][xyz]
    if supplier_override:
        return base * supplier_override
    return base
```

### pipeline.py — Modify

Remove:
- `backdate_physical_stock` import and calls (~40 lines)
- `tally_name` references → `name`
- Double reorder computation (Phase 1 + Phase 4 → single Phase 4)

Keep:
- 6-phase structure
- Bulk pre-fetch pattern
- Incremental identification
- Brand rollup phase

Add to brand rollups:
- `min_days_to_stockout` (catches critical slow movers)

### aggregation.py — Minor Modify

Add `min_days_to_stockout`:
```python
min_dts = min((dts for dts in all_dts if dts is not None and dts >= 0), default=None)
```

This must include `0` so actively stocked-out SKUs are visible in brand-level rollups.

Update status names: `NO_DATA` → `NO_DEMAND`, add `STOCKED_OUT`.

## Pipeline Execution Order

Same 6-phase structure:

1. **Snapshot storage** — store today's inventory snapshot from UC
2. **Transaction loading** — load new dispatches, returns, GRNs into transactions table
3. **Position computation** — compute `is_in_stock` per day from snapshots + demand
4. **Velocity + Classification** — flat velocity, ABC, XYZ, WMA, trend, safety buffers
5. **Reorder computation** — effective stock, reorder qty, status
6. **Rollups** — SKU metrics upsert, brand metrics aggregation
