-- uc_004_status_rename.sql
-- Rename reorder status values and brand_metrics columns for clarity.
-- NOTE: no_demand_skus is NOT renamed — dead_stock_skus already exists (F19 metric).

-- 1. Rename brand_metrics columns (4 of 5 — no_demand_skus stays)
DO $$ BEGIN
  ALTER TABLE brand_metrics RENAME COLUMN critical_skus TO urgent_skus;
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE brand_metrics RENAME COLUMN warning_skus TO reorder_skus;
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE brand_metrics RENAME COLUMN ok_skus TO healthy_skus;
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE brand_metrics RENAME COLUMN stocked_out_skus TO lost_sales_skus;
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

-- 1b. Ensure columns exist (may not have been in original schema)
ALTER TABLE brand_metrics ADD COLUMN IF NOT EXISTS lost_sales_skus INTEGER NOT NULL DEFAULT 0;
ALTER TABLE brand_metrics ADD COLUMN IF NOT EXISTS no_demand_skus INTEGER NOT NULL DEFAULT 0;

-- 2. Drop old CHECK constraint (must happen before value update)
ALTER TABLE sku_metrics DROP CONSTRAINT IF EXISTS valid_reorder_status;

-- 3. Update sku_metrics.reorder_status values
UPDATE sku_metrics SET reorder_status = CASE reorder_status
  WHEN 'stocked_out' THEN 'lost_sales'
  WHEN 'critical' THEN 'urgent'
  WHEN 'warning' THEN 'reorder'
  WHEN 'ok' THEN 'healthy'
  WHEN 'no_demand' THEN 'dead_stock'
  ELSE reorder_status
END
WHERE reorder_status IN ('stocked_out', 'critical', 'warning', 'ok', 'no_demand');

-- 4. Add new CHECK constraint with updated values
ALTER TABLE sku_metrics ADD CONSTRAINT valid_reorder_status
  CHECK (reorder_status IN ('urgent', 'reorder', 'healthy', 'out_of_stock', 'lost_sales', 'dead_stock', 'no_data'));

-- Seed ABC-only buffer keys if missing
INSERT INTO app_settings (key, value) VALUES ('buffer_a', '1.3') ON CONFLICT (key) DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_b', '1.2') ON CONFLICT (key) DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_c', '1.1') ON CONFLICT (key) DO NOTHING;
