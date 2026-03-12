# 05 — Computation Engine

## Overview

This is the core intelligence. After each nightly sync, the computation engine:
1. Reconstructs daily stock positions for every SKU
2. Identifies "in-stock" vs "out-of-stock" days
3. Calculates wholesale and online velocity separately
4. Computes days-to-stockout
5. Flags reorder alerts
6. Rolls up to brand level

## Step 1: Reconstruct Daily Stock Positions

### The Problem

Tally gives us transaction-level data (vouchers) and a current closing balance. But we need to know the stock level on EVERY day historically. This is necessary because:
- We need to know which days had stock (for velocity calculation)
- We need to identify the exact date stock hit zero (for stockout tracking)
- We need to exclude "out of stock" days from velocity averages

### The Algorithm

For each stock item:

```python
def reconstruct_daily_positions(stock_item_name: str, 
                                 opening_balance: float,
                                 opening_date: date,
                                 transactions: list,
                                 end_date: date) -> list:
    """
    Reconstruct day-by-day stock position from opening balance and transactions.
    
    Args:
        stock_item_name: The SKU
        opening_balance: Stock quantity at opening_date (from Tally)
        opening_date: Start of financial year (e.g., 2025-04-01)
        transactions: List of {date, qty_in, qty_out, channel} sorted by date
        end_date: Today's date
    
    Returns:
        List of daily position records
    """
    positions = []
    running_balance = opening_balance
    current_date = opening_date
    txn_index = 0
    
    while current_date <= end_date:
        day_inward = 0
        day_outward = 0
        day_wholesale_out = 0
        day_online_out = 0
        day_store_out = 0
        
        # Sum all transactions for this date
        while txn_index < len(transactions) and transactions[txn_index]['date'] == current_date:
            txn = transactions[txn_index]
            
            if txn['is_inward']:
                # Only count supplier inwards (not internal returns)
                if txn['channel'] == 'supplier':
                    day_inward += txn['quantity']
                # Internal returns (Art Lounge India - Purchase) are EXCLUDED
                # They're accounting entries, not real supply
            else:
                day_outward += txn['quantity']
                
                # Channel breakdown
                if txn['channel'] == 'wholesale':
                    day_wholesale_out += txn['quantity']
                elif txn['channel'] == 'online':
                    day_online_out += txn['quantity']
                elif txn['channel'] == 'store':
                    day_store_out += txn['quantity']
                # 'ignore' and 'internal' channels are excluded from outward
            
            txn_index += 1
        
        opening_qty = running_balance
        closing_qty = running_balance + day_inward - day_outward
        
        positions.append({
            'stock_item_name': stock_item_name,
            'position_date': current_date,
            'opening_qty': opening_qty,
            'inward_qty': day_inward,
            'outward_qty': day_outward,
            'closing_qty': closing_qty,
            'wholesale_out': day_wholesale_out,
            'online_out': day_online_out,
            'store_out': day_store_out,
            'is_in_stock': closing_qty > 0,
        })
        
        running_balance = closing_qty
        current_date += timedelta(days=1)
    
    return positions
```

### Handling the "Art Lounge India - Purchase" paired transactions

These internal entries create a +1 inward that doesn't represent real supply. The rule:

- **Transactions with channel = 'internal' are EXCLUDED from both inward and outward calculations.**
- **Transactions with channel = 'ignore' (Physical Stock) are applied to the running balance** (they represent real corrections to inventory count) **but are NOT counted in velocity calculations.**

Physical Stock adjustments change the stock level but don't represent demand. If stock is adjusted from 45 to 0, the running balance drops to 0, but no "outward demand" is recorded for that day.

```python
# Physical Stock adjustments: apply to balance, not to velocity
if txn['channel'] == 'ignore' and txn['voucher_type'] == 'Physical Stock':
    # This IS an outward/inward for balance purposes
    if txn['is_inward']:
        day_inward += txn['quantity']  # Rare — stock count found more than expected
    else:
        day_outward += txn['quantity']  # Stock zeroed out or corrected down
    # But do NOT add to wholesale_out, online_out, or store_out
    # (they're not demand)
```

### Handling Credit Notes

Credit notes represent returns. A customer returns 60 units = inward of 60 units. This should:
- Increase the running balance (the stock is back)
- NOT be counted as "supply" for import cycle detection
- NOT offset the original sale in velocity calculation

The simplest approach: **treat credit notes as inward for balance purposes, but exclude them from velocity entirely.** If Hindustan Trading bought 60 and returned 60, the velocity should still show that 60-unit demand happened — the return is a separate event.

```python
if txn['voucher_type'] == 'Credit Note':
    # Increases balance (stock returned)
    day_inward += txn['quantity']
    # But not counted in any velocity metric
```

## Step 2: Calculate Velocity

### Core Principle

**Velocity = total outward units during in-stock periods ÷ total in-stock days**

"In-stock" means closing_qty > 0 on that day. Days where stock was zero or negative are excluded entirely — sales on those days are backorders/noise and don't represent normal demand.

### The Calculation

```python
def calculate_velocity(stock_item_name: str, 
                       daily_positions: list) -> dict:
    """
    Calculate wholesale and online demand velocity.
    
    Uses ALL in-stock days across the entire financial year.
    This captures seasonality and gives a representative average.
    Out-of-stock days are excluded from both numerator and denominator.
    
    Returns:
        {
            'wholesale_velocity': float,   # units per day
            'online_velocity': float,      # units per day
            'total_velocity': float,       # units per day
            'total_in_stock_days': int,
            'velocity_start_date': date,   # First in-stock day used
            'velocity_end_date': date,     # Last in-stock day used
        }
    """
    in_stock_days = [p for p in daily_positions if p['is_in_stock']]
    
    if not in_stock_days:
        return {
            'wholesale_velocity': 0,
            'online_velocity': 0,
            'total_velocity': 0,
            'total_in_stock_days': 0,
            'velocity_start_date': None,
            'velocity_end_date': None,
        }
    
    total_wholesale_out = sum(p['wholesale_out'] for p in in_stock_days)
    total_online_out = sum(p['online_out'] for p in in_stock_days)
    num_in_stock_days = len(in_stock_days)
    
    wholesale_velocity = total_wholesale_out / num_in_stock_days
    online_velocity = total_online_out / num_in_stock_days
    
    return {
        'wholesale_velocity': round(wholesale_velocity, 4),
        'online_velocity': round(online_velocity, 4),
        'total_velocity': round(wholesale_velocity + online_velocity, 4),
        'total_in_stock_days': num_in_stock_days,
        'velocity_start_date': in_stock_days[0]['position_date'],
        'velocity_end_date': in_stock_days[-1]['position_date'],
    }
```

### Example: Speedball Sealer

From the real data:
- In-stock days: Apr 1 - Jun 7 (68 days) + Nov 26 - Feb 24 (90 days, approximate) = 158 days
- Wholesale outward during in-stock days: 40 + 213 = 253 units
- Online outward during in-stock days: 0 + 32 = 32 units
- Wholesale velocity: 253 / 158 = 1.60 units/day = **48.0 units/month**
- Online velocity: 32 / 158 = 0.20 units/day = **6.1 units/month**
- Total velocity: 1.80 units/day = **54.1 units/month**

Note: this gives a more conservative (and realistic) velocity than just looking at the post-restock period, because it includes the slower April-May period.

## Step 3: Days to Stockout

Simple division:

```python
def calculate_days_to_stockout(current_stock: float, 
                                total_velocity: float) -> float:
    """
    Estimate days until stock hits zero.
    Uses total velocity (wholesale + online) since both drain the same pile.
    
    Returns:
        Number of days. None if velocity is 0 (no demand data).
    """
    if total_velocity <= 0:
        return None  # No demand data — can't predict
    
    if current_stock <= 0:
        return 0  # Already out of stock
    
    return current_stock / total_velocity
```

## Step 4: Import History Detection

Find the most recent import (purchase from supplier) for each SKU:

```python
def detect_import_history(stock_item_name: str,
                          transactions: list) -> dict:
    """
    Find import shipments for this SKU.
    Imports = Purchase vouchers from supplier-classified parties.
    """
    imports = [t for t in transactions 
               if t['channel'] == 'supplier' and t['is_inward']]
    
    if not imports:
        return {
            'last_import_date': None,
            'last_import_qty': None,
            'last_import_supplier': None,
            'import_count': 0,
            'avg_import_interval_days': None,
        }
    
    # Sort by date
    imports.sort(key=lambda t: t['date'])
    
    # Calculate average interval between imports
    intervals = []
    for i in range(1, len(imports)):
        delta = (imports[i]['date'] - imports[i-1]['date']).days
        intervals.append(delta)
    
    last = imports[-1]
    
    return {
        'last_import_date': last['date'],
        'last_import_qty': last['quantity'],
        'last_import_supplier': last['party'],
        'import_count': len(imports),
        'avg_import_interval_days': sum(intervals) / len(intervals) if intervals else None,
    }
```

## Step 5: Reorder Status Flag

```python
def determine_reorder_status(current_stock: float,
                              days_to_stockout: float,
                              supplier_lead_time: int,
                              total_velocity: float) -> tuple:
    """
    Determine reorder urgency.
    
    Args:
        current_stock: Current quantity on hand
        days_to_stockout: Estimated days until zero
        supplier_lead_time: Default lead time for this item's supplier (days)
        total_velocity: Total demand velocity (units/day)
    
    Returns:
        (status, suggested_qty)
        status: 'critical', 'warning', 'ok', 'out_of_stock', 'no_data'
    """
    if total_velocity <= 0:
        if current_stock <= 0:
            return ('out_of_stock', None)
        return ('no_data', None)
    
    if current_stock <= 0:
        # Already out of stock — order immediately
        suggested_qty = total_velocity * supplier_lead_time * 1.3  # 30% safety buffer
        return ('out_of_stock', round(suggested_qty))
    
    if days_to_stockout is None:
        return ('no_data', None)
    
    # Suggested order quantity: enough to cover lead time + 30% buffer
    suggested_qty = total_velocity * supplier_lead_time * 1.3
    
    if days_to_stockout <= supplier_lead_time:
        # You needed to order already — even if you order TODAY, stock will run out
        # before the shipment arrives
        return ('critical', round(suggested_qty))
    
    elif days_to_stockout <= supplier_lead_time + 30:
        # Buffer zone — order now to avoid running out
        return ('warning', round(suggested_qty))
    
    else:
        return ('ok', round(suggested_qty))
```

### Reorder Status Definitions

| Status | Meaning | Color | Action |
|--------|---------|-------|--------|
| `critical` | Days to stockout < supplier lead time. Even ordering today won't prevent a gap. | Red | Order immediately. Consider air freight. |
| `warning` | Days to stockout < supplier lead time + 30 day buffer. Approaching the point of no return. | Amber | Start the order process now. |
| `ok` | Sufficient stock for now. | Green | No action needed. |
| `out_of_stock` | Current stock is zero or negative. | Black/Dark Red | Order needed. Already losing sales. |
| `no_data` | Not enough transaction history to calculate velocity. New item or never sold. | Grey | Manual review needed. |

## Step 6: Brand-Level Rollup

```python
def compute_brand_metrics(category_name: str, 
                           sku_metrics: list,
                           supplier: dict) -> dict:
    """
    Aggregate SKU metrics to brand level.
    
    sku_metrics: list of sku_metrics records for this category
    supplier: supplier record with lead time info
    """
    total = len(sku_metrics)
    
    in_stock = sum(1 for s in sku_metrics if s['current_stock'] > 0)
    out_of_stock = sum(1 for s in sku_metrics if s['current_stock'] <= 0)
    critical = sum(1 for s in sku_metrics if s['reorder_status'] == 'critical')
    warning = sum(1 for s in sku_metrics if s['reorder_status'] == 'warning')
    ok = sum(1 for s in sku_metrics if s['reorder_status'] == 'ok')
    no_data = sum(1 for s in sku_metrics if s['reorder_status'] == 'no_data')
    
    # Weighted average days to stockout
    # Weight by total_velocity so fast-moving items have more impact
    weighted_sum = 0
    weight_total = 0
    for s in sku_metrics:
        if s['days_to_stockout'] is not None and s['total_velocity'] > 0:
            weighted_sum += s['days_to_stockout'] * s['total_velocity']
            weight_total += s['total_velocity']
    
    avg_days = weighted_sum / weight_total if weight_total > 0 else None
    
    return {
        'category_name': category_name,
        'total_skus': total,
        'in_stock_skus': in_stock,
        'out_of_stock_skus': out_of_stock,
        'critical_skus': critical,
        'warning_skus': warning,
        'ok_skus': ok,
        'no_data_skus': no_data,
        'avg_days_to_stockout': round(avg_days, 1) if avg_days else None,
        'primary_supplier': supplier.get('name') if supplier else None,
        'supplier_lead_time': supplier.get('lead_time_default') if supplier else None,
    }
```

## Full Computation Pipeline

The nightly job calls these in sequence:

```python
def run_computation_pipeline(db_conn):
    """
    Run after each nightly sync.
    Recomputes all derived metrics from raw transaction data.
    """
    
    # 1. Get all stock items
    stock_items = fetch_all_stock_items(db_conn)
    
    # 2. For each item, reconstruct positions and compute metrics
    for item in stock_items:
        transactions = fetch_transactions_for_item(db_conn, item['tally_name'])
        
        if not transactions:
            # No transactions — mark as no_data
            upsert_sku_metrics(db_conn, {
                'stock_item_name': item['tally_name'],
                'category_name': item['category_name'],
                'current_stock': item['closing_balance'],
                'reorder_status': 'no_data' if item['closing_balance'] > 0 else 'out_of_stock',
            })
            continue
        
        # Reconstruct daily positions
        positions = reconstruct_daily_positions(
            stock_item_name=item['tally_name'],
            opening_balance=parse_quantity(item.get('opening_balance', 0)),
            opening_date=date(2025, 4, 1),  # FY start
            transactions=transactions,
            end_date=date.today(),
        )
        
        # Bulk insert daily positions
        upsert_daily_positions(db_conn, positions)
        
        # Calculate velocity
        velocity = calculate_velocity(item['tally_name'], positions)
        
        # Detect import history
        import_history = detect_import_history(item['tally_name'], transactions)
        
        # Get supplier lead time
        supplier = get_supplier_for_category(db_conn, item['category_name'])
        lead_time = supplier['lead_time_default'] if supplier else 180  # Default 6 months
        
        # Days to stockout
        days_to_stockout = calculate_days_to_stockout(
            item['closing_balance'], velocity['total_velocity']
        )
        
        # Reorder status
        status, suggested_qty = determine_reorder_status(
            item['closing_balance'], days_to_stockout, lead_time, velocity['total_velocity']
        )
        
        # Save metrics
        upsert_sku_metrics(db_conn, {
            'stock_item_name': item['tally_name'],
            'category_name': item['category_name'],
            'current_stock': item['closing_balance'],
            **velocity,
            'days_to_stockout': days_to_stockout,
            'estimated_stockout_date': (date.today() + timedelta(days=days_to_stockout)) if days_to_stockout else None,
            **import_history,
            'reorder_status': status,
            'reorder_qty_suggested': suggested_qty,
        })
    
    # 3. Compute brand rollups
    categories = fetch_all_categories(db_conn)
    for cat in categories:
        sku_metrics = fetch_sku_metrics_for_category(db_conn, cat['tally_name'])
        supplier = get_supplier_for_category(db_conn, cat['tally_name'])
        brand_metrics = compute_brand_metrics(cat['tally_name'], sku_metrics, supplier)
        upsert_brand_metrics(db_conn, brand_metrics)
    
    print("Computation pipeline complete.")
```

## Performance Notes

- For 10,000 SKUs × 365 days, the daily_stock_positions table will have ~3.6M rows per year. The computation should run in minutes, not hours.
- The most expensive operation is reconstructing positions for all items. This can be parallelized.
- Consider only recomputing positions for items that had transactions since the last sync (optimization for later).
- The brand rollup is fast — it's just aggregating pre-computed SKU metrics.
