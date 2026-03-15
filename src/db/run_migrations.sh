#!/bin/bash
# Run all migrations in order against the local database
# Usage: bash src/db/run_migrations.sh

PSQL="/c/Program Files/PostgreSQL/17/bin/psql"
DB="artlounge_reorder"
USER="reorder_app"
export PGPASSWORD=password

echo "Running migrations against $DB..."

# Base schema (idempotent)
"$PSQL" -U "$USER" -d "$DB" -f src/db/schema.sql 2>&1 | grep -v "already exists"

# V2 migrations
"$PSQL" -U "$USER" -d "$DB" -f src/db/migration_v2.sql 2>&1 | grep -v "already exists"

# Numbered migrations in order
for f in src/db/migrations/001_overrides.sql \
         src/db/migrations/002_dead_stock.sql \
         src/db/migrations/003_reorder_intent.sql \
         src/db/migrations/004_bigserial_dsp.sql \
         src/db/migrations/005_supplier_buffer_override.sql \
         src/db/migrations/006_check_constraints.sql \
         src/db/migrations/007_fix_txn_unique.sql \
         src/db/migrations/008_brand_metrics_not_null.sql \
         src/db/migrations/009_drop_redundant_indexes.sql; do
    echo "  Running $(basename $f)..."
    "$PSQL" -U "$USER" -d "$DB" -f "$f" 2>&1 | grep -v "already exists"
done

# V3+ migrations
"$PSQL" -U "$USER" -d "$DB" -f src/db/migration_v3_xyz_toggle.sql 2>&1 | grep -v "already exists"
"$PSQL" -U "$USER" -d "$DB" -f src/db/migration_v4_trgm.sql 2>&1 | grep -v "already exists"
"$PSQL" -U "$USER" -d "$DB" -f src/db/migration_v4_settings_defaults.sql 2>&1 | grep -v "already exists"

echo "All migrations complete."
