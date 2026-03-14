BEGIN;
-- Global toggle (default OFF = ABC-only buffers)
INSERT INTO app_settings (key, value) VALUES ('use_xyz_buffer', 'false') ON CONFLICT DO NOTHING;

-- ABC-only buffer values
INSERT INTO app_settings (key, value) VALUES ('buffer_a', '1.5') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_b', '1.3') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('buffer_c', '1.1') ON CONFLICT DO NOTHING;

-- Per-item toggle: NULL = follow global, TRUE = force XYZ on, FALSE = force XYZ off
ALTER TABLE stock_items ADD COLUMN IF NOT EXISTS use_xyz_buffer BOOLEAN DEFAULT NULL;
COMMIT;
