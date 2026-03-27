"""
Daily stock position computation.

Two modes:
1. HISTORICAL BACKFILL (ledger_import.py): Uses Transaction Ledger CSVs
   with today's snapshot as anchor to reconstruct every historical day.

2. PIPELINE RECOMPUTE (this module): Builds daily positions from
   the transactions table. When no snapshots are provided, starts
   from opening balance = 0 and walks forward applying movements.

is_in_stock semantics (F4):
  A day is "in stock" if closing_qty > 0 OR if demand occurred that day.
"""
from datetime import date, timedelta
from collections import defaultdict

import psycopg2.extras


def build_daily_positions_from_snapshots_and_txns(
    stock_item_name: str,
    snapshot_by_date: dict,
    transactions: list[dict],
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Build daily positions for a single SKU using snapshots + transactions.

    For dates with a snapshot, closing_qty = snapshot value (ground truth).
    For dates between snapshots, carry forward from last snapshot and apply
    transaction movements.

    When snapshot_by_date is empty (ledger-based pipeline), starts from
    opening_balance = 0 and relies purely on transaction movements.

    Used by the computation pipeline for per-SKU position building.
    """
    txns_by_date = defaultdict(list)
    for t in transactions:
        d = t.get("date") or t.get("txn_date")
        if d:
            txns_by_date[d].append(t)

    positions = []

    # Find the latest snapshot to anchor from
    if snapshot_by_date:
        latest_snap_date = max(snapshot_by_date.keys())
        latest_snap_stock = float(snapshot_by_date[latest_snap_date])

        # Compute opening balance: work backwards from latest snapshot
        net_movement = 0.0
        for d, txns in txns_by_date.items():
            if start_date <= d <= latest_snap_date:
                for t in txns:
                    qty = float(t.get("quantity", 0))
                    if t.get("is_inward"):
                        net_movement += qty
                    else:
                        net_movement -= qty
        opening_balance = latest_snap_stock - net_movement
    else:
        # No snapshots: start from 0
        opening_balance = 0

    # Walk forward day by day
    balance = opening_balance
    current = start_date

    while current <= end_date:
        day_inward = 0.0
        day_outward = 0.0
        day_wholesale_out = 0.0
        day_online_out = 0.0
        day_store_out = 0.0

        for t in txns_by_date.get(current, []):
            channel = t.get("channel", "unclassified")
            qty = float(t.get("quantity", 0))

            if t.get("is_inward"):
                day_inward += qty
            else:
                day_outward += qty

            if not t.get("is_inward"):
                if channel == "wholesale":
                    day_wholesale_out += qty
                elif channel == "online":
                    day_online_out += qty
                elif channel == "store":
                    day_store_out += qty
            elif t.get("return_type"):
                if channel == "wholesale":
                    day_wholesale_out -= qty
                elif channel == "online":
                    day_online_out -= qty
                elif channel == "store":
                    day_store_out -= qty

        opening_qty = balance
        balance = balance + day_inward - day_outward

        # If we have a snapshot for this date, use it as ground truth
        if current in snapshot_by_date:
            balance = float(snapshot_by_date[current])

        closing_qty = balance

        had_demand = (day_wholesale_out + day_online_out + day_store_out) > 0
        is_in_stock = closing_qty > 0 or had_demand

        positions.append({
            "stock_item_name": stock_item_name,
            "position_date": current,
            "opening_qty": opening_qty,
            "inward_qty": day_inward,
            "outward_qty": day_outward,
            "closing_qty": closing_qty,
            "wholesale_out": day_wholesale_out,
            "online_out": day_online_out,
            "store_out": day_store_out,
            "is_in_stock": is_in_stock,
        })

        current += timedelta(days=1)

    return positions


def upsert_daily_positions(db_conn, positions: list[dict]):
    """Bulk upsert daily positions into the database."""
    if not positions:
        return
    sql = """
        INSERT INTO daily_stock_positions
            (stock_item_name, position_date, opening_qty, inward_qty, outward_qty,
             closing_qty, wholesale_out, online_out, store_out, is_in_stock)
        VALUES
            (%(stock_item_name)s, %(position_date)s, %(opening_qty)s, %(inward_qty)s, %(outward_qty)s,
             %(closing_qty)s, %(wholesale_out)s, %(online_out)s, %(store_out)s, %(is_in_stock)s)
        ON CONFLICT (stock_item_name, position_date) DO UPDATE SET
            opening_qty = EXCLUDED.opening_qty,
            inward_qty = EXCLUDED.inward_qty,
            outward_qty = EXCLUDED.outward_qty,
            closing_qty = EXCLUDED.closing_qty,
            wholesale_out = EXCLUDED.wholesale_out,
            online_out = EXCLUDED.online_out,
            store_out = EXCLUDED.store_out,
            is_in_stock = EXCLUDED.is_in_stock
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, positions, page_size=1000)


def fetch_transactions_for_item(db_conn, stock_item_name: str) -> list[dict]:
    """Fetch all transactions for a given stock item, ordered by date."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT txn_date AS date, stock_change, txn_type,
                   entity, entity_type, channel, is_demand, facility
            FROM transactions
            WHERE stock_item_name = %s
            ORDER BY txn_date, id
        """, (stock_item_name,))
        rows = []
        for row in cur.fetchall():
            rows.append({
                "date": row[0],
                "quantity": abs(row[1]),
                "is_inward": row[2] == "IN",
                "channel": row[5],
                "return_type": "CIR" if row[3] == "PUTAWAY_CIR"
                          else "RTO" if row[3] == "PUTAWAY_RTO" else None,
                "voucher_type": row[3],
                "entity": row[3],
                "entity_type": row[4],
                "is_demand": row[6],
                "facility": row[7],
                "amount": None,
            })
        return rows
