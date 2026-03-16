-- migration_v5_manual_party.sql
-- Add is_manual flag to parties so manual UI reclassifications survive nightly auto-classify

ALTER TABLE parties ADD COLUMN IF NOT EXISTS is_manual BOOLEAN DEFAULT FALSE;
