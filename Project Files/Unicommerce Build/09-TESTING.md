# 09 — Testing Strategy

## Overview

Test at three levels: UC API integration tests (live), computation engine unit tests (pure logic), and end-to-end sync tests.

## 1. UC API Integration Tests

Test against the **sandbox** environment first, then verify against production.

```
tests/
├── test_uc_client.py        # OAuth, token refresh, request helpers
├── test_uc_catalog.py       # SKU pull, incremental update
├── test_uc_inventory.py     # Snapshot pull, multi-facility aggregation
├── test_uc_orders.py        # Shipping package search, channel mapping
├── test_uc_returns.py       # CIR/RTO search, 30-day window looping, detail
├── test_uc_inbound.py       # GRN list + detail, lead time computation
```

**Key test cases:**
- Auth succeeds with valid credentials
- Auth fails gracefully with invalid credentials
- Token auto-refreshes when expired
- Inventory snapshot aggregates correctly across 3 facilities
- inventoryBlocked is subtracted from inventory (F1 validation)
- Shipping packages return items with correct SKU + quantity
- Channel mapping: CUSTOM→wholesale, CUSTOM_SHOP→store, MAGENTO2→online
- Returns: 30-day window loop covers full date range using updated timestamps
- Returns: reversePickupCode field name works for detail fetch
- Returns: same-SKU multi-quantity returns are aggregated (no silent unit loss)
- Returns: channel is mapped to original sale channel (not a synthetic "return" channel)
- GRN detail includes PO linkage for lead time calc
- Dedup: same package pulled twice → single transaction row

**Reference SKU:** SpeedBall #22B Pen Nib (SP009405)
- Known inventory: 20 total, 1 blocked, 10 putaway pending at ppetpl
- Expected available_stock = 20 - 1 + 10 = 29 (at ppetpl)
- Appeared in order MA-000054351 (MAGENTO2 channel, 3 units)

## 2. Computation Engine Unit Tests

Pure logic tests with synthetic data. No API calls, no database.

```
tests/
├── test_velocity.py         # All velocity formula variants
├── test_reorder.py          # Reorder quantity, status, effective stock
├── test_classification.py   # ABC, XYZ (calendar weeks), safety buffer
├── test_stock_position.py   # Snapshot storage, is_in_stock logic
├── test_aggregation.py      # Brand rollups, min_days_to_stockout
```

**Key test cases for velocity (F7):**
- Normal case: 100 net demand / 50 in-stock days = 2.0/day
- Zero demand: 0 / 50 = 0.0
- Zero in-stock days: → velocity 0 (not div-by-zero)
- Below min sample (13 days): → marked unreliable
- At min sample (14 days): → valid
- Negative net demand (more returns than dispatches): → clamped to 0
- Per-channel clamping: negative wholesale velocity clamped to 0

**Key test cases for reorder (F15):**
- Buffer on coverage only (NOT on lead time demand)
  - velocity=1, lead=90, coverage=91, buffer=1.3, stock=200
  - demand_during_lead = 1 × 90 = 90 (no buffer!)
  - order_for_coverage = 1 × 91 × 1.3 = 118.3
  - suggested_qty = max(0, (90 + 118.3) - 200) = 8.3
- Lead-time deficit must be included in reorder qty
  - velocity=1, lead=90, coverage=91, buffer=1.3, stock=20
  - suggested_qty = max(0, (90 + 118.3) - 20) = 188.3
- openPurchase NOT in effective_stock
- must_stock with zero velocity: min WARNING, not forced CRITICAL
- do_not_reorder: shows calculated status, qty = 0, suppressed flag

**Key test cases for XYZ (F18):**
- Calendar weeks (not stitched sequential days)
- Partial week < 4 days excluded
- Minimum 4 qualifying weeks required
- Item with stockout gap: weeks from different months don't merge

**Key test cases for status (F16):**
- STOCKED_OUT: velocity > 0, stock = 0
- NO_DEMAND: velocity = 0, stock > 0
- must_stock with plenty of stock → WARNING not CRITICAL

**Key test cases for aggregation (F23):**
- `min_days_to_stockout` includes `0` (active stockouts must appear in brand rollups)

## 3. End-to-End Sync Tests

Test the full sync pipeline against the UC sandbox or production.

```
tests/
├── test_sync_full.py        # Full sync from scratch
├── test_sync_incremental.py # Incremental sync (simulate second run)
├── test_backfill.py         # Historical backfill pipeline
```

**Key test cases:**
- Full sync: catalog + snapshot + dispatches + returns + GRNs → pipeline → metrics
- Incremental sync: only new data pulled, existing data preserved
- Dedup: overlapping sync windows don't create duplicate transactions
- Pipeline produces valid sku_metrics for all SKUs
- Brand rollups aggregate correctly
- Sync log updated with correct stats

## 4. Comparison Tests (Tally vs UC)

Once both systems have data, compare results for known SKUs:

```
tests/
├── test_comparison.py       # Compare Tally vs UC metrics for same SKUs
```

Pick 10-20 SKUs across different profiles:
- High velocity (A-class)
- Low velocity (C-class)
- Currently out of stock
- Recently restocked
- Has returns

Compare: velocity, stock level, reorder status, ABC class. Document discrepancies and reasons (expected: UC should be more accurate).

## Test Data

**Do NOT mock the UC API** for integration tests. Use real sandbox/production data.

For unit tests, use synthetic data fixtures:
```python
SAMPLE_SNAPSHOT = {
    "SP009405": {"inventory": 20, "inventoryBlocked": 1, "putawayPending": 10,
                 "openSale": 0, "openPurchase": 0, "badInventory": 0},
    ...
}
```
