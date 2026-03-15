-- Add buffer_override column to suppliers table
-- Allows per-supplier safety buffer override (default is global 1.3x)

ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS buffer_override NUMERIC;
