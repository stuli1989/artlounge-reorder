#!/bin/bash
set -e

echo "=== STARTUP (MODE=${MODE:-web}) ==="

# If MODE=sync, just run the nightly sync and exit
if [ "$MODE" = "sync" ]; then
    echo "Running nightly ledger sync..."
    PYTHONPATH=. python -m unicommerce.ledger_sync
    echo "Sync complete. Exiting."
    exit 0
fi

# Step 1: Run schema migrations if needed
PYTHONPATH=. python -c "
from extraction.data_loader import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

# Check if channel_rules exists (indicates uc_002 was applied)
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='channel_rules')\")
has_schema = cur.fetchone()[0]

if not has_schema:
    print('Running schema migrations...')
    with open('db/migrations/uc_001_schema.sql') as f:
        cur.execute(f.read())
    conn.commit()
    with open('db/migrations/uc_002_ledger_rebuild.sql') as f:
        cur.execute(f.read())
    conn.commit()
    print('Migrations complete.')
else:
    print('Schema up to date.')

cur.execute('SELECT COUNT(*) FROM transactions')
print(f'Transactions in DB: {cur.fetchone()[0]}')
conn.close()
"

# Step 2: Run backfill if DB is empty (first deploy only)
TXNS=$(PYTHONPATH=. python -c "
from extraction.data_loader import get_db_connection
c = get_db_connection()
cur = c.cursor()
cur.execute('SELECT COUNT(*) FROM transactions')
print(cur.fetchone()[0])
c.close()
")

if [ "$TXNS" = "0" ]; then
    echo "Empty DB — running initial backfill (this takes ~10 minutes)..."
    PYTHONPATH=. python -m unicommerce.ledger_sync --backfill
    echo "Backfill complete."
else
    echo "DB has $TXNS transactions."
    # Check if positions need rebuilding (e.g., after a fix)
    POSITIONS=$(PYTHONPATH=. python -c "
from extraction.data_loader import get_db_connection
c = get_db_connection()
cur = c.cursor()
cur.execute('SELECT COUNT(*) FROM daily_stock_positions')
print(cur.fetchone()[0])
c.close()
")
    if [ "$POSITIONS" = "0" ]; then
        echo "Positions empty — rebuilding pipeline..."
        PYTHONPATH=. python -c "
from extraction.data_loader import get_db_connection
from engine.pipeline import run_computation_pipeline
db_conn = get_db_connection()
run_computation_pipeline(db_conn)
db_conn.close()
"
        echo "Pipeline rebuild complete."
    else
        echo "Positions: $POSITIONS rows — skipping rebuild."
    fi
fi

# Step 3: Start the app
echo "Starting API server..."
exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
