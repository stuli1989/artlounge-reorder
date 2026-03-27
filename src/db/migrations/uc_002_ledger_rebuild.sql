-- uc_002_ledger_rebuild.sql
-- Ledger-based pipeline rebuild: single source of truth

BEGIN;

-- 1. Drop tables no longer needed
DROP TABLE IF EXISTS facility_inventory CASCADE;
DROP TABLE IF EXISTS daily_inventory_snapshots CASCADE;
DROP TABLE IF EXISTS return_items CASCADE;
DROP TABLE IF EXISTS returns CASCADE;
DROP TABLE IF EXISTS grn_receipts CASCADE;
DROP TABLE IF EXISTS facilities CASCADE;

-- 2. Recreate transactions table with ledger schema
DROP TABLE IF EXISTS transactions CASCADE;
CREATE TABLE transactions (
    id BIGSERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    txn_date DATE NOT NULL,
    entity TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_code TEXT NOT NULL DEFAULT '',
    txn_type TEXT NOT NULL CHECK (txn_type IN ('IN', 'OUT')),
    units NUMERIC NOT NULL DEFAULT 0,
    stock_change NUMERIC NOT NULL DEFAULT 0,
    facility TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'internal',
    is_demand BOOLEAN NOT NULL DEFAULT FALSE,
    sale_order_code TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_code, stock_item_name, txn_type, txn_date, units, facility)
);
CREATE INDEX idx_txn_sku ON transactions(stock_item_name);
CREATE INDEX idx_txn_date ON transactions(txn_date);
CREATE INDEX idx_txn_sku_date ON transactions(stock_item_name, txn_date);

-- 3. Drop snapshot-derived columns from sku_metrics
ALTER TABLE sku_metrics DROP COLUMN IF EXISTS open_purchase;
ALTER TABLE sku_metrics DROP COLUMN IF EXISTS bad_inventory;

-- 4. Update sync_log for ledger-based sync
ALTER TABLE sync_log DROP COLUMN IF EXISTS dispatches_synced;
ALTER TABLE sync_log DROP COLUMN IF EXISTS returns_synced;
ALTER TABLE sync_log DROP COLUMN IF EXISTS grns_synced;
ALTER TABLE sync_log DROP COLUMN IF EXISTS items_synced;
ALTER TABLE sync_log ADD COLUMN IF NOT EXISTS ledger_rows_loaded INT DEFAULT 0;
ALTER TABLE sync_log ADD COLUMN IF NOT EXISTS facilities_synced INT DEFAULT 0;

-- 5. Create channel_rules table
CREATE TABLE IF NOT EXISTS channel_rules (
    id SERIAL PRIMARY KEY,
    rule_type TEXT NOT NULL,
    match_value TEXT NOT NULL,
    facility_filter TEXT,
    channel TEXT NOT NULL,
    priority INT NOT NULL DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Seed default channel rules
INSERT INTO channel_rules (rule_type, match_value, channel, priority) VALUES
    ('entity', 'GRN', 'supplier', 100),
    ('entity', 'INVENTORY_ADJUSTMENT', 'internal', 90),
    ('entity', 'INBOUND_GATEPASS', 'internal', 90),
    ('entity', 'OUTBOUND_GATEPASS', 'internal', 90),
    ('entity', 'PUTAWAY_CANCELLED_ITEM', 'internal', 90),
    ('entity', 'PUTAWAY_PICKLIST_ITEM', 'internal', 90),
    ('entity', 'PUTAWAY_CIR', 'online', 80),
    ('entity', 'PUTAWAY_RTO', 'online', 80);

INSERT INTO channel_rules (rule_type, match_value, channel, priority) VALUES
    ('sale_order_prefix', 'MA-', 'online', 70),
    ('sale_order_prefix', 'B2C-', 'online', 70);

INSERT INTO channel_rules (rule_type, match_value, facility_filter, channel, priority) VALUES
    ('sale_order_prefix', 'SO', 'PPETPLKALAGHODA', 'store', 60),
    ('sale_order_prefix', 'SO', 'ppetpl', 'wholesale', 50);

-- Default fallback for PICKLIST with no matching rule
INSERT INTO channel_rules (rule_type, match_value, channel, priority) VALUES
    ('default', 'PICKLIST', 'wholesale', 0);

-- 7. Add columns from older migrations that uc_001 missed
ALTER TABLE stock_items ADD COLUMN IF NOT EXISTS use_xyz_buffer BOOLEAN DEFAULT NULL;
ALTER TABLE overrides ADD COLUMN IF NOT EXISTS stale_since TIMESTAMPTZ;
ALTER TABLE overrides ADD COLUMN IF NOT EXISTS computed_value_at_creation NUMERIC;
ALTER TABLE overrides ADD COLUMN IF NOT EXISTS computed_value_latest NUMERIC;
ALTER TABLE overrides ADD COLUMN IF NOT EXISTS drift_pct NUMERIC;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS store_velocity NUMERIC DEFAULT 0;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS wma_store_velocity NUMERIC DEFAULT 0;

-- 8. Seed app_settings if empty
INSERT INTO app_settings (key, value) VALUES
    ('use_xyz_buffer', 'false'),
    ('dead_stock_threshold_days', '90'),
    ('slow_mover_velocity_threshold', '0.1'),
    ('abc_a_threshold', '0.80'),
    ('abc_b_threshold', '0.95'),
    ('buffer_ax', '1.2'), ('buffer_ay', '1.3'), ('buffer_az', '1.5'),
    ('buffer_bx', '1.15'), ('buffer_by', '1.25'), ('buffer_bz', '1.4'),
    ('buffer_cx', '1.1'), ('buffer_cy', '1.2'), ('buffer_cz', '1.3'),
    ('wma_window_days', '90'),
    ('trend_up_threshold', '1.2'),
    ('trend_down_threshold', '0.8'),
    ('min_velocity_sample_days', '14')
ON CONFLICT (key) DO NOTHING;

-- 9. Truncate positions and metrics for clean rebuild
TRUNCATE daily_stock_positions;
TRUNCATE sku_metrics;
TRUNCATE brand_metrics;

COMMIT;
