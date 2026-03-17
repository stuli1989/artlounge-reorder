-- Make voucher_number NOT NULL and replace expression-based unique index
-- with a plain unique constraint so ON CONFLICT works reliably.
--
-- Prerequisite: no NULL voucher_number rows exist (verified 2026-03-17).

BEGIN;

-- 1. Backfill any NULLs (defensive — none exist today)
UPDATE transactions SET voucher_number = '' WHERE voucher_number IS NULL;

-- 2. Make column NOT NULL with a default
ALTER TABLE transactions ALTER COLUMN voucher_number SET DEFAULT '';
ALTER TABLE transactions ALTER COLUMN voucher_number SET NOT NULL;

-- 3. Drop the expression-based unique index (cannot be used by ON CONFLICT)
DROP INDEX IF EXISTS uq_transactions_dedup;

-- 4. Create a plain unique constraint on the raw columns
ALTER TABLE transactions
    ADD CONSTRAINT uq_transactions_dedup
    UNIQUE (txn_date, voucher_number, stock_item_name, quantity, is_inward, rate);

COMMIT;
