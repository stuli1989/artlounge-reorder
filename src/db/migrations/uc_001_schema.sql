-- Unicommerce Migration: Complete schema for artlounge_reorder_uc
-- Run: PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder_uc -f src/db/migrations/uc_001_schema.sql

BEGIN;

-- ============================================================
-- 1. suppliers
-- ============================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id                  SERIAL PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    lead_time_sea       INTEGER,
    lead_time_air       INTEGER,
    lead_time_default   INTEGER NOT NULL,
    currency            TEXT DEFAULT 'USD',
    min_order_value     NUMERIC,
    typical_order_months INTEGER DEFAULT 6,
    buffer_override     NUMERIC,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. stock_categories (brands)
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_categories (
    id                  SERIAL PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    parent              TEXT,
    source_id           TEXT,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. stock_items (SKUs)
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_items (
    id                  SERIAL PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    sku_code            VARCHAR(50),
    stock_group         TEXT,
    category_name       TEXT NOT NULL,
    base_unit           TEXT,
    source_id           TEXT,
    opening_balance     NUMERIC DEFAULT 0,
    closing_balance     NUMERIC DEFAULT 0,
    closing_value       NUMERIC DEFAULT 0,
    part_no             TEXT,
    ean                 VARCHAR(50),
    brand               VARCHAR(200),
    cost_price          NUMERIC,
    mrp                 NUMERIC,
    hsn_code            VARCHAR(20),
    reorder_intent      TEXT DEFAULT 'normal',
    is_hazardous        BOOLEAN DEFAULT FALSE,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_reorder_intent CHECK (reorder_intent IN ('must_stock', 'normal', 'do_not_reorder'))
);
CREATE INDEX IF NOT EXISTS idx_stock_items_category ON stock_items(category_name);
CREATE INDEX IF NOT EXISTS idx_stock_items_intent ON stock_items(reorder_intent);
CREATE UNIQUE INDEX IF NOT EXISTS idx_stock_items_sku_code ON stock_items(sku_code) WHERE sku_code IS NOT NULL;

-- ============================================================
-- 4. parties
-- ============================================================
CREATE TABLE IF NOT EXISTS parties (
    id                  SERIAL PRIMARY KEY,
    name                TEXT UNIQUE NOT NULL,
    party_group         TEXT,
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
CREATE INDEX IF NOT EXISTS idx_parties_name ON parties(name);

-- ============================================================
-- 5. transactions
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id                  SERIAL PRIMARY KEY,
    txn_date            DATE NOT NULL,
    party_name          TEXT NOT NULL DEFAULT '',
    voucher_type        TEXT NOT NULL,
    voucher_number      TEXT NOT NULL DEFAULT '',
    stock_item_name     TEXT NOT NULL,
    quantity            NUMERIC NOT NULL,
    is_inward           BOOLEAN NOT NULL,
    rate                NUMERIC,
    amount              NUMERIC,
    channel             TEXT,
    return_type         VARCHAR(10),
    uc_channel          VARCHAR(50),
    facility            VARCHAR(50),
    shipping_package_code VARCHAR(50),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_txn_channel CHECK (channel IN (
        'supplier', 'wholesale', 'online', 'store', 'internal', 'ignore', 'unclassified'
    ))
);
-- UC dedup key: voucher_number (shipping package code or return code) + SKU + direction
ALTER TABLE transactions
    ADD CONSTRAINT uq_transactions_dedup
    UNIQUE (voucher_number, stock_item_name, is_inward);
CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_stock_item ON transactions(stock_item_name);
CREATE INDEX IF NOT EXISTS idx_txn_party ON transactions(party_name);
CREATE INDEX IF NOT EXISTS idx_txn_channel ON transactions(channel);
CREATE INDEX IF NOT EXISTS idx_txn_item_date ON transactions(stock_item_name, txn_date);

-- ============================================================
-- 6. daily_stock_positions
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_stock_positions (
    id                  BIGSERIAL PRIMARY KEY,
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
CREATE INDEX IF NOT EXISTS idx_daily_pos_date ON daily_stock_positions(position_date);
CREATE INDEX IF NOT EXISTS idx_daily_pos_in_stock ON daily_stock_positions(stock_item_name, is_in_stock);

-- ============================================================
-- 7. sku_metrics
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
    -- V2 columns
    abc_class                   TEXT,
    xyz_class                   TEXT,
    demand_cv                   NUMERIC,
    total_revenue               NUMERIC DEFAULT 0,
    wma_wholesale_velocity      NUMERIC DEFAULT 0,
    wma_online_velocity         NUMERIC DEFAULT 0,
    wma_total_velocity          NUMERIC DEFAULT 0,
    trend_direction             TEXT DEFAULT 'flat',
    trend_ratio                 NUMERIC,
    safety_buffer               NUMERIC DEFAULT 1.3,
    -- UC-specific columns
    open_purchase               NUMERIC DEFAULT 0,
    bad_inventory               NUMERIC DEFAULT 0,
    zero_activity_ratio         NUMERIC,
    min_sample_met              BOOLEAN DEFAULT TRUE,
    computed_at                 TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_reorder_status CHECK (reorder_status IN (
        'critical', 'warning', 'ok', 'out_of_stock', 'stocked_out', 'no_demand'
    )),
    CONSTRAINT valid_trend_direction CHECK (trend_direction IN ('up', 'down', 'flat')),
    CONSTRAINT valid_abc_class CHECK (abc_class IS NULL OR abc_class IN ('A', 'B', 'C')),
    CONSTRAINT valid_xyz_class CHECK (xyz_class IS NULL OR xyz_class IN ('X', 'Y', 'Z'))
);
CREATE INDEX IF NOT EXISTS idx_sku_metrics_category ON sku_metrics(category_name);
CREATE INDEX IF NOT EXISTS idx_sku_metrics_status ON sku_metrics(reorder_status);
CREATE INDEX IF NOT EXISTS idx_sku_metrics_stockout ON sku_metrics(days_to_stockout);
CREATE INDEX IF NOT EXISTS idx_sku_metrics_abc ON sku_metrics(abc_class);
CREATE INDEX IF NOT EXISTS idx_sku_metrics_trend ON sku_metrics(trend_direction);

-- ============================================================
-- 8. brand_metrics
-- ============================================================
CREATE TABLE IF NOT EXISTS brand_metrics (
    id                          SERIAL PRIMARY KEY,
    category_name               TEXT UNIQUE NOT NULL,
    total_skus                  INTEGER NOT NULL DEFAULT 0,
    in_stock_skus               INTEGER NOT NULL DEFAULT 0,
    out_of_stock_skus           INTEGER NOT NULL DEFAULT 0,
    critical_skus               INTEGER NOT NULL DEFAULT 0,
    warning_skus                INTEGER NOT NULL DEFAULT 0,
    ok_skus                     INTEGER NOT NULL DEFAULT 0,
    no_data_skus                INTEGER NOT NULL DEFAULT 0,
    stocked_out_skus            INTEGER NOT NULL DEFAULT 0,
    no_demand_skus              INTEGER NOT NULL DEFAULT 0,
    avg_days_to_stockout        NUMERIC,
    min_days_to_stockout        NUMERIC,
    dead_stock_skus             INTEGER DEFAULT 0,
    slow_mover_skus             INTEGER DEFAULT 0,
    a_class_skus                INTEGER DEFAULT 0,
    b_class_skus                INTEGER DEFAULT 0,
    c_class_skus                INTEGER DEFAULT 0,
    inactive_skus               INTEGER DEFAULT 0,
    primary_supplier            TEXT,
    supplier_lead_time          INTEGER,
    computed_at                 TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_brand_metrics_name ON brand_metrics(category_name);

-- ============================================================
-- 9. overrides
-- ============================================================
CREATE TABLE IF NOT EXISTS overrides (
    id                  SERIAL PRIMARY KEY,
    stock_item_name     TEXT NOT NULL,
    field_name          TEXT NOT NULL,
    override_value      TEXT NOT NULL,
    reason              TEXT,
    created_by          TEXT DEFAULT 'system',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    expires_at          TIMESTAMPTZ,
    is_active           BOOLEAN DEFAULT TRUE,
    UNIQUE(stock_item_name, field_name, is_active)
);
CREATE INDEX IF NOT EXISTS idx_overrides_item ON overrides(stock_item_name);

-- ============================================================
-- 10. override_audit_log
-- ============================================================
CREATE TABLE IF NOT EXISTS override_audit_log (
    id                  SERIAL PRIMARY KEY,
    override_id         INTEGER REFERENCES overrides(id),
    action              TEXT NOT NULL,
    old_value           TEXT,
    new_value           TEXT,
    changed_by          TEXT DEFAULT 'system',
    changed_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 11. app_settings
-- ============================================================
CREATE TABLE IF NOT EXISTS app_settings (
    key                 TEXT PRIMARY KEY,
    value               TEXT NOT NULL,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO app_settings (key, value) VALUES ('dead_stock_threshold_days', '90') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('slow_mover_velocity_threshold', '0.1') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('abc_a_threshold', '0.80') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('abc_b_threshold', '0.95') ON CONFLICT DO NOTHING;
-- Updated buffer matrix per UC plan (F14)
INSERT INTO app_settings (key, value) VALUES ('buffer_ax', '1.2') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_ay', '1.3') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_az', '1.5') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_bx', '1.15') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_by', '1.25') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_bz', '1.4') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_cx', '1.1') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_cy', '1.2') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_cz', '1.3') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('wma_window_days', '90') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('trend_up_threshold', '1.2') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('trend_down_threshold', '0.8') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('min_velocity_sample_days', '14') ON CONFLICT DO NOTHING;

-- ============================================================
-- 12. sync_log
-- ============================================================
CREATE TABLE IF NOT EXISTS sync_log (
    id                  SERIAL PRIMARY KEY,
    sync_started        TIMESTAMPTZ NOT NULL,
    sync_completed      TIMESTAMPTZ,
    status              TEXT DEFAULT 'running',
    source              TEXT DEFAULT 'unicommerce',
    CONSTRAINT valid_sync_status CHECK (status IN ('running', 'completed', 'failed')),
    categories_synced   INTEGER DEFAULT 0,
    items_synced        INTEGER DEFAULT 0,
    transactions_synced INTEGER DEFAULT 0,
    dispatches_synced   INTEGER DEFAULT 0,
    returns_synced      INTEGER DEFAULT 0,
    grns_synced         INTEGER DEFAULT 0,
    txn_from_date       DATE,
    txn_to_date         DATE,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 13. users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id                  SERIAL PRIMARY KEY,
    username            TEXT UNIQUE NOT NULL,
    password_hash       TEXT NOT NULL,
    role                TEXT DEFAULT 'viewer',
    is_active           BOOLEAN DEFAULT TRUE,
    last_login          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 14. facilities (NEW — dynamic facility registry)
-- ============================================================
CREATE TABLE IF NOT EXISTS facilities (
    code                VARCHAR(50) PRIMARY KEY,
    name                VARCHAR(200),
    party_name          VARCHAR(200),
    is_active           BOOLEAN DEFAULT TRUE,
    discovered_at       TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 15. daily_inventory_snapshots (NEW — UC inventory snapshots)
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_inventory_snapshots (
    id                  SERIAL PRIMARY KEY,
    snapshot_date       DATE NOT NULL,
    sku_code            VARCHAR(50) NOT NULL,
    inventory           INTEGER NOT NULL DEFAULT 0,
    inventory_blocked   INTEGER NOT NULL DEFAULT 0,
    putaway_pending     INTEGER NOT NULL DEFAULT 0,
    open_sale           INTEGER NOT NULL DEFAULT 0,
    open_purchase       INTEGER NOT NULL DEFAULT 0,
    bad_inventory       INTEGER NOT NULL DEFAULT 0,
    available_stock     INTEGER GENERATED ALWAYS AS
        (inventory - inventory_blocked + putaway_pending) STORED,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(snapshot_date, sku_code)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_sku_date ON daily_inventory_snapshots(sku_code, snapshot_date);

-- ============================================================
-- 16. facility_inventory (NEW — per-facility breakdown)
-- ============================================================
CREATE TABLE IF NOT EXISTS facility_inventory (
    id                  SERIAL PRIMARY KEY,
    snapshot_date       DATE NOT NULL,
    facility_code       VARCHAR(50) NOT NULL,
    sku_code            VARCHAR(50) NOT NULL,
    inventory           INTEGER NOT NULL DEFAULT 0,
    inventory_blocked   INTEGER NOT NULL DEFAULT 0,
    putaway_pending     INTEGER NOT NULL DEFAULT 0,
    open_sale           INTEGER NOT NULL DEFAULT 0,
    open_purchase       INTEGER NOT NULL DEFAULT 0,
    bad_inventory       INTEGER NOT NULL DEFAULT 0,
    UNIQUE(snapshot_date, facility_code, sku_code)
);

-- ============================================================
-- 17. grn_receipts (NEW — for lead time computation)
-- ============================================================
CREATE TABLE IF NOT EXISTS grn_receipts (
    code                VARCHAR(50) PRIMARY KEY,
    po_code             VARCHAR(50),
    vendor_code         VARCHAR(100),
    vendor_name         VARCHAR(200),
    facility_code       VARCHAR(50),
    received_date       TIMESTAMPTZ NOT NULL,
    po_created_date     TIMESTAMPTZ,
    total_quantity      INTEGER,
    total_rejected      INTEGER,
    computed_lead_days  INTEGER,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 18. returns (NEW — return header)
-- ============================================================
CREATE TABLE IF NOT EXISTS returns (
    reverse_pickup_code VARCHAR(50) PRIMARY KEY,
    return_type         VARCHAR(10) NOT NULL,
    sale_order_code     VARCHAR(50),
    facility_code       VARCHAR(50),
    channel             VARCHAR(50),
    return_created_date TIMESTAMPTZ,
    return_completed_date TIMESTAMPTZ,
    invoice_code        VARCHAR(50),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 19. return_items (NEW — return line items)
-- ============================================================
CREATE TABLE IF NOT EXISTS return_items (
    id                  SERIAL PRIMARY KEY,
    reverse_pickup_code VARCHAR(50) REFERENCES returns(reverse_pickup_code),
    sku_code            VARCHAR(50) NOT NULL,
    item_name           VARCHAR(200),
    quantity            INTEGER NOT NULL DEFAULT 1,
    inventory_type      VARCHAR(50),
    UNIQUE(reverse_pickup_code, sku_code)
);

COMMIT;
