# 07 — Historical Backfill (One-Time)

## Overview

The incremental sync builds data going forward from the first run. Backfill fills the gap: historical data from FY start (April 1, 2025) to the first sync date.

**Status:** Blocked on Unicommerce providing the Transaction Ledger report.

## What We Need to Backfill

| Data | Source | Purpose |
|---|---|---|
| Historical dispatches | Shipping Package search (paginated by date) | Velocity computation for full FY |
| Historical returns | Return search (30-day windows looped) | Net demand adjustment |
| Historical GRNs | GRN list + detail (bounded windows + pagination) | Lead time computation |
| Historical daily stock positions | Transaction Ledger export (from UC) | Accurate daily stock levels |

## Backfill Strategy

### Phase 1: Transactions (can do NOW with existing API)

Pull all historical dispatches, returns, and GRNs from FY start to first sync date.

```python
def backfill_transactions(client, db_conn, fy_start, first_sync_date):
    """One-time pull of all historical transactions."""

    # 1. Dispatches — paginate by month
    for month_start, month_end in monthly_windows(fy_start, first_sync_date):
        for facility in client.facilities:
            packages = pull_dispatched_in_range(client, facility, month_start, month_end)
            txns = transform_packages_to_transactions(packages)
            load_transactions(db_conn, txns)

    # 2. Returns — 30-day windows
    for window_start, window_end in date_windows(fy_start, first_sync_date, max_days=30):
        for return_type in ["CIR", "RTO"]:
            for facility in client.facilities:
                returns = pull_returns_in_window(client, facility, return_type,
                                                 window_start, window_end)
                txns = transform_returns_to_transactions(returns)
                load_transactions(db_conn, txns)

    # 3. GRNs — bounded windows (never unbounded empty-body pull)
    for window_start, window_end in date_windows(fy_start, first_sync_date, max_days=30):
        for facility in client.facilities:
            grn_codes = iter_grn_codes_in_window(client, facility, window_start, window_end)
            grns = fetch_grn_details(client, facility, grn_codes)
            txns = transform_grns_to_transactions(grns)
            load_transactions(db_conn, txns)
```

**Timing estimate:** ~10-20 minutes for full FY (~1,158 orders/month × 12 months = ~14,000 orders, each with item details).

### Phase 2: Daily Stock Positions (NEEDS Transaction Ledger)

Without the Transaction Ledger, we can't know what stock levels were on historical dates. Options:

**Option A (when Transaction Ledger arrives):**
1. Export Transaction Ledger from UC (covers full FY movements)
2. Take today's inventory snapshot as anchor
3. Walk backwards: for each day from today to FY start, subtract that day's inward and add that day's outward
4. Store reconstructed daily snapshots

```python
def backfill_stock_positions(db_conn, anchor_snapshot, transaction_ledger):
    """Reconstruct historical stock positions from Transaction Ledger."""
    # anchor_snapshot = today's known inventory
    # Walk backwards day by day
    current = dict(anchor_snapshot)  # {sku: available_stock}
    for date in reverse_date_range(today, fy_start):
        day_txns = transaction_ledger.get(date, [])
        for txn in day_txns:
            if txn.is_inward:
                current[txn.sku] -= txn.quantity  # undo the inward
            else:
                current[txn.sku] += txn.quantity  # undo the outward
        store_daily_snapshot(db_conn, date, current)
```

**Option B (without Transaction Ledger):**
1. Use the dispatches + returns + GRNs we already pulled (Phase 1)
2. Anchor on today's snapshot
3. Walk backwards using those transactions
4. Less accurate (misses inventory adjustments, inter-facility transfers) but good enough for velocity computation

**Recommendation:** Start with Option B immediately. Upgrade to Option A when Transaction Ledger arrives. The velocity computation only needs `is_in_stock` per day, which Option B can approximate well enough.

### Phase 3: Recompute Everything

After backfill, run the full computation pipeline:
```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.sync --full
```

This recomputes all velocities, classifications, and reorder metrics using the full historical data.

## Backfill CLI

```bash
# Backfill transactions (dispatches, returns, GRNs) from FY start
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.backfill --transactions

# Backfill stock positions (Option B — from transactions + today's snapshot)
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.backfill --positions

# Backfill stock positions from Transaction Ledger (Option A — when available)
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.backfill --positions --ledger-file=path/to/ledger.csv

# Full backfill (transactions + positions + recompute)
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.backfill --full
```

## Idempotency

All backfill operations use `ON CONFLICT DO NOTHING` / `ON CONFLICT DO UPDATE`. Running backfill twice produces the same result. Safe to re-run after errors.

## When to Run

1. **After first incremental sync is working** — backfill adds historical depth
2. **Before going live** — ensures velocity has full FY data, not just last few days
3. **After Transaction Ledger arrives** — re-run position backfill for maximum accuracy
