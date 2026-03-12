# T11: Stockout Prediction + Import History + Reorder Status

## Prerequisites
- T10 completed (velocity calculation exists)

## Objective
Implement three related computations: days-to-stockout, import history detection, and reorder status flags.

## File to Create

### `engine/reorder.py`

#### 1. `calculate_days_to_stockout(current_stock: float, total_velocity: float) -> float | None`

```python
def calculate_days_to_stockout(current_stock, total_velocity):
    if total_velocity <= 0:
        return None   # No demand data — can't predict
    if current_stock <= 0:
        return 0      # Already out of stock
    return current_stock / total_velocity
```

#### 2. `detect_import_history(stock_item_name: str, transactions: list[dict]) -> dict`

Find all import shipments (Purchase from supplier-classified parties):

```python
def detect_import_history(stock_item_name, transactions):
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

    imports.sort(key=lambda t: t['date'])

    # Average interval between imports
    intervals = []
    for i in range(1, len(imports)):
        delta = (imports[i]['date'] - imports[i-1]['date']).days
        intervals.append(delta)

    last = imports[-1]
    return {
        'last_import_date': last['date'],
        'last_import_qty': last['quantity'],
        'last_import_supplier': last.get('party_name', last.get('party', '')),
        'import_count': len(imports),
        'avg_import_interval_days': sum(intervals) / len(intervals) if intervals else None,
    }
```

#### 3. `determine_reorder_status(current_stock, days_to_stockout, supplier_lead_time, total_velocity) -> tuple[str, float | None]`

Returns `(status, suggested_qty)`:

| Status | Condition | Color |
|--------|-----------|-------|
| `out_of_stock` | current_stock <= 0 | Dark Red |
| `critical` | days_to_stockout <= supplier_lead_time | Red |
| `warning` | days_to_stockout <= supplier_lead_time + 30 | Amber |
| `ok` | days_to_stockout > supplier_lead_time + 30 | Green |
| `no_data` | total_velocity <= 0 | Grey |

**Suggested order quantity formula:**
```
suggested_qty = total_velocity * supplier_lead_time * 1.3  (30% safety buffer)
```

```python
def determine_reorder_status(current_stock, days_to_stockout, supplier_lead_time, total_velocity):
    if total_velocity <= 0:
        if current_stock <= 0:
            return ('out_of_stock', None)
        return ('no_data', None)

    suggested_qty = total_velocity * supplier_lead_time * 1.3

    if current_stock <= 0:
        return ('out_of_stock', round(suggested_qty))

    if days_to_stockout is None:
        return ('no_data', None)

    if days_to_stockout <= supplier_lead_time:
        return ('critical', round(suggested_qty))
    elif days_to_stockout <= supplier_lead_time + 30:
        return ('warning', round(suggested_qty))
    else:
        return ('ok', round(suggested_qty))
```

#### 4. `get_supplier_for_category(db_conn, category_name: str) -> dict | None`
- Query suppliers table, cross-reference with the transactions to find which supplier supplies this brand
- Fallback: return None if no supplier found (use default lead time of 180 days)

```sql
SELECT DISTINCT s.* FROM suppliers s
JOIN parties p ON p.tally_name = s.tally_party
JOIN transactions t ON t.party_name = p.tally_name
JOIN stock_items si ON si.tally_name = t.stock_item_name
WHERE si.category_name = %s AND t.channel = 'supplier' AND t.is_inward = TRUE
LIMIT 1
```

## Test Case: Speedball Sealer
- Current stock: 18
- Total velocity: ~1.8 units/day
- Days to stockout: 18 / 1.8 = ~10 days
- Supplier lead time: 180 days (sea freight)
- Status: **CRITICAL** (10 << 180)
- Suggested qty (sea): 1.8 * 180 * 1.3 = ~421 units

## Acceptance Criteria
- [ ] Days-to-stockout returns None when velocity is 0, returns 0 when already out of stock
- [ ] Import history correctly identifies supplier purchases only
- [ ] Reorder status logic matches the priority: out_of_stock > critical > warning > ok > no_data
- [ ] Suggested quantity uses velocity * lead_time * 1.3 formula
- [ ] Supplier lookup falls back gracefully when no supplier found
