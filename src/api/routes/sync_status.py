"""Sync status API endpoint."""
import threading
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user, require_role
from api.database import get_db
from unicommerce.ledger_sync import get_sync_progress

router = APIRouter(tags=["sync"])


@router.get("/sync/status")
def sync_status(user: dict = Depends(get_current_user)):
    """Return last sync info and data freshness."""
    progress = get_sync_progress()

    with get_db() as conn:
        with conn.cursor() as cur:
            # Last completed sync
            cur.execute("""
                SELECT * FROM sync_log
                WHERE status = 'completed'
                ORDER BY sync_completed DESC
                LIMIT 1
            """)
            last_sync = cur.fetchone()

            # Count unclassified parties
            cur.execute("SELECT COUNT(*) AS cnt FROM parties WHERE channel = 'unclassified'")
            unclassified = cur.fetchone()["cnt"]

            # Data freshness info
            cur.execute("SELECT MAX(snapshot_date) FROM inventory_snapshots")
            latest_snapshot_date = cur.fetchone()[0]

            cur.execute("SELECT MAX(txn_date) FROM transactions")
            latest_transaction_date = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM sku_metrics")
            total_skus = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM brand_metrics")
            total_brands = cur.fetchone()[0]

    now = datetime.now(timezone.utc)

    if not last_sync:
        return {
            "last_sync_completed": None,
            "status": "never",
            "ledger_rows_loaded": 0,
            "facilities_synced": 0,
            "freshness": "critical",
            "unclassified_parties_count": unclassified,
            "is_running": progress["running"],
            "current_step": progress["step"],
            "sync_error": progress["error"],
            "latest_snapshot_date": str(latest_snapshot_date) if latest_snapshot_date else None,
            "latest_transaction_date": str(latest_transaction_date) if latest_transaction_date else None,
            "total_skus": total_skus,
            "total_brands": total_brands,
            "days_since_sync": None,
        }

    completed = last_sync["sync_completed"]
    if completed.tzinfo is None:
        hours_ago = (now.replace(tzinfo=None) - completed).total_seconds() / 3600
    else:
        hours_ago = (now - completed).total_seconds() / 3600

    days_since_sync = round(hours_ago / 24, 1)

    if hours_ago < 24:
        freshness = "fresh"
    elif hours_ago < 48:
        freshness = "stale"
    else:
        freshness = "critical"

    return {
        "last_sync_completed": last_sync["sync_completed"],
        "status": last_sync["status"],
        "ledger_rows_loaded": last_sync.get("ledger_rows_loaded", 0) or 0,
        "facilities_synced": last_sync.get("facilities_synced", 0) or 0,
        "freshness": freshness,
        "unclassified_parties_count": unclassified,
        "is_running": progress["running"],
        "current_step": progress["step"],
        "sync_error": progress["error"],
        "latest_snapshot_date": str(latest_snapshot_date) if latest_snapshot_date else None,
        "latest_transaction_date": str(latest_transaction_date) if latest_transaction_date else None,
        "total_skus": total_skus,
        "total_brands": total_brands,
        "days_since_sync": days_since_sync,
    }


@router.post("/sync/trigger")
def trigger_sync(user: dict = Depends(require_role("admin"))):
    """Manually trigger a full data sync. Admin only."""
    progress = get_sync_progress()
    if progress["running"]:
        raise HTTPException(409, "A sync is already running")

    def _run_sync():
        try:
            from extraction.data_loader import get_db_connection
            from unicommerce.ledger_sync import run_nightly_sync
            conn = get_db_connection()
            run_nightly_sync(conn)
            conn.close()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Manual sync failed")

    thread = threading.Thread(target=_run_sync, daemon=True)
    thread.start()
    return {"status": "started"}
