BEGIN;

-- 1. Inventory snapshots from UC Snapshot API (nightly pull)
CREATE TABLE IF NOT EXISTS inventory_snapshots (
    id BIGSERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    inventory NUMERIC NOT NULL DEFAULT 0,
    inventory_blocked NUMERIC NOT NULL DEFAULT 0,
    bad_inventory NUMERIC NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_item_name, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_snap_sku ON inventory_snapshots(stock_item_name);

-- 2. KG demand from Shipping Package API
CREATE TABLE IF NOT EXISTS kg_demand (
    id BIGSERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    txn_date DATE NOT NULL,
    quantity NUMERIC NOT NULL,
    channel TEXT NOT NULL,
    shipping_package_code TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_item_name, shipping_package_code)
);
CREATE INDEX IF NOT EXISTS idx_kg_sku_date ON kg_demand(stock_item_name, txn_date);

-- 3. Drift log for monitoring
CREATE TABLE IF NOT EXISTS drift_log (
    id BIGSERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    check_date DATE NOT NULL,
    forward_walk_stock NUMERIC,
    snapshot_stock NUMERIC,
    drift NUMERIC,
    inventory_blocked NUMERIC,
    bad_inventory NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMIT;
