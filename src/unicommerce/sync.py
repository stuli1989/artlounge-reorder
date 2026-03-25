"""
Nightly sync orchestrator for Unicommerce.

Pulls incremental data from UC API, normalizes into transactions,
and runs the computation pipeline.

CLI usage:
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.sync
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.sync --full
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.sync --dry-run
"""
import argparse
import logging
import sys
from datetime import date, datetime, timedelta

from config.settings import (
    UC_TENANT, UC_USERNAME, UC_PASSWORD, DATABASE_URL, FY_START_DATE,
)
from extraction.data_loader import get_db_connection
from unicommerce.client import UnicommerceClient
from unicommerce.catalog import pull_all_skus, pull_updated_skus, load_catalog
from unicommerce.inventory import pull_inventory_snapshot, store_daily_snapshot
from unicommerce.orders import pull_dispatched_since, transform_packages_to_transactions
from unicommerce.returns import pull_returns_since, transform_returns_to_transactions, store_return_details
from unicommerce.inbound import pull_grns_since, transform_grns_to_transactions, store_grn_details
from unicommerce.transaction_loader import load_transactions
from engine.pipeline import run_computation_pipeline

logger = logging.getLogger(__name__)


def get_last_successful_sync(db_conn):
    """Get the last successful sync record."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT id, sync_completed FROM sync_log
            WHERE status = 'completed' AND source = 'unicommerce'
            ORDER BY sync_completed DESC LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return {"id": row[0], "completed_at": row[1]}
    return None


def create_sync_log(db_conn, source="unicommerce"):
    """Create a new sync log entry."""
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sync_log (sync_started, status, source)
            VALUES (NOW(), 'running', %s)
            RETURNING id
        """, (source,))
        sync_id = cur.fetchone()[0]
    db_conn.commit()
    return sync_id


def update_sync_log(db_conn, sync_id, status, stats=None, error=None):
    """Update sync log with completion status."""
    with db_conn.cursor() as cur:
        cur.execute("""
            UPDATE sync_log SET
                sync_completed = NOW(),
                status = %s,
                items_synced = %s,
                dispatches_synced = %s,
                returns_synced = %s,
                grns_synced = %s,
                error_message = %s
            WHERE id = %s
        """, (
            status,
            stats.get("skus_updated", 0) if stats else 0,
            stats.get("dispatches", 0) if stats else 0,
            stats.get("returns", 0) if stats else 0,
            stats.get("grns", 0) if stats else 0,
            error,
            sync_id,
        ))
    db_conn.commit()


def minutes_since(dt):
    """Compute minutes between a datetime and now."""
    if dt is None:
        return 99999
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime.combine(dt, datetime.min.time())
    if dt.tzinfo:
        from datetime import timezone
        now = datetime.now(timezone.utc)
    else:
        now = datetime.now()
    diff = now - dt
    return int(diff.total_seconds() / 60)


def hours_since(dt):
    """Compute hours between a datetime/date and now."""
    return max(1, minutes_since(dt) // 60)


def run_nightly_sync(db_conn, full=False, dry_run=False):
    """
    Main sync entry point.

    Args:
        db_conn: PostgreSQL connection
        full: Force complete re-pull (first run or recovery)
        dry_run: Pull data but don't write to DB
    """
    sync_id = create_sync_log(db_conn)

    try:
        # Authenticate
        print("Authenticating with Unicommerce...")
        client = UnicommerceClient(UC_TENANT, UC_USERNAME, UC_PASSWORD)
        client.authenticate()
        client.discover_facilities()
        client.store_facilities(db_conn)
        print(f"  Authenticated. Facilities: {client.facilities}")

        # Determine sync window
        last_sync = get_last_successful_sync(db_conn)
        if last_sync and not full:
            since_date = last_sync["completed_at"]
            if isinstance(since_date, datetime):
                since_date = since_date.date()
            since_minutes = minutes_since(last_sync["completed_at"]) + 60
            since_hours = hours_since(last_sync["completed_at"]) + 1
            print(f"  Incremental sync since {since_date}")
        else:
            since_date = FY_START_DATE
            since_minutes = minutes_since(FY_START_DATE) + 60
            since_hours = hours_since(FY_START_DATE) + 1
            print(f"  Full sync from {since_date}")

        stats = {"skus_updated": 0, "dispatches": 0, "returns": 0, "grns": 0}

        # Step 1: Update catalog
        print("\n1. Pulling catalog...")
        if full:
            uc_items = pull_all_skus(client)
        else:
            uc_items = pull_updated_skus(client, hours_since=since_hours)
        stats["skus_updated"] = len(uc_items)
        if not dry_run:
            load_catalog(db_conn, uc_items)
        print(f"  {len(uc_items)} SKUs pulled")

        # Step 2: Inventory snapshot (always full)
        print("\n2. Pulling inventory snapshot...")
        aggregated, facility_data = pull_inventory_snapshot(client, db_conn)
        if not dry_run:
            store_daily_snapshot(db_conn, date.today(), aggregated, facility_data)
        print(f"  {len(aggregated)} SKUs with inventory")

        # Step 3: Dispatched shipments
        print("\n3. Pulling dispatched shipments...")
        packages = pull_dispatched_since(client, minutes_since=since_minutes)
        dispatch_txns = transform_packages_to_transactions(packages)
        stats["dispatches"] = len(packages)
        if not dry_run:
            load_transactions(db_conn, dispatch_txns)
        print(f"  {len(packages)} packages → {len(dispatch_txns)} transaction rows")

        # Step 4: Returns
        print("\n4. Pulling returns...")
        returns = pull_returns_since(client, since_date)
        return_txns = transform_returns_to_transactions(returns)
        stats["returns"] = len(returns)
        if not dry_run:
            load_transactions(db_conn, return_txns)
            store_return_details(db_conn, returns)
        print(f"  {len(returns)} returns → {len(return_txns)} transaction rows")

        # Step 5: GRNs
        print("\n5. Pulling GRNs...")
        grns = pull_grns_since(client, since_date)
        grn_txns = transform_grns_to_transactions(grns)
        stats["grns"] = len(grns)
        if not dry_run:
            load_transactions(db_conn, grn_txns)
            store_grn_details(db_conn, grns)
        print(f"  {len(grns)} GRNs → {len(grn_txns)} transaction rows")

        # Step 6: Computation pipeline
        if not dry_run:
            print("\n6. Running computation pipeline...")
            run_computation_pipeline(db_conn, incremental=not full)
        else:
            print("\n6. Skipping pipeline (dry run)")

        # Step 7: Update sync log
        if not dry_run:
            update_sync_log(db_conn, sync_id, status="completed", stats=stats)

        print(f"\nSync complete! Stats: {stats}")

        # Step 8: Send notification
        try:
            from sync.email_notifier import send_sync_notification
            send_sync_notification(success=True, stats=stats)
        except Exception as e:
            logger.warning("Email notification failed: %s", e)

        return stats

    except Exception as e:
        logger.error("Sync failed: %s", e, exc_info=True)
        update_sync_log(db_conn, sync_id, status="failed", error=str(e))

        try:
            from sync.email_notifier import send_sync_notification
            send_sync_notification(success=False, error=str(e))
        except Exception:
            pass

        raise


def main():
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Unicommerce nightly sync")
    parser.add_argument("--full", action="store_true", help="Full re-sync (not incremental)")
    parser.add_argument("--dry-run", action="store_true", help="Pull data but don't write to DB")
    args = parser.parse_args()

    db_conn = get_db_connection()
    try:
        run_nightly_sync(db_conn, full=args.full, dry_run=args.dry_run)
    finally:
        db_conn.close()


if __name__ == "__main__":
    main()
