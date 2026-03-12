-- Art Lounge Reorder System — Database Schema
-- Run: psql -U reorder_app -d artlounge_reorder -f db/schema.sql

BEGIN;

-- ============================================================
-- 1. suppliers — International brands/suppliers
-- ============================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id                  SERIAL PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    tally_party         TEXT,
    lead_time_sea       INTEGER,
    lead_time_air       INTEGER,
    lead_time_default   INTEGER NOT NULL,
    currency            TEXT DEFAULT 'USD',
    min_order_value     NUMERIC,
    typical_order_months INTEGER DEFAULT 6,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. stock_categories — Brands (Tally stock categories)
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_categories (
    id                  SERIAL PRIMARY KEY,
    tally_name          TEXT UNIQUE NOT NULL,
    parent              TEXT,
    tally_master_id     TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stock_categories_name ON stock_categories(tally_name);

-- ============================================================
-- 3. stock_items — SKUs
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_items (
    id                  SERIAL PRIMARY KEY,
    tally_name          TEXT UNIQUE NOT NULL,
    stock_group         TEXT,
    category_name       TEXT NOT NULL,
    base_unit           TEXT,
    tally_master_id     TEXT,
    opening_balance     NUMERIC DEFAULT 0,
    closing_balance     NUMERIC DEFAULT 0,
    closing_value       NUMERIC DEFAULT 0,
    part_no             TEXT,
    is_hazardous        BOOLEAN DEFAULT FALSE,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stock_items_category ON stock_items(category_name);
CREATE INDEX IF NOT EXISTS idx_stock_items_name ON stock_items(tally_name);

-- ============================================================
-- 4. parties — Customers, suppliers, internal entities
-- ============================================================
CREATE TABLE IF NOT EXISTS parties (
    id                  SERIAL PRIMARY KEY,
    tally_name          TEXT UNIQUE NOT NULL,
    tally_parent        TEXT,
    channel             TEXT NOT NULL DEFAULT 'unclassified',
    supplier_id         INTEGER REFERENCES suppliers(id),
    classified_at       TIMESTAMPTZ,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_channel CHECK (channel IN (
        'supplier', 'wholesale', 'online', 'store', 'internal', 'ignore', 'unclassified'
    ))
);
CREATE INDEX IF NOT EXISTS idx_parties_channel ON parties(channel);
CREATE INDEX IF NOT EXISTS idx_parties_name ON parties(tally_name);

-- ============================================================
-- 5. transactions — Inventory vouchers from Tally
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id                  SERIAL PRIMARY KEY,
    txn_date            DATE NOT NULL,
    party_name          TEXT NOT NULL,
    voucher_type        TEXT NOT NULL,
    voucher_number      TEXT,
    stock_item_name     TEXT NOT NULL,
    quantity            NUMERIC NOT NULL,
    is_inward           BOOLEAN NOT NULL,
    rate                NUMERIC,
    amount              NUMERIC,
    channel             TEXT,
    tally_master_id     TEXT,
    tally_alter_id      TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(txn_date, voucher_number, stock_item_name, quantity, is_inward, rate)
);
CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_stock_item ON transactions(stock_item_name);
CREATE INDEX IF NOT EXISTS idx_txn_party ON transactions(party_name);
CREATE INDEX IF NOT EXISTS idx_txn_channel ON transactions(channel);
CREATE INDEX IF NOT EXISTS idx_txn_item_date ON transactions(stock_item_name, txn_date);

-- ============================================================
-- 6. daily_stock_positions — Reconstructed daily stock levels
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_stock_positions (
    id                  SERIAL PRIMARY KEY,
    stock_item_name     TEXT NOT NULL,
    position_date       DATE NOT NULL,
    opening_qty         NUMERIC NOT NULL,
    inward_qty          NUMERIC DEFAULT 0,
    outward_qty         NUMERIC DEFAULT 0,
    closing_qty         NUMERIC NOT NULL,
    wholesale_out       NUMERIC DEFAULT 0,
    online_out          NUMERIC DEFAULT 0,
    store_out           NUMERIC DEFAULT 0,
    is_in_stock         BOOLEAN NOT NULL,
    UNIQUE(stock_item_name, position_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_pos_item ON daily_stock_positions(stock_item_name);
CREATE INDEX IF NOT EXISTS idx_daily_pos_date ON daily_stock_positions(position_date);
CREATE INDEX IF NOT EXISTS idx_daily_pos_in_stock ON daily_stock_positions(stock_item_name, is_in_stock);

-- ============================================================
-- 7. sku_metrics — Per-SKU computed metrics
-- ============================================================
CREATE TABLE IF NOT EXISTS sku_metrics (
    id                          SERIAL PRIMARY KEY,
    stock_item_name             TEXT UNIQUE NOT NULL,
    category_name               TEXT NOT NULL,
    current_stock               NUMERIC NOT NULL,
    wholesale_velocity          NUMERIC DEFAULT 0,
    online_velocity             NUMERIC DEFAULT 0,
    total_velocity              NUMERIC DEFAULT 0,
    total_in_stock_days         INTEGER DEFAULT 0,
    velocity_start_date         DATE,
    velocity_end_date           DATE,
    days_to_stockout            NUMERIC,
    estimated_stockout_date     DATE,
    last_import_date            DATE,
    last_import_qty             NUMERIC,
    last_import_supplier        TEXT,
    reorder_status              TEXT DEFAULT 'ok',
    reorder_qty_suggested       NUMERIC,
    last_sale_date              DATE,
    total_zero_activity_days    INTEGER DEFAULT 0,
    computed_at                 TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_reorder_status CHECK (reorder_status IN (
        'critical', 'warning', 'ok', 'out_of_stock', 'no_data'
    ))
);
CREATE INDEX IF NOT EXISTS idx_sku_metrics_category ON sku_metrics(category_name);
CREATE INDEX IF NOT EXISTS idx_sku_metrics_status ON sku_metrics(reorder_status);
CREATE INDEX IF NOT EXISTS idx_sku_metrics_stockout ON sku_metrics(days_to_stockout);

-- ============================================================
-- 8. brand_metrics — Per-brand rollup
-- ============================================================
CREATE TABLE IF NOT EXISTS brand_metrics (
    id                          SERIAL PRIMARY KEY,
    category_name               TEXT UNIQUE NOT NULL,
    total_skus                  INTEGER DEFAULT 0,
    in_stock_skus               INTEGER DEFAULT 0,
    out_of_stock_skus           INTEGER DEFAULT 0,
    critical_skus               INTEGER DEFAULT 0,
    warning_skus                INTEGER DEFAULT 0,
    ok_skus                     INTEGER DEFAULT 0,
    no_data_skus                INTEGER DEFAULT 0,
    avg_days_to_stockout        NUMERIC,
    dead_stock_skus             INTEGER DEFAULT 0,
    primary_supplier            TEXT,
    supplier_lead_time          INTEGER,
    computed_at                 TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_brand_metrics_name ON brand_metrics(category_name);

-- ============================================================
-- 9. app_settings — Key-value configuration
-- ============================================================
CREATE TABLE IF NOT EXISTS app_settings (
    key                 TEXT PRIMARY KEY,
    value               TEXT NOT NULL,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO app_settings (key, value) VALUES ('dead_stock_threshold_days', '30') ON CONFLICT DO NOTHING;

-- ============================================================
-- 10. sync_log — Sync audit trail
-- ============================================================
CREATE TABLE IF NOT EXISTS sync_log (
    id                  SERIAL PRIMARY KEY,
    sync_started        TIMESTAMPTZ NOT NULL,
    sync_completed      TIMESTAMPTZ,
    status              TEXT DEFAULT 'running',
    categories_synced   INTEGER DEFAULT 0,
    items_synced        INTEGER DEFAULT 0,
    transactions_synced INTEGER DEFAULT 0,
    new_parties_found   INTEGER DEFAULT 0,
    txn_from_date       DATE,
    txn_to_date         DATE,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMIT;
