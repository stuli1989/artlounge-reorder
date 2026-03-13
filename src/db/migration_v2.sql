-- V2 Intelligence Upgrade Migration
-- ABC/XYZ classification, WMA velocity, trend detection, variable safety buffers
-- Run: PGPASSWORD=password psql -U reorder_app -d artlounge_reorder -f db/migration_v2.sql

BEGIN;

-- ============================================================
-- 1. New columns on sku_metrics
-- ============================================================
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS abc_class TEXT;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS xyz_class TEXT;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS demand_cv NUMERIC;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS total_revenue NUMERIC DEFAULT 0;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS wma_wholesale_velocity NUMERIC DEFAULT 0;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS wma_online_velocity NUMERIC DEFAULT 0;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS wma_total_velocity NUMERIC DEFAULT 0;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS trend_direction TEXT DEFAULT 'flat';
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS trend_ratio NUMERIC;
ALTER TABLE sku_metrics ADD COLUMN IF NOT EXISTS safety_buffer NUMERIC DEFAULT 1.3;

CREATE INDEX IF NOT EXISTS idx_sku_metrics_abc ON sku_metrics(abc_class);
CREATE INDEX IF NOT EXISTS idx_sku_metrics_trend ON sku_metrics(trend_direction);

-- ============================================================
-- 2. New columns on brand_metrics
-- ============================================================
ALTER TABLE brand_metrics ADD COLUMN IF NOT EXISTS a_class_skus INTEGER DEFAULT 0;
ALTER TABLE brand_metrics ADD COLUMN IF NOT EXISTS b_class_skus INTEGER DEFAULT 0;
ALTER TABLE brand_metrics ADD COLUMN IF NOT EXISTS c_class_skus INTEGER DEFAULT 0;
ALTER TABLE brand_metrics ADD COLUMN IF NOT EXISTS inactive_skus INTEGER DEFAULT 0;

-- ============================================================
-- 3. New app_settings for ABC/XYZ thresholds and safety buffers
-- ============================================================
INSERT INTO app_settings (key, value) VALUES ('abc_a_threshold', '0.80') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('abc_b_threshold', '0.95') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_ax', '1.5') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_ay', '1.6') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_az', '1.8') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_bx', '1.3') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_by', '1.4') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_bz', '1.5') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_cx', '1.1') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_cy', '1.2') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_cz', '1.3') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('wma_window_days', '90') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('trend_up_threshold', '1.2') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('trend_down_threshold', '0.8') ON CONFLICT DO NOTHING;

-- ============================================================
-- 4. Mark inactive SKUs (zero opening + zero closing + no transactions)
-- ============================================================
UPDATE stock_items SET is_active = FALSE
WHERE opening_balance = 0 AND closing_balance = 0
  AND tally_name NOT IN (SELECT DISTINCT stock_item_name FROM transactions);

COMMIT;
