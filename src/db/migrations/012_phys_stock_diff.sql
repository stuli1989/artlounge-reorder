-- Add phys_stock_diff column to transactions table.
-- For Physical Stock vouchers, this stores the actual stock adjustment
-- from Tally's BATCHPHYSDIFF field (not the physical count).
-- NULL for non-Physical Stock vouchers.

ALTER TABLE transactions ADD COLUMN IF NOT EXISTS phys_stock_diff NUMERIC;
