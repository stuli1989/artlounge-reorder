"""
Sync log helpers for tracking nightly sync runs.
"""
from datetime import date


def create_sync_log(db_conn) -> int:
    """Create a new sync log entry. Returns the sync log ID."""
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sync_log (sync_started, status)
            VALUES (NOW(), 'running')
            RETURNING id
        """)
        sync_id = cur.fetchone()[0]
    db_conn.commit()
    return sync_id


def update_sync_log(db_conn, sync_id: int, **kwargs):
    """Update a sync log entry with results."""
    set_parts = []
    values = []

    for key in ("status", "categories_synced", "items_synced",
                "transactions_synced", "new_parties_found",
                "txn_from_date", "txn_to_date", "error_message"):
        if key in kwargs:
            set_parts.append(f"{key} = %s")
            values.append(kwargs[key])

    if kwargs.get("status") == "completed":
        set_parts.append("sync_completed = NOW()")

    if not set_parts:
        return

    values.append(sync_id)
    sql = f"UPDATE sync_log SET {', '.join(set_parts)} WHERE id = %s"

    with db_conn.cursor() as cur:
        cur.execute(sql, values)
    db_conn.commit()


def get_last_sync_end_date(db_conn) -> date | None:
    """Get the txn_to_date from the last completed sync."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT MAX(txn_to_date) FROM sync_log WHERE status = 'completed'
        """)
        row = cur.fetchone()
        return row[0] if row else None
