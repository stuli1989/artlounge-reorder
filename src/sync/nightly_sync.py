"""
Nightly sync job: Pull data from Tally -> Load into PostgreSQL -> Compute metrics.

Usage:
    python sync/nightly_sync.py              # Normal nightly run
    python sync/nightly_sync.py --full       # Force full re-sync (re-extract + recompute all)
    python sync/nightly_sync.py --dry-run    # Show what would happen, no DB writes
    python sync/nightly_sync.py --offline    # Use cached XML files (no Tally needed)
"""
import argparse
import sys
import traceback
from datetime import datetime, date, timedelta

from config.settings import DATABASE_URL, FY_START_DATE
from extraction.data_loader import (
    get_db_connection,
    load_all_master_data,
    load_master_data_from_files,
)
from extraction.transaction_loader import (
    sync_transactions_from_tally,
    load_transactions_from_file,
)
from extraction.party_classifier import auto_classify_all_parties, detect_new_parties
from engine.pipeline import run_computation_pipeline
from engine.override_drift import process_override_drift
from sync.sync_helpers import create_sync_log, update_sync_log, get_last_sync_end_date
from sync.email_notifier import send_sync_notification


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def run_sync(full: bool = False, dry_run: bool = False, offline: bool = False):
    """Execute the full nightly sync pipeline."""
    mode_label = "DRY RUN" if dry_run else ("FULL" if full else "normal")
    log(f"Starting nightly sync ({mode_label})...")
    db_conn = get_db_connection()

    if dry_run:
        log("DRY RUN mode — no database writes will be performed")

    sync_id = None if dry_run else create_sync_log(db_conn)
    summary = {}

    try:
        # 1. Sync master data
        if dry_run:
            log("DRY RUN — skipping master data load")
            summary["categories_synced"] = 0
            summary["items_synced"] = 0
        elif offline:
            log("Loading master data from cached XML files...")
            counts = load_master_data_from_files(db_conn)
            summary["categories_synced"] = counts["categories"]
            summary["items_synced"] = counts["items"]
            log(f"Master data: {counts['categories']} categories, {counts['items']} items")
        else:
            from extraction.tally_client import TallyClient
            tally = TallyClient()

            log("Testing Tally connection...")
            if not tally.test_connection():
                raise ConnectionError("Cannot reach Tally. Is Tally Prime running with HTTP server enabled?")
            log("Tally connection OK")

            log("Syncing master data from Tally...")
            counts = load_all_master_data(tally, db_conn)
            summary["categories_synced"] = counts["categories"]
            summary["items_synced"] = counts["items"]
            log(f"Master data: {counts['categories']} categories, {counts['items']} items")

        # 2. Auto-classify parties (skip in dry-run)
        if not dry_run:
            log("Auto-classifying parties...")
            classified = auto_classify_all_parties(db_conn)
            total_classified = sum(classified.values()) if classified else 0
            log(f"  {total_classified} parties classified")
        else:
            log("DRY RUN — skipping party classification")

        # 3. Sync transactions (skip in dry-run)
        if dry_run:
            log("DRY RUN — skipping transaction sync")
            summary["transactions_synced"] = 0
        elif offline:
            import os
            sample_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample_responses")
            xml_path = os.path.join(sample_dir, "vouchers_full_fy.xml")
            log("Loading transactions from cached XML...")
            txn_count = load_transactions_from_file(db_conn, xml_path)
            summary["transactions_synced"] = txn_count
            log(f"Transactions: {txn_count} new rows inserted")
        else:
            log("Syncing transactions from Tally...")
            txn_count = sync_transactions_from_tally(tally, db_conn)
            summary["transactions_synced"] = txn_count
            log(f"Transactions: {txn_count} new rows inserted")

        # 4. Detect new parties
        if not dry_run:
            log("Checking for new unclassified parties...")
            new_parties = detect_new_parties(db_conn)
            summary["new_parties_found"] = len(new_parties)
            if new_parties:
                log(f"  WARNING: {len(new_parties)} new unclassified parties found:")
                for p in new_parties[:10]:
                    log(f"    - {p}")
                if len(new_parties) > 10:
                    log(f"    ... and {len(new_parties) - 10} more")
            else:
                log("  No new parties")
        else:
            summary["new_parties_found"] = 0

        # 5. Run computation pipeline (skip in dry-run)
        if dry_run:
            log("DRY RUN — skipping computation pipeline")
        else:
            incremental = not full
            mode_str = "full" if full else "incremental"
            log(f"Running computation pipeline ({mode_str})...")
            run_computation_pipeline(db_conn, incremental=incremental)

            # 5b. Check override drift
            log("Checking override drift...")
            drift_result = process_override_drift(db_conn)
            log(f"  Override drift: {drift_result['overrides_checked']} checked, {drift_result['newly_stale']} newly stale, {drift_result['auto_expired']} auto-expired")

        # 6. Update sync log
        if not dry_run:
            today = date.today()
            update_sync_log(
                db_conn, sync_id,
                status="completed",
                categories_synced=summary.get("categories_synced", 0),
                items_synced=summary.get("items_synced", 0),
                transactions_synced=summary.get("transactions_synced", 0),
                new_parties_found=summary.get("new_parties_found", 0),
                txn_from_date=FY_START_DATE,
                txn_to_date=today,
            )
            send_sync_notification("completed", summary)

        log("Sync completed successfully!")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        log(f"SYNC FAILED: {error_msg}")
        traceback.print_exc()

        if sync_id:
            try:
                update_sync_log(db_conn, sync_id, status="failed", error_message=error_msg)
            except Exception:
                pass

        send_sync_notification("failed", summary, error_msg)
        sys.exit(1)

    finally:
        db_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Art Lounge nightly sync")
    parser.add_argument("--full", action="store_true", help="Force full FY re-extract and recompute (same as normal for now)")
    parser.add_argument("--dry-run", action="store_true", help="Preview sync without any DB writes")
    parser.add_argument("--offline", action="store_true",
                        help="Use cached XML files instead of live Tally")
    args = parser.parse_args()

    run_sync(full=args.full, dry_run=args.dry_run, offline=args.offline)


if __name__ == "__main__":
    main()
