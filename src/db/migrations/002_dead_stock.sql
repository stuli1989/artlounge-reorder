-- Dead stock detection: app_settings table + new columns on sku_metrics and brand_metrics

BEGIN;

-- app_settings: key-value config table
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO app_settings (key, value) VALUES ('dead_stock_threshold_days', '30') ON CONFLICT DO NOTHING;

-- sku_metrics: dead stock fields
ALTER TABLE sku_metrics
    ADD COLUMN IF NOT EXISTS last_sale_date DATE,
    ADD COLUMN IF NOT EXISTS total_zero_activity_days INTEGER DEFAULT 0;

-- brand_metrics: dead stock rollup count
ALTER TABLE brand_metrics ADD COLUMN IF NOT EXISTS dead_stock_skus INTEGER DEFAULT 0;

COMMIT;
