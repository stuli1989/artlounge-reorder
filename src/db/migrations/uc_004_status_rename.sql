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

-- 2. Update sku_metrics.reorder_status values
UPDATE sku_metrics SET reorder_status = CASE reorder_status
  WHEN 'stocked_out' THEN 'lost_sales'
  WHEN 'critical' THEN 'urgent'
  WHEN 'warning' THEN 'reorder'
  WHEN 'ok' THEN 'healthy'
  WHEN 'no_demand' THEN 'dead_stock'
  ELSE reorder_status
END
WHERE reorder_status IN ('stocked_out', 'critical', 'warning', 'ok', 'no_demand');
