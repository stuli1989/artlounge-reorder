# 06 — Incremental Sync Design

## Overview

The nightly sync pulls only data changed since the last successful sync. No full re-pulls after the initial setup. Designed to run on Railway as a cron job (once per day, ~2-5 minutes).

## Sync Orchestrator (`unicommerce/sync.py`)

```python
def run_nightly_sync(db_conn, full=False):
    """
    Main entry point. Called by Railway cron or manually.
    full=True forces a complete re-pull (first run or recovery).
    """
    sync_id = create_sync_log(db_conn, source="unicommerce")
    try:
        client = UnicommerceClient(UC_TENANT, UC_USERNAME, UC_PASSWORD)
        client.authenticate()
        client.discover_facilities()

        last_sync = get_last_successful_sync(db_conn)
        since_date = last_sync.completed_at if last_sync and not full else FY_START_DATE
        since_minutes = minutes_since(since_date) + 60  # 1hr buffer

        # Step 1: Update catalog (new/changed SKUs)
        updated_skus = pull_updated_skus(client, hours_since_last_sync=hours_since(since_date) + 1)
        load_catalog(db_conn, updated_skus)

        # Step 2: Pull inventory snapshot (always full — it's a point-in-time snapshot)
        inventory = pull_inventory_snapshot(client)
        store_daily_snapshot(db_conn, today(), inventory)

        # Step 3: Pull dispatched shipments (incremental)
        packages = pull_dispatched_since(client, since_minutes)
        dispatch_txns = transform_packages_to_transactions(packages)
        load_transactions(db_conn, dispatch_txns)

        # Step 4: Pull returns (incremental by updated timestamp, 30-day windows)
        returns = pull_returns_since(client, since_date)
        return_txns = transform_returns_to_transactions(returns)
        load_transactions(db_conn, return_txns)

        # Step 5: Pull GRNs (incremental)
        grns = pull_grns_since(client, since_date)
        grn_txns = transform_grns_to_transactions(grns)
        load_transactions(db_conn, grn_txns)
        store_grn_details(db_conn, grns)  # for lead time computation

        # Step 6: Run computation pipeline
        run_computation_pipeline(db_conn, incremental=not full)

        # Step 7: Update sync log
        update_sync_log(db_conn, sync_id, status="success",
            stats={"skus_updated": len(updated_skus),
                   "dispatches": len(packages),
                   "returns": len(returns),
                   "grns": len(grns)})

        # Step 8: Send notification
        send_sync_notification(success=True, stats=...)

    except Exception as e:
        update_sync_log(db_conn, sync_id, status="failed", error=str(e))
        send_sync_notification(success=False, error=str(e))
        raise
```

## Transaction Normalization

All UC data (dispatches, returns, GRNs) is normalized into the same `transactions` table format:

```python
def transform_packages_to_transactions(packages):
    """Convert shipping packages to transaction rows."""
    txns = []
    for pkg in packages:
        dispatch_date = epoch_to_date(pkg["dispatched"])
        channel = CHANNEL_MAP.get(pkg["channel"], "unclassified")
        for sku_key, item in pkg["items"].items():
            txns.append({
                "txn_date": dispatch_date,
                "stock_item_name": item["itemSku"],
                "quantity": item["quantity"],
                "is_inward": False,  # dispatch = outward
                "channel": channel,
                "uc_channel": pkg["channel"],
                "party_name": pkg.get("customer", ""),
                "voucher_type": "Dispatch",
                "voucher_number": pkg["code"],
                "rate": None,  # from sale order if needed
                "amount": None,
                "return_type": None,
                "facility": pkg.get("_facility"),
                "shipping_package_code": pkg["code"],
            })
    return txns

def transform_returns_to_transactions(returns):
    """Convert returns to inward rows that offset the original sale channel."""
    txns = []
    for ret in returns:
        ret_date = parse_date(ret["returnSaleOrderValue"]["returnCreatedDate"])
        sale_order_channel = ret.get("_sale_order_channel")  # hydrated from original sale order
        channel = CHANNEL_MAP.get(sale_order_channel, "unclassified")
        reverse_pickup_code = ret.get("reversePickupCode") or ret["returnSaleOrderValue"].get("reversePickupCode")
        voucher_number = f"{ret['_return_type']}-{reverse_pickup_code}"

        qty_by_sku = {}
        for item in ret.get("returnSaleOrderItems", []):
            sku = item["skuCode"]
            qty_by_sku[sku] = qty_by_sku.get(sku, 0) + int(item.get("quantity") or 1)

        for sku, qty in qty_by_sku.items():
            txns.append({
                "txn_date": ret_date,
                "stock_item_name": sku,
                "quantity": qty,
                "is_inward": True,  # return = inward
                "channel": channel,
                "uc_channel": sale_order_channel,
                "party_name": "",
                "voucher_type": "Return",
                "voucher_number": voucher_number,
                "return_type": ret["_return_type"],  # CIR or RTO
                "facility": ret.get("_facility"),
                "shipping_package_code": ret.get("shipmentCode"),
            })
    return txns
```

## Deduplication

Emit one normalized row per `(voucher_number, stock_item_name, is_inward)` (aggregate duplicate SKU lines per voucher before writing).

Transactions should use `ON CONFLICT ... DO UPDATE` with a **stable idempotency key**:
```sql
UNIQUE(voucher_number, stock_item_name, is_inward)
```

Recommended upsert behavior:
```sql
ON CONFLICT (voucher_number, stock_item_name, is_inward) DO UPDATE
SET txn_date = EXCLUDED.txn_date,
    quantity = EXCLUDED.quantity,
    channel = EXCLUDED.channel,
    uc_channel = EXCLUDED.uc_channel,
    return_type = EXCLUDED.return_type,
    facility = EXCLUDED.facility
```

If a shipping package is pulled twice (overlap between syncs), the second write is idempotent. If UC corrects a quantity/status later, the row is updated instead of duplicated.

## Sync State Tracking

The `sync_log` table tracks:
- `started_at`, `completed_at` — timing
- `status` — success/failed
- `source` — "unicommerce"
- `stats` — JSON with counts (skus_updated, dispatches, returns, grns)
- `error` — error message if failed

The incremental window is computed from `last successful sync completed_at`. On failure, next sync will re-pull the failed window (idempotent due to dedup).

## CLI Interface

```bash
# Normal nightly sync (incremental)
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.sync

# Full re-sync (first run or recovery)
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.sync --full

# Dry run (pull data, don't write to DB)
cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.sync --dry-run
```

## Timing Estimates

| Step | API Calls | Estimated Time |
|---|---|---|
| Auth + facility discovery | 2 | <1s |
| Catalog (incremental) | 1 | ~2s |
| Inventory snapshot (3 facilities × ~24 chunks) | ~72 | ~60-120s |
| Dispatched packages (incremental) | ~3-6 | ~5s |
| Returns (incremental) | ~6-12 | ~10s |
| GRNs (incremental) | ~3-6 | ~5s |
| Computation pipeline | 0 (DB only) | ~30-60s |
| **Total** | **~90-110** | **~2-5 min** |

For full sync (first run): ~5-10 minutes depending on historical volume.

## Error Recovery

- **Auth failure:** Retry once, then fail with clear message.
- **Single endpoint failure:** Log error, continue with other endpoints. Pipeline runs with whatever data was pulled.
- **Pipeline failure:** Sync log marked failed. Raw data already in DB. Next sync will re-run pipeline.
- **Partial data:** Dedup ensures no double-counting. Missing data will be caught in next sync window.
