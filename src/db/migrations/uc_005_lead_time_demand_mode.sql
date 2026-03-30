-- uc_005_lead_time_demand_mode.sql
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS lead_time_demand_mode TEXT NOT NULL DEFAULT 'full';
