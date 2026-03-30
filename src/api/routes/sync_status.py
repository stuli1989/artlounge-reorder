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
        }

    completed = last_sync["sync_completed"]
    now = datetime.now(timezone.utc)
    if completed.tzinfo is None:
        hours_ago = (now.replace(tzinfo=None) - completed).total_seconds() / 3600
    else:
        hours_ago = (now - completed).total_seconds() / 3600

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
