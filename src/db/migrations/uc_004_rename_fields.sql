-- Migration: Rename stock_item_name → item_code, part_no → display_name
--
-- Unicommerce semantics:
--   skuCode (e.g. "0102004") was stored as stock_items.name / *.stock_item_name
--   name (e.g. "WN PWC 5ML ALIZ CRIMSON") was stored as stock_items.part_no
--
-- After this migration:
--   item_code = the SKU code (Unicommerce skuCode)
--   display_name = the human-readable product name (Unicommerce name)
--
-- PostgreSQL RENAME COLUMN is metadata-only (instant, no data rewrite).
-- Indexes, unique constraints, and CHECK constraints update automatically.

BEGIN;

-- 1. stock_items: rename PK column and display column
ALTER TABLE stock_items RENAME COLUMN name TO item_code;
ALTER TABLE stock_items RENAME COLUMN part_no TO display_name;

-- 2. sku_metrics
ALTER TABLE sku_metrics RENAME COLUMN stock_item_name TO item_code;

-- 3. transactions
ALTER TABLE transactions RENAME COLUMN stock_item_name TO item_code;

-- 4. daily_stock_positions
ALTER TABLE daily_stock_positions RENAME COLUMN stock_item_name TO item_code;

-- 5. overrides
ALTER TABLE overrides RENAME COLUMN stock_item_name TO item_code;

-- 6. drift_log
ALTER TABLE drift_log RENAME COLUMN stock_item_name TO item_code;

-- 7. inventory_snapshots
ALTER TABLE inventory_snapshots RENAME COLUMN stock_item_name TO item_code;

-- 8. kg_demand
ALTER TABLE kg_demand RENAME COLUMN stock_item_name TO item_code;

COMMIT;
