# src/unicommerce/ledger_sync.py
"""
Nightly sync orchestrator — pulls transaction ledger via Export Job API,
parses, loads into transactions table, runs pipeline.

Usage:
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --backfill
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_sync --dry-run
"""
import argparse
import logging
import os
import glob
from datetime import datetime, timedelta, date

import psycopg2.extras

from unicommerce.client import UnicommerceClient
from unicommerce.ledger_parser import parse_ledger_csv, parse_ledger_file, classify_channel
from unicommerce.catalog import pull_all_skus, load_catalog
from engine.pipeline import run_computation_pipeline
from extraction.data_loader import get_db_connection
from config.settings import UC_FACILITIES_FALLBACK

logger = logging.getLogger(__name__)

OVERLAP_DAYS = 3
BACKFILL_WINDOW_DAYS = 90  # Export Job API max is 92


def _fetch_channel_rules(db_conn):
    """Load active channel rules from DB, sorted by priority DESC."""
    with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT rule_type, match_value, facility_filter, channel, priority
            FROM channel_rules WHERE is_active = TRUE
            ORDER BY priority DESC
        """)
        return cur.fetchall()


def _load_transactions(db_conn, parsed_rows, rules):
    """Classify channels and upsert parsed rows into transactions table."""
    if not parsed_rows:
        return 0

    for row in parsed_rows:
        row["channel"] = classify_channel(row, rules)

    sql = """
        INSERT INTO transactions
            (stock_item_name, txn_date, entity, entity_type, entity_code,
             txn_type, units, stock_change, facility, channel, is_demand, sale_order_code)
        VALUES
            (%(sku_code)s, %(txn_date)s, %(entity)s, %(entity_type)s, %(entity_code)s,
             %(txn_type)s, %(units)s, %(stock_change)s, %(facility)s, %(channel)s,
             %(is_demand)s, %(sale_order_code)s)
        ON CONFLICT (entity_code, stock_item_name, txn_type, txn_date, units, facility)
        DO NOTHING
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, parsed_rows, page_size=1000)
    db_conn.commit()
    return len(parsed_rows)


def pull_ledger_for_facility(client, facility, start_date, end_date):
    """Pull transaction ledger CSV for one facility via Export Job API.

    Returns parsed rows list, or empty list on failure.
    """
    try:
        job_code = client.create_export_job(facility, start_date, end_date)
        status, file_path = client.poll_export_job(job_code, facility=facility, timeout=300)

        if status != "COMPLETE" or not file_path:
            logger.error("Export job %s for %s: status=%s", job_code, facility, status)
            return []

        csv_text = client.download_export_csv(file_path)
        rows = parse_ledger_csv(csv_text)
        logger.info("Facility %s: %d rows parsed", facility, len(rows))
        return rows

    except Exception as e:
        logger.error("Failed to pull ledger for %s: %s", facility, e)
        return []


def _send_sync_email(total_loaded, facilities_ok, total_facilities, error=None):
    """Send email notification on sync completion."""
    from config.settings import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL
    if not SMTP_HOST or not NOTIFY_EMAIL:
        return

    import smtplib
    from email.mime.text import MIMEText

    status = "SUCCESS" if not error else "FAILED"
    subject = f"Ledger Sync {status} - {date.today()}"
    body = f"Ledger sync {status}\n\nRows loaded: {total_loaded}\nFacilities: {facilities_ok}/{total_facilities}\n"
    if error:
        body += f"\nError: {error}\n"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_EMAIL

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [NOTIFY_EMAIL], msg.as_string())
        logger.info("Sync notification email sent to %s", NOTIFY_EMAIL)
    except Exception as e:
        logger.warning("Failed to send sync email: %s", e)


def run_nightly_sync(db_conn, days_back=OVERLAP_DAYS, dry_run=False):
    """Main nightly sync: pull ledger, load transactions, run pipeline."""
    print("=== NIGHTLY LEDGER SYNC ===")

    client = UnicommerceClient()
    client.authenticate()
    client.discover_facilities()

    # 1. Pull catalog
    print("Step 1: Pulling catalog...")
    try:
        skus = pull_all_skus(client)
        if skus and not dry_run:
            load_catalog(db_conn, skus)
            print(f"  Catalog: {len(skus)} SKUs loaded")
    except Exception as e:
        print(f"  Catalog pull failed: {e} (continuing)")

    # 2. Pull ledger per facility
    print(f"Step 2: Pulling ledger (last {days_back} days)...")
    end_dt = datetime.now().replace(hour=23, minute=59, second=59)
    start_dt = (end_dt - timedelta(days=days_back)).replace(hour=0, minute=0, second=0)

    rules = _fetch_channel_rules(db_conn)
    total_loaded = 0
    facilities_ok = 0

    for facility in client.facilities:
        rows = pull_ledger_for_facility(client, facility, start_dt, end_dt)
        if rows:
            if not dry_run:
                loaded = _load_transactions(db_conn, rows, rules)
                total_loaded += loaded
            else:
                total_loaded += len(rows)
            facilities_ok += 1
            print(f"  {facility}: {len(rows)} rows")
        else:
            print(f"  {facility}: FAILED or empty")

    print(f"  Total: {total_loaded} rows loaded, {facilities_ok}/{len(client.facilities)} facilities OK")

    # 3. Run pipeline
    if not dry_run:
        print("Step 3: Running pipeline...")
        run_computation_pipeline(db_conn)
        print("  Pipeline complete")

    # 4. Log sync
    if not dry_run:
        with db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sync_log (source, sync_started, sync_completed, status,
                                      ledger_rows_loaded, facilities_synced)
                VALUES ('ledger', NOW() - INTERVAL '1 minute', NOW(), 'completed', %s, %s)
            """, (total_loaded, facilities_ok))
        db_conn.commit()

    # 5. Email notification
    try:
        _send_sync_email(total_loaded, facilities_ok, len(client.facilities))
    except Exception as e:
        logger.warning("Email notification failed: %s", e)

    print("=== SYNC COMPLETE ===")


def run_backfill(db_conn, from_csv_dir=None):
    """Historical backfill — either from API (92-day windows) or from CSV directory."""
    print("=== HISTORICAL BACKFILL ===")

    rules = _fetch_channel_rules(db_conn)

    if from_csv_dir:
        # Load from local CSV files
        files = sorted(glob.glob(os.path.join(from_csv_dir, "**", "*.csv"), recursive=True))
        print(f"Loading {len(files)} CSV files from {from_csv_dir}")
        total = 0
        for f in files:
            rows = parse_ledger_file(f)
            loaded = _load_transactions(db_conn, rows, rules)
            total += loaded
            print(f"  {os.path.basename(f)}: {loaded} rows")
        print(f"Total loaded: {total}")
    else:
        # Pull from API in 90-day windows
        client = UnicommerceClient()
        client.authenticate()
        client.discover_facilities()

        # Jun 1 2025 to today
        start = datetime(2025, 6, 1)
        end = datetime.now()
        total = 0

        window_start = start
        while window_start < end:
            window_end = min(window_start + timedelta(days=BACKFILL_WINDOW_DAYS), end)
            start_dt = window_start.replace(hour=0, minute=0, second=0)
            end_dt = window_end.replace(hour=23, minute=59, second=59)

            print(f"\nWindow: {start_dt.date()} to {end_dt.date()}")
            for facility in client.facilities:
                rows = pull_ledger_for_facility(client, facility, start_dt, end_dt)
                if rows:
                    loaded = _load_transactions(db_conn, rows, rules)
                    total += loaded
                    print(f"  {facility}: {loaded} rows")

            window_start = window_end + timedelta(days=1)

        print(f"\nTotal loaded: {total}")

    # Run full pipeline
    print("\nRunning full pipeline...")
    run_computation_pipeline(db_conn)
    print("=== BACKFILL COMPLETE ===")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="Ledger-based sync")
    parser.add_argument("--backfill", action="store_true", help="Run historical backfill from API")
    parser.add_argument("--backfill-csv", type=str, help="Backfill from local CSV directory")
    parser.add_argument("--dry-run", action="store_true", help="Pull data but don't write to DB")
    parser.add_argument("--days", type=int, default=OVERLAP_DAYS, help="Days to look back (default 3)")
    args = parser.parse_args()

    db_conn = get_db_connection()
    try:
        if args.backfill:
            run_backfill(db_conn)
        elif args.backfill_csv:
            run_backfill(db_conn, from_csv_dir=args.backfill_csv)
        else:
            run_nightly_sync(db_conn, days_back=args.days, dry_run=args.dry_run)
    finally:
        db_conn.close()


if __name__ == "__main__":
    main()
