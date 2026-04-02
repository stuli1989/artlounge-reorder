#!/bin/bash
# sync-from-railway.sh — Sync Railway DB to local PostgreSQL
# Usage: ./sync-from-railway.sh [--exclude-positions]
#
# Requires PG18 client tools for Railway (v18 server) and PG17 for local restore.

set -euo pipefail

# ── PG Binaries ──
PG18_BIN="/c/Users/Kshitij Shah/pg18/pgsql/bin"  # v18 client for Railway
PG17_BIN="/c/Program Files/PostgreSQL/17/bin"      # v17 for local server

# ── Railway DB ──
RAILWAY_HOST="switchyard.proxy.rlwy.net"
RAILWAY_PORT="21840"
RAILWAY_USER="postgres"
RAILWAY_PASS="vASLgwlzeBzWIKCneufLWxQScFUJFjWE"
RAILWAY_DB="railway"

# ── Local DB ──
LOCAL_USER="reorder_app"
LOCAL_PASS="password"
LOCAL_DB="artlounge_reorder_uc"

DUMP_FILE="railway_to_local.dump"
EXCLUDE_POSITIONS=false

# Parse args
for arg in "$@"; do
  case $arg in
    --exclude-positions) EXCLUDE_POSITIONS=true ;;
  esac
done

echo "=== Syncing Railway → Local ==="

# Step 1: pg_dump from Railway (using v18 client)
EXCLUDE_ARGS=""
if [ "$EXCLUDE_POSITIONS" = true ]; then
  EXCLUDE_ARGS="--exclude-table=daily_stock_positions"
  echo "Excluding daily_stock_positions (use sync-positions-chunked.sh separately)"
fi

echo "Step 1: Dumping Railway DB..."
PGPASSWORD=$RAILWAY_PASS "$PG18_BIN/pg_dump" \
  -h $RAILWAY_HOST -p $RAILWAY_PORT -U $RAILWAY_USER -d $RAILWAY_DB \
  --no-owner --no-privileges --clean --if-exists \
  $EXCLUDE_ARGS \
  -Fc -f "$DUMP_FILE"

DUMP_SIZE=$(ls -lh "$DUMP_FILE" | awk '{print $5}')
echo "  Dump: $DUMP_SIZE"

# Step 2: Restore to local (using v17 pg_restore)
echo "Step 2: Restoring to local DB..."
PGPASSWORD=$LOCAL_PASS "$PG17_BIN/pg_restore" \
  -U $LOCAL_USER -d $LOCAL_DB \
  --no-owner --no-privileges --clean --if-exists \
  "$DUMP_FILE" 2>&1 || true  # pg_restore returns non-zero on warnings

# Step 3: Verify
echo ""
echo "Step 3: Verifying..."
PGPASSWORD=$LOCAL_PASS "$PG17_BIN/psql" -U $LOCAL_USER -d $LOCAL_DB -c "
SELECT 'stock_items' AS tbl, COUNT(*) AS cnt FROM stock_items
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL SELECT 'sku_metrics', COUNT(*) FROM sku_metrics
UNION ALL SELECT 'brand_metrics', COUNT(*) FROM brand_metrics
UNION ALL SELECT 'inventory_snapshots', COUNT(*) FROM inventory_snapshots
UNION ALL SELECT 'daily_stock_positions', COUNT(*) FROM daily_stock_positions
ORDER BY tbl;
"

# Cleanup
rm -f "$DUMP_FILE"
echo "=== SYNC COMPLETE ==="
