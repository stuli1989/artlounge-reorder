-- Run as superuser (postgres):
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Run as reorder_app:
CREATE INDEX IF NOT EXISTS idx_stock_items_tally_name_trgm
  ON stock_items USING gin (tally_name gin_trgm_ops);
