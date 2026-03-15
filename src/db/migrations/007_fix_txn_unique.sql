-- Fix: PostgreSQL treats NULL != NULL in UNIQUE constraints
-- Drop old constraint and create a new one with COALESCE for voucher_number

ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_txn_date_voucher_number_stock_item_name_quanti_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_dedup
    ON transactions(txn_date, COALESCE(voucher_number, ''), stock_item_name, quantity, is_inward, rate);
