BEGIN;

-- Analysis defaults (consumed by SkuDetail, CriticalSkus, DeadStock pages)
INSERT INTO app_settings (key, value) VALUES ('default_velocity_type', 'flat') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('default_date_range', 'full_fy') ON CONFLICT DO NOTHING;

COMMIT;
