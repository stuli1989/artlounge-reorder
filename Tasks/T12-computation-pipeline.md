# T12: Full Computation Pipeline + Brand Rollup

## Prerequisites
- T09 (stock position reconstruction)
- T10 (velocity calculation)
- T11 (stockout + reorder status)

## Objective
Build the orchestrator that runs all computations for every SKU and rolls up results to brand level. This runs after each nightly sync.

## Files to Create

### 1. `engine/aggregation.py`

#### `compute_brand_metrics(category_name: str, sku_metrics_list: list[dict], supplier: dict | None) -> dict`

Aggregate SKU metrics to brand level:
```python
def compute_brand_metrics(category_name, sku_metrics_list, supplier):
    total = len(sku_metrics_list)
    in_stock = sum(1 for s in sku_metrics_list if s['current_stock'] > 0)
    out_of_stock = sum(1 for s in sku_metrics_list if s['current_stock'] <= 0)
    critical = sum(1 for s in sku_metrics_list if s['reorder_status'] == 'critical')
    warning = sum(1 for s in sku_metrics_list if s['reorder_status'] == 'warning')
    ok = sum(1 for s in sku_metrics_list if s['reorder_status'] == 'ok')
    no_data = sum(1 for s in sku_metrics_list if s['reorder_status'] == 'no_data')

    # Weighted average days to stockout (weight by velocity — fast movers matter more)
    weighted_sum = 0
    weight_total = 0
    for s in sku_metrics_list:
        if s.get('days_to_stockout') is not None and s.get('total_velocity', 0) > 0:
            weighted_sum += s['days_to_stockout'] * s['total_velocity']
            weight_total += s['total_velocity']

    avg_days = round(weighted_sum / weight_total, 1) if weight_total > 0 else None

    return {
        'category_name': category_name,
        'total_skus': total,
        'in_stock_skus': in_stock,
        'out_of_stock_skus': out_of_stock,
        'critical_skus': critical,
        'warning_skus': warning,
        'ok_skus': ok,
        'no_data_skus': no_data,
        'avg_days_to_stockout': avg_days,
        'primary_supplier': supplier.get('name') if supplier else None,
        'supplier_lead_time': supplier.get('lead_time_default') if supplier else None,
    }
```

### 2. `engine/pipeline.py`

#### `run_computation_pipeline(db_conn)`

Main orchestrator — called after nightly sync:

```python
def run_computation_pipeline(db_conn):
    """Recompute all derived metrics from raw transaction data."""
    from datetime import date, timedelta

    FY_START = date(2025, 4, 1)
    today = date.today()

    # 1. Get all stock items
    stock_items = fetch_all_stock_items(db_conn)
    print(f"  Computing metrics for {len(stock_items)} stock items...")

    # 2. For each item: reconstruct positions, calculate velocity, determine status
    for i, item in enumerate(stock_items):
        transactions = fetch_transactions_for_item(db_conn, item['tally_name'])

        if not transactions:
            upsert_sku_metrics(db_conn, {
                'stock_item_name': item['tally_name'],
                'category_name': item['category_name'],
                'current_stock': item['closing_balance'],
                'reorder_status': 'out_of_stock' if item['closing_balance'] <= 0 else 'no_data',
            })
            continue

        # Get opening balance
        opening_balance = item.get('opening_balance', 0) or 0

        # Reconstruct daily positions
        positions = reconstruct_daily_positions(
            stock_item_name=item['tally_name'],
            opening_balance=opening_balance,
            opening_date=FY_START,
            transactions=transactions,
            end_date=today,
        )

        # Save positions
        upsert_daily_positions(db_conn, positions)

        # Calculate velocity
        velocity = calculate_velocity(item['tally_name'], positions)

        # Import history
        import_history = detect_import_history(item['tally_name'], transactions)

        # Supplier lead time
        supplier = get_supplier_for_category(db_conn, item['category_name'])
        lead_time = supplier['lead_time_default'] if supplier else 180

        # Days to stockout
        current_stock = item['closing_balance']
        days_to_stockout = calculate_days_to_stockout(current_stock, velocity['total_velocity'])

        # Reorder status
        status, suggested_qty = determine_reorder_status(
            current_stock, days_to_stockout, lead_time, velocity['total_velocity']
        )

        # Save SKU metrics
        upsert_sku_metrics(db_conn, {
            'stock_item_name': item['tally_name'],
            'category_name': item['category_name'],
            'current_stock': current_stock,
            **velocity,
            'days_to_stockout': days_to_stockout,
            'estimated_stockout_date': (today + timedelta(days=int(days_to_stockout))) if days_to_stockout else None,
            **{k: v for k, v in import_history.items() if k in [
                'last_import_date', 'last_import_qty', 'last_import_supplier'
            ]},
            'reorder_status': status,
            'reorder_qty_suggested': suggested_qty,
        })

        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(stock_items)} items...")

    # 3. Brand rollups
    print("  Computing brand rollups...")
    categories = fetch_all_categories(db_conn)
    for cat in categories:
        sku_metrics = fetch_sku_metrics_for_category(db_conn, cat['tally_name'])
        supplier = get_supplier_for_category(db_conn, cat['tally_name'])
        brand_data = compute_brand_metrics(cat['tally_name'], sku_metrics, supplier or {})
        upsert_brand_metrics(db_conn, brand_data)

    print("  Computation pipeline complete.")
```

#### Helper functions needed in pipeline.py:
- `fetch_all_stock_items(db_conn)` — SELECT from stock_items
- `fetch_all_categories(db_conn)` — SELECT from stock_categories
- `fetch_sku_metrics_for_category(db_conn, category_name)` — SELECT from sku_metrics
- `upsert_sku_metrics(db_conn, metrics_dict)` — UPSERT into sku_metrics
- `upsert_brand_metrics(db_conn, metrics_dict)` — UPSERT into brand_metrics

## Performance Notes
- For 10,000 SKUs × 365 days → ~3.6M daily position rows
- The pipeline should complete in minutes, not hours
- Progress logged every 500 items
- Commit after each item or in batches of 100

## Acceptance Criteria
- [ ] Pipeline processes all stock items and produces sku_metrics
- [ ] Brand rollup aggregates SKU metrics correctly
- [ ] Weighted average days-to-stockout weights by velocity (fast movers matter more)
- [ ] Items with no transactions get 'no_data' or 'out_of_stock' status
- [ ] Progress logging every 500 items
- [ ] All database operations use upsert (safe to re-run)
