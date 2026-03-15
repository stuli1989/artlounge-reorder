-- Add CHECK constraints for data integrity

-- transactions.channel
DO $$ BEGIN
    ALTER TABLE transactions ADD CONSTRAINT valid_txn_channel
        CHECK (channel IN ('supplier', 'wholesale', 'online', 'store', 'internal', 'ignore', 'unclassified'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- sync_log.status
DO $$ BEGIN
    ALTER TABLE sync_log ADD CONSTRAINT valid_sync_status
        CHECK (status IN ('running', 'completed', 'failed'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- sku_metrics.trend_direction
ALTER TABLE sku_metrics DROP CONSTRAINT IF EXISTS valid_trend_direction;
ALTER TABLE sku_metrics ADD CONSTRAINT valid_trend_direction
    CHECK (trend_direction IN ('up', 'down', 'flat'));

-- sku_metrics.abc_class
ALTER TABLE sku_metrics DROP CONSTRAINT IF EXISTS valid_abc_class;
ALTER TABLE sku_metrics ADD CONSTRAINT valid_abc_class
    CHECK (abc_class IN ('A', 'B', 'C') OR abc_class IS NULL);

-- sku_metrics.xyz_class
ALTER TABLE sku_metrics DROP CONSTRAINT IF EXISTS valid_xyz_class;
ALTER TABLE sku_metrics ADD CONSTRAINT valid_xyz_class
    CHECK (xyz_class IN ('X', 'Y', 'Z') OR xyz_class IS NULL);
