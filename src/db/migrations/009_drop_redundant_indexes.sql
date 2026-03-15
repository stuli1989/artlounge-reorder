-- Drop redundant indexes on daily_stock_positions
-- idx_dsp_item_date_desc: 731 MB, 0 scans - completely unused
DROP INDEX IF EXISTS idx_dsp_item_date_desc;
-- idx_daily_pos_item: 121 MB, 50 scans - subsumed by composite unique index
DROP INDEX IF EXISTS idx_daily_pos_item;
-- idx_stock_items_name: duplicate of unique constraint index stock_items_tally_name_key
DROP INDEX IF EXISTS idx_stock_items_name;
-- idx_stock_categories_name: duplicate of unique constraint index
DROP INDEX IF EXISTS idx_stock_categories_name;
