# 04 — Database Schema

## Overview

The UC database (`artlounge_reorder_uc`) reuses the same table structure with targeted changes: rename `tally_*` columns, drop Tally-specific fields, add UC-specific fields, add new tables for UC data.

## Schema Changes from Tally

### Renamed Columns

| Table | Old Column | New Column |
|---|---|---|
| `stock_categories` | `tally_name` | `name` |
| `stock_categories` | `tally_master_id` | `source_id` |
| `stock_items` | `tally_name` | `name` |
| `stock_items` | `tally_master_id` | `source_id` |
| `stock_items` | `tally_alter_id` | `sku_code` (UC's primary key) |
| `parties` | `tally_name` | `name` |
| `parties` | `tally_parent` | `party_group` |

### Dropped Columns

| Table | Column | Reason |
|---|---|---|
| `transactions` | `phys_stock_diff` | Tally Physical Stock workaround |
| `suppliers` | `backdate_physical_stock` | Tally workaround |
| `app_settings` | `backdate_physical_stock` key | Tally workaround |
| `app_settings` | `physical_stock_grace_days` key | Tally workaround |

### Added Columns

| Table | Column | Type | Purpose |
|---|---|---|---|
| `stock_items` | `sku_code` | VARCHAR(50) | UC SKU code (primary identifier) |
| `stock_items` | `ean` | VARCHAR(50) | Barcode |
| `stock_items` | `brand` | VARCHAR(200) | UC brand field |
| `stock_items` | `cost_price` | NUMERIC | From UC catalog |
| `stock_items` | `mrp` | NUMERIC | Max retail price |
| `stock_items` | `hsn_code` | VARCHAR(20) | Tax classification |
| `transactions` | `return_type` | VARCHAR(10) | CIR, RTO, or NULL |
| `transactions` | `uc_channel` | VARCHAR(50) | Raw UC channel code |
| `transactions` | `facility` | VARCHAR(50) | Source facility code |
| `transactions` | `shipping_package_code` | VARCHAR(50) | UC package reference |
| `sku_metrics` | `open_purchase` | NUMERIC | Pending PO qty (display only) |
| `sku_metrics` | `bad_inventory` | NUMERIC | Damaged stock |
| `sku_metrics` | `zero_activity_ratio` | NUMERIC | Zero-activity days / in-stock days |
| `sku_metrics` | `min_sample_met` | BOOLEAN | velocity has >= 14 in-stock days |

## New Tables

### `daily_inventory_snapshots`

Stores nightly inventory snapshots per SKU (aggregated across facilities).

```sql
CREATE TABLE daily_inventory_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    sku_code VARCHAR(50) NOT NULL,
    inventory INTEGER NOT NULL DEFAULT 0,
    inventory_blocked INTEGER NOT NULL DEFAULT 0,
    putaway_pending INTEGER NOT NULL DEFAULT 0,
    open_sale INTEGER NOT NULL DEFAULT 0,
    open_purchase INTEGER NOT NULL DEFAULT 0,
    bad_inventory INTEGER NOT NULL DEFAULT 0,
    available_stock INTEGER GENERATED ALWAYS AS
        (inventory - inventory_blocked + putaway_pending) STORED,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(snapshot_date, sku_code)
);
CREATE INDEX idx_snapshots_sku_date ON daily_inventory_snapshots(sku_code, snapshot_date);
```

### `facility_inventory` (optional — for drill-down)

Per-facility inventory breakdown.

```sql
CREATE TABLE facility_inventory (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    facility_code VARCHAR(50) NOT NULL,
    sku_code VARCHAR(50) NOT NULL,
    inventory INTEGER NOT NULL DEFAULT 0,
    inventory_blocked INTEGER NOT NULL DEFAULT 0,
    putaway_pending INTEGER NOT NULL DEFAULT 0,
    open_sale INTEGER NOT NULL DEFAULT 0,
    open_purchase INTEGER NOT NULL DEFAULT 0,
    bad_inventory INTEGER NOT NULL DEFAULT 0,
    UNIQUE(snapshot_date, facility_code, sku_code)
);
```

### `facilities`

Dynamic facility registry.

```sql
CREATE TABLE facilities (
    code VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200),
    party_name VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    discovered_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW()
);
```

### `grn_receipts` (for lead time computation)

```sql
CREATE TABLE grn_receipts (
    code VARCHAR(50) PRIMARY KEY,
    po_code VARCHAR(50),
    vendor_code VARCHAR(100),
    vendor_name VARCHAR(200),
    facility_code VARCHAR(50),
    received_date TIMESTAMP NOT NULL,
    po_created_date TIMESTAMP,
    total_quantity INTEGER,
    total_rejected INTEGER,
    computed_lead_days INTEGER,  -- received_date - po_created_date
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `returns`

```sql
CREATE TABLE returns (
    reverse_pickup_code VARCHAR(50) PRIMARY KEY,
    return_type VARCHAR(10) NOT NULL,  -- CIR or RTO
    sale_order_code VARCHAR(50),
    facility_code VARCHAR(50),
    channel VARCHAR(50),
    return_created_date TIMESTAMP,
    return_completed_date TIMESTAMP,
    invoice_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `return_items`

```sql
CREATE TABLE return_items (
    id SERIAL PRIMARY KEY,
    reverse_pickup_code VARCHAR(50) REFERENCES returns(reverse_pickup_code),
    sku_code VARCHAR(50) NOT NULL,
    item_name VARCHAR(200),
    quantity INTEGER NOT NULL DEFAULT 1,
    inventory_type VARCHAR(50),  -- GOOD_INVENTORY, BAD, etc.
    UNIQUE(reverse_pickup_code, sku_code)
);
```

## Tables Unchanged

These tables carry over as-is (structure identical):
- `suppliers` (minus `backdate_physical_stock` column)
- `overrides`, `override_audit_log`
- `sku_metrics` (plus new columns above)
- `brand_metrics`
- `daily_stock_positions`
- `sync_log`
- `app_settings` (minus Tally-specific keys)
- `users`

## Migration Script

A single SQL migration file (`db/migrations/uc_001_schema.sql`) creates the UC-specific schema. Run once when setting up the `artlounge_reorder_uc` database.
