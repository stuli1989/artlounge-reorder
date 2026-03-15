-- Fix integer overflow risk on daily_stock_positions.id
-- Sequence is at 52.8M, consuming ~8.8M per sync. SERIAL (int4) maxes at 2.1B.
-- Upgrade to bigint (max 9.2 quintillion) to prevent overflow.

ALTER TABLE daily_stock_positions ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE daily_stock_positions_id_seq AS bigint;
