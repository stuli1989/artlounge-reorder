# 06 — Nightly Sync Job

## Overview

A Python script that runs automatically every night. It:
1. Connects to Tally's HTTP server
2. Pulls updated master data (stock items, categories)
3. Pulls new/changed transaction data (vouchers)
4. Loads everything into PostgreSQL
5. Detects new unclassified parties
6. Triggers the computation pipeline
7. Logs results

## Schedule

- **When:** Every night at 2:00 AM IST
- **Why 2 AM:** No one is using Tally at this hour. The sync puts load on Tally's HTTP server.
- **Duration:** Estimated 5-30 minutes depending on data volume
- **Where it runs:** On the AWS Windows machine (same machine as Tally). The agent reads from Tally at localhost:9000, does all computation locally, and writes results to Railway's managed Postgres over SSL. The agent DOES NOT run on Railway — it must run on a machine that can reach Tally.

## Sync Strategy

### First Run (Full Sync)

The very first execution pulls EVERYTHING:
- All stock categories
- All stock items
- All ledgers (for party list)
- All inventory vouchers for the current financial year (Apr 1, 2025 to today)

This may take 30-60 minutes depending on data volume.

### Subsequent Runs (Delta Sync)

After the first run, we only pull changes:

**Master data:** Always do a full refresh of stock categories and stock items. These are small (a few thousand rows) and fast. Items may be added, renamed, or recategorized.

**Transaction data:** Only pull vouchers with dates since the last sync, plus a 7-day overlap buffer.

```python
def get_sync_date_range(db_conn) -> tuple:
    """
    Determine date range for transaction sync.
    
    Returns (from_date, to_date) as strings in YYYYMMDD format.
    """
    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT MAX(txn_to_date) FROM sync_log 
        WHERE status = 'completed'
    """)
    last_sync_end = cursor.fetchone()[0]
    
    if last_sync_end is None:
        # First run — pull entire financial year
        return ("20250401", date.today().strftime("%Y%m%d"))
    
    # Delta: from 7 days before last sync end (overlap for late entries)
    # to today
    overlap_start = last_sync_end - timedelta(days=7)
    return (overlap_start.strftime("%Y%m%d"), date.today().strftime("%Y%m%d"))
```

**Why the 7-day overlap?** Vouchers can be backdated — someone might enter a July 15 sale on July 18. If our last sync covered up to July 15, we'd miss it. The overlap ensures we catch backdated entries. The UNIQUE constraint on the transactions table prevents duplicates.

## Main Sync Script

```python
# sync/nightly_sync.py

"""
Nightly sync job: Pull data from Tally → Load into PostgreSQL → Compute metrics.

Usage:
    python nightly_sync.py              # Normal nightly run
    python nightly_sync.py --full       # Force full re-sync
    python nightly_sync.py --dry-run    # Pull data but don't load
"""

import argparse
import sys
from datetime import datetime, date, timedelta

from extraction.tally_client import TallyClient
from extraction.xml_requests import *
from extraction.xml_parser import *
from engine.stock_position import reconstruct_daily_positions
from engine.velocity import calculate_velocity
from engine.reorder import determine_reorder_status
from engine.aggregation import compute_brand_metrics
from config.settings import TALLY_HOST, TALLY_PORT, DB_CONNECTION_STRING


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='Force full re-sync')
    parser.add_argument('--dry-run', action='store_true', help='Pull but dont load')
    args = parser.parse_args()
    
    # Initialize
    tally = TallyClient(host=TALLY_HOST, port=TALLY_PORT)
    db_conn = get_db_connection(DB_CONNECTION_STRING)
    
    sync_id = create_sync_log(db_conn, status='running')
    
    try:
        # Step 1: Test Tally connection
        print(f"[{timestamp()}] Connecting to Tally at {TALLY_HOST}:{TALLY_PORT}...")
        if not tally.test_connection():
            raise ConnectionError("Cannot reach Tally. Is it running?")
        print(f"[{timestamp()}] Connected.")
        
        # Step 2: Sync stock categories
        print(f"[{timestamp()}] Syncing stock categories...")
        categories = sync_stock_categories(tally, db_conn)
        print(f"[{timestamp()}] Synced {len(categories)} categories.")
        
        # Step 3: Sync stock items
        print(f"[{timestamp()}] Syncing stock items...")
        items = sync_stock_items(tally, db_conn)
        print(f"[{timestamp()}] Synced {len(items)} stock items.")
        
        # Step 4: Sync transactions
        from_date, to_date = get_sync_date_range(db_conn) if not args.full else ("20250401", date.today().strftime("%Y%m%d"))
        print(f"[{timestamp()}] Syncing transactions from {from_date} to {to_date}...")
        txn_count = sync_transactions(tally, db_conn, from_date, to_date)
        print(f"[{timestamp()}] Synced {txn_count} transactions.")
        
        # Step 5: Check for new parties
        new_parties = check_new_parties(db_conn)
        if new_parties:
            print(f"[{timestamp()}] WARNING: {len(new_parties)} new unclassified parties:")
            for p in new_parties:
                print(f"  - {p}")
        
        # Step 6: Run computation pipeline
        if not args.dry_run:
            print(f"[{timestamp()}] Running computation pipeline...")
            run_computation_pipeline(db_conn)
            print(f"[{timestamp()}] Computation complete.")
        
        # Step 7: Update sync log
        update_sync_log(db_conn, sync_id, 
                       status='completed',
                       categories_synced=len(categories),
                       items_synced=len(items),
                       transactions_synced=txn_count,
                       new_parties_found=len(new_parties),
                       txn_from_date=from_date,
                       txn_to_date=to_date)
        
        print(f"[{timestamp()}] Nightly sync completed successfully.")
        
    except Exception as e:
        print(f"[{timestamp()}] SYNC FAILED: {e}")
        update_sync_log(db_conn, sync_id, 
                       status='failed', 
                       error_message=str(e))
        sys.exit(1)
    
    finally:
        db_conn.close()
```

## Transaction Sync Detail

The transaction sync is the most complex part. Tally's Day Book response can be very large, so we batch by month:

```python
def sync_transactions(tally: TallyClient, 
                      db_conn, 
                      from_date: str, 
                      to_date: str) -> int:
    """
    Pull inventory vouchers from Tally and load into database.
    Batches by month to avoid timeout/memory issues.
    """
    total_synced = 0
    
    # Generate monthly date ranges
    for month_start, month_end in generate_monthly_ranges(from_date, to_date):
        print(f"  Pulling {month_start} to {month_end}...")
        
        try:
            xml_request = inventory_vouchers_request(month_start, month_end)
            raw_response = tally.send_request_raw(xml_request, timeout=600)
            
            # Parse vouchers from XML
            voucher_records = parse_vouchers(raw_response)
            
            # Enrich with channel classification
            for record in voucher_records:
                record['channel'] = lookup_party_channel(db_conn, record['party'])
            
            # Upsert into database (UNIQUE constraint handles dedup)
            inserted = upsert_transactions(db_conn, voucher_records)
            total_synced += inserted
            
            print(f"  → {len(voucher_records)} parsed, {inserted} new/updated")
            
        except Exception as e:
            print(f"  → ERROR for {month_start}-{month_end}: {e}")
            # Continue with next month — don't fail the entire sync
            continue
    
    return total_synced


def generate_monthly_ranges(from_date: str, to_date: str) -> list:
    """Generate (start, end) tuples for each month in the range."""
    from datetime import datetime
    import calendar
    
    start = datetime.strptime(from_date, "%Y%m%d").date()
    end = datetime.strptime(to_date, "%Y%m%d").date()
    
    ranges = []
    current = start
    
    while current <= end:
        month_end_day = calendar.monthrange(current.year, current.month)[1]
        month_end = current.replace(day=month_end_day)
        
        if month_end > end:
            month_end = end
        
        ranges.append((
            current.strftime("%Y%m%d"),
            month_end.strftime("%Y%m%d")
        ))
        
        # Move to first day of next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)
    
    return ranges
```

## Scheduling

The sync agent runs on the AWS Windows box via Task Scheduler:

### Windows Task Scheduler Setup
1. Open Task Scheduler
2. Create Basic Task → "Art Lounge Nightly Sync"
3. Trigger: Daily at 2:00 AM
4. Action: Start a Program
   - Program: `C:\artlounge-sync\venv\Scripts\python.exe`
   - Arguments: `sync\nightly_sync.py`
   - Start in: `C:\artlounge-sync`
5. Under Conditions: uncheck "Start only if computer is on AC power"
6. Under Settings: check "Run task as soon as possible after a scheduled start is missed"

## Error Handling

| Error | Recovery |
|-------|----------|
| Tally not reachable | Log error, send alert, retry next night. Dashboard shows stale data with warning. |
| Single month fails | Skip that month, continue with others. Log partial sync. |
| Database connection fails | Abort entire sync, log error, send alert. |
| XML parsing error | Save raw XML to disk for debugging, skip affected records, continue. |
| New unclassified parties | Sync completes but dashboard shows warning banner. Velocities may be slightly off until classified. |

## Monitoring

The sync_log table provides audit trail. The dashboard should show:
- Last successful sync time
- "Data freshness" indicator (green if < 24h, amber if 24-48h, red if > 48h)
- Count of unclassified parties (if any)
