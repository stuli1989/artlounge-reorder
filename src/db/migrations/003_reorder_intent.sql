-- Migration 003: Reorder Intent Classification + Slow Movers
BEGIN;

ALTER TABLE stock_items
    ADD COLUMN IF NOT EXISTS reorder_intent TEXT DEFAULT 'normal';

DO $$ BEGIN
    ALTER TABLE stock_items ADD CONSTRAINT valid_reorder_intent
        CHECK (reorder_intent IN ('must_stock', 'normal', 'do_not_reorder'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_stock_items_intent ON stock_items(reorder_intent);

ALTER TABLE brand_metrics
    ADD COLUMN IF NOT EXISTS slow_mover_skus INTEGER DEFAULT 0;

INSERT INTO app_settings (key, value) VALUES ('slow_mover_velocity_threshold', '0.1')
    ON CONFLICT DO NOTHING;

COMMIT;
