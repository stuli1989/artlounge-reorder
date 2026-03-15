-- Ensure brand_metrics integer count columns are never NULL

UPDATE brand_metrics SET total_skus = 0 WHERE total_skus IS NULL;
UPDATE brand_metrics SET in_stock_skus = 0 WHERE in_stock_skus IS NULL;
UPDATE brand_metrics SET critical_skus = 0 WHERE critical_skus IS NULL;
UPDATE brand_metrics SET warning_skus = 0 WHERE warning_skus IS NULL;
UPDATE brand_metrics SET ok_skus = 0 WHERE ok_skus IS NULL;
UPDATE brand_metrics SET out_of_stock_skus = 0 WHERE out_of_stock_skus IS NULL;
UPDATE brand_metrics SET no_data_skus = 0 WHERE no_data_skus IS NULL;

ALTER TABLE brand_metrics ALTER COLUMN total_skus SET NOT NULL;
ALTER TABLE brand_metrics ALTER COLUMN total_skus SET DEFAULT 0;
ALTER TABLE brand_metrics ALTER COLUMN in_stock_skus SET NOT NULL;
ALTER TABLE brand_metrics ALTER COLUMN in_stock_skus SET DEFAULT 0;
ALTER TABLE brand_metrics ALTER COLUMN critical_skus SET NOT NULL;
ALTER TABLE brand_metrics ALTER COLUMN critical_skus SET DEFAULT 0;
ALTER TABLE brand_metrics ALTER COLUMN warning_skus SET NOT NULL;
ALTER TABLE brand_metrics ALTER COLUMN warning_skus SET DEFAULT 0;
ALTER TABLE brand_metrics ALTER COLUMN ok_skus SET NOT NULL;
ALTER TABLE brand_metrics ALTER COLUMN ok_skus SET DEFAULT 0;
ALTER TABLE brand_metrics ALTER COLUMN out_of_stock_skus SET NOT NULL;
ALTER TABLE brand_metrics ALTER COLUMN out_of_stock_skus SET DEFAULT 0;
ALTER TABLE brand_metrics ALTER COLUMN no_data_skus SET NOT NULL;
ALTER TABLE brand_metrics ALTER COLUMN no_data_skus SET DEFAULT 0;
