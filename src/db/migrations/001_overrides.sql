-- Manual overrides for SKU metrics (stock, velocity, notes)
-- Override Layer pattern: sync always writes computed values to sku_metrics,
-- API reads apply COALESCE(override, computed) at query time.

CREATE TABLE IF NOT EXISTS overrides (
    id SERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL REFERENCES stock_items(tally_name),
    field_name TEXT NOT NULL CHECK (field_name IN (
        'current_stock', 'total_velocity',
        'wholesale_velocity', 'online_velocity', 'store_velocity',
        'note'
    )),
    override_value NUMERIC,  -- NULL for note-only entries
    note TEXT NOT NULL,       -- mandatory reason
    hold_from_po BOOLEAN NOT NULL DEFAULT FALSE,
    created_by TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,  -- optional auto-expiry

    -- Active/deactive state
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deactivated_at TIMESTAMPTZ,
    deactivated_reason TEXT,

    -- Staleness detection
    computed_value_at_creation NUMERIC,  -- snapshot when override was created
    computed_value_latest NUMERIC,       -- updated by nightly sync
    drift_pct NUMERIC,
    is_stale BOOLEAN NOT NULL DEFAULT FALSE,
    stale_since TIMESTAMPTZ,
    last_reviewed_at TIMESTAMPTZ
);

-- Only one active override per field per SKU
CREATE UNIQUE INDEX IF NOT EXISTS idx_overrides_active_unique
    ON overrides (stock_item_name, field_name) WHERE is_active = TRUE;

-- Fast lookups for override-aware queries
CREATE INDEX IF NOT EXISTS idx_overrides_active_item
    ON overrides (stock_item_name) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_overrides_stale
    ON overrides (is_stale) WHERE is_active = TRUE AND is_stale = TRUE;


-- Append-only audit log for all override actions
CREATE TABLE IF NOT EXISTS override_audit_log (
    id SERIAL PRIMARY KEY,
    override_id INTEGER NOT NULL REFERENCES overrides(id),
    action TEXT NOT NULL CHECK (action IN (
        'created', 'deactivated', 'flagged_stale',
        'reviewed_keep', 'reviewed_remove', 'auto_expired'
    )),
    old_values JSONB,
    new_values JSONB,
    performed_by TEXT NOT NULL DEFAULT 'user',
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_override_id ON override_audit_log(override_id);
