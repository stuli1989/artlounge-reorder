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


def validate_extraction_counts(db_conn, new_counts: dict) -> list[str]:
    """Compare new extraction counts against previous sync to detect data issues.

    Returns list of warning messages. Raises ValueError if critical drop detected.
    """
    warnings = []

    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT categories_synced, items_synced, transactions_synced
            FROM sync_log WHERE status = 'completed'
            ORDER BY sync_completed DESC LIMIT 1
        """)
        prev = cur.fetchone()

    if not prev:
        return warnings  # First sync, nothing to compare

    prev_cats = prev[0] or 0
    prev_items = prev[1] or 0
    prev_txns = prev[2] or 0

    new_cats = new_counts.get("categories", 0)
    new_items = new_counts.get("items", 0)

    # Critical: categories dropped to 0
    if prev_cats > 0 and new_cats == 0:
        raise ValueError(
            f"Categories dropped from {prev_cats} to 0 — aborting sync. "
            "Tally may not be responding correctly."
        )

    # Critical: items dropped >10%
    if prev_items > 0 and new_items < prev_items * 0.9:
        raise ValueError(
            f"Items dropped >10%: {prev_items} → {new_items} — aborting sync. "
            "Check Tally data integrity."
        )

    # Warning: transaction count dropped
    new_txns = new_counts.get("transactions", 0)
    if prev_txns > 0 and new_txns < prev_txns:
        warnings.append(
            f"Transaction count dropped: {prev_txns} → {new_txns}. "
            "This could indicate a Tally issue."
        )

    return warnings
