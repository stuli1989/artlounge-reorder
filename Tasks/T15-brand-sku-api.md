# T15: Brand Overview + SKU Detail API Endpoints

## Prerequisites
- T14 (FastAPI skeleton exists)

## Objective
Implement the API endpoints for the Brand Overview and SKU Detail dashboard views.

## Files to Modify

### 1. `api/routes/brands.py`

#### `GET /api/brands`
Returns list of brand metrics, sorted by urgency (critical first).

Query params:
- `search` (optional) — filter by brand name (case-insensitive ILIKE)

Response:
```json
[
  {
    "category_name": "Speedball",
    "total_skus": 847,
    "in_stock_skus": 650,
    "out_of_stock_skus": 40,
    "critical_skus": 12,
    "warning_skus": 45,
    "ok_skus": 650,
    "no_data_skus": 100,
    "avg_days_to_stockout": 42.5,
    "primary_supplier": "Speedball Art Products",
    "supplier_lead_time": 180,
    "computed_at": "2026-03-11T02:00:00Z"
  }
]
```

SQL:
```sql
SELECT * FROM brand_metrics
WHERE (%s IS NULL OR category_name ILIKE %s)
ORDER BY critical_skus DESC, warning_skus DESC, avg_days_to_stockout ASC NULLS LAST
```

#### `GET /api/brands/summary`
Returns aggregate summary stats for the header cards:
```json
{
  "total_brands": 23,
  "brands_with_critical": 5,
  "brands_with_warning": 8,
  "total_skus_out_of_stock": 312
}
```

### 2. `api/routes/skus.py`

#### `GET /api/brands/{category_name}/skus`
Returns SKU metrics for a specific brand.

Query params:
- `status` (optional) — comma-separated: "critical,warning"
- `min_velocity` (optional) — float, filter out slow/dead stock
- `sort` (optional) — column name, default "days_to_stockout"
- `sort_dir` (optional) — "asc" or "desc", default "asc"
- `search` (optional) — filter by SKU name

Response: list of sku_metrics records.

SQL:
```sql
SELECT * FROM sku_metrics
WHERE category_name = %s
  AND (%s IS NULL OR reorder_status = ANY(%s))
  AND (%s IS NULL OR total_velocity >= %s)
  AND (%s IS NULL OR stock_item_name ILIKE %s)
ORDER BY days_to_stockout ASC NULLS LAST
```

#### `GET /api/brands/{category_name}/skus/{stock_item_name}/positions`
Returns daily stock position data for charting.

Query params:
- `from_date` (optional) — default FY start
- `to_date` (optional) — default today

Response:
```json
[
  {
    "position_date": "2025-04-01",
    "opening_qty": 45,
    "closing_qty": 45,
    "inward_qty": 0,
    "outward_qty": 0,
    "wholesale_out": 0,
    "online_out": 0,
    "is_in_stock": true
  }
]
```

#### `GET /api/brands/{category_name}/skus/{stock_item_name}/transactions`
Returns transaction history for a specific SKU.

Query params:
- `limit` (optional) — default 50

Response: list of transaction records ordered by date DESC.

## URL Encoding Note
Stock item names and category names may contain special characters (spaces, ampersands). Use URL encoding. FastAPI handles this automatically via path parameters.

## Acceptance Criteria
- [ ] Brand list sorted by critical_skus DESC, then warning_skus DESC
- [ ] Brand summary returns aggregate counts
- [ ] SKU list filterable by status, velocity, and search
- [ ] Positions endpoint returns daily data for charting
- [ ] Transactions endpoint returns recent history with limit
- [ ] NULL days_to_stockout sorts to bottom (NULLS LAST)
- [ ] All endpoints use `get_db()` context manager
- [ ] All queries parameterized (no SQL injection)
