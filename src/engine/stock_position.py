"""
Daily stock position computation.

Two modes:
1. HISTORICAL BACKFILL (ledger_import.py): Uses Transaction Ledger CSVs
   with today's snapshot as anchor to reconstruct every historical day.

2. NIGHTLY SYNC (this module): Uses consecutive inventory snapshots.
   Each night's snapshot IS the closing position for that day.
   Inward/outward quantities come from the transactions table.
   Channel breakdown (wholesale/online/store) comes from API-pulled
   dispatches. Movements not captured by the API (adjustments, transfers)
   show up as snapshot deltas but don't affect velocity (correct behavior —
   only customer demand drives velocity).

is_in_stock semantics (F4):
  A day is "in stock" if available_stock > 0 OR if demand occurred that day.
"""
from datetime import date, timedelta
from collections import defaultdict

import psycopg2.extras


def build_positions_from_snapshots(
    db_conn,
    start_date: date = None,
    end_date: date = None,
):
    """Build daily positions from stored inventory snapshots + transactions.

    For each day that has a snapshot, the closing_qty = snapshot available_stock.
    For days between snapshots, closing_qty is interpolated from the nearest
    earlier snapshot adjusted by transactions.

    Inward/outward/channel breakdowns come from the transactions table.

    This is the nightly sync path — used after the initial ledger backfill.
    """
    if end_date is None:
        end_date = date.today()

    # Get all snapshot dates
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT snapshot_date FROM daily_inventory_snapshots
            WHERE snapshot_date >= %s AND snapshot_date <= %s
            ORDER BY snapshot_date
        """, (start_date or date(2025, 1, 1), end_date))
        snapshot_dates = [row[0] for row in cur.fetchall()]

    if not snapshot_dates:
        return []

    # For each snapshot date, get all SKU positions
    all_positions = []
    for snap_date in snapshot_dates:
        positions = _build_positions_for_date(db_conn, snap_date)
        all_positions.extend(positions)

    return all_positions


def _build_positions_for_date(db_conn, position_date):
    """Build positions for a single date using snapshot + transactions."""
    positions = []

    # Get snapshot data for this date
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sku_code, available_stock
            FROM daily_inventory_snapshots
            WHERE snapshot_date = %s
        """, (position_date,))
        snapshots = {row[0]: float(row[1]) for row in cur.fetchall()}

    # Get transactions for this date
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT stock_item_name, quantity, is_inward, channel, return_type
            FROM transactions
            WHERE txn_date = %s
        """, (position_date,))

        txns_by_sku = defaultdict(list)
        for row in cur.fetchall():
            txns_by_sku[row[0]].append({
                "quantity": float(row[1]),
                "is_inward": row[2],
                "channel": row[3],
                "return_type": row[4],
            })

    for sku, closing_qty in snapshots.items():
        day_txns = txns_by_sku.get(sku, [])

        day_inward = sum(t["quantity"] for t in day_txns if t["is_inward"])
        day_outward = sum(t["quantity"] for t in day_txns if not t["is_inward"])

        day_wholesale_out = 0.0
        day_online_out = 0.0
        day_store_out = 0.0

        for t in day_txns:
            if not t["is_inward"]:
                ch = t.get("channel", "")
                if ch == "wholesale":
                    day_wholesale_out += t["quantity"]
                elif ch == "online":
                    day_online_out += t["quantity"]
                elif ch == "store":
                    day_store_out += t["quantity"]
            elif t.get("return_type"):
                ch = t.get("channel", "")
                qty = t["quantity"]
                if ch == "wholesale":
                    day_wholesale_out -= qty
                elif ch == "online":
                    day_online_out -= qty
                elif ch == "store":
                    day_store_out -= qty

        opening_qty = closing_qty - day_inward + day_outward
        had_demand = (day_wholesale_out + day_online_out + day_store_out) > 0
        is_in_stock = closing_qty > 0 or had_demand

        positions.append({
            "stock_item_name": sku,
            "position_date": position_date,
            "opening_qty": opening_qty,
            "inward_qty": day_inward,
            "outward_qty": day_outward,
            "closing_qty": closing_qty,
            "wholesale_out": day_wholesale_out,
            "online_out": day_online_out,
            "store_out": day_store_out,
            "is_in_stock": is_in_stock,
        })

    return positions


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
    else:
        latest_snap_date = None
        latest_snap_stock = 0

    # Compute opening balance: work backwards from latest snapshot
    if latest_snap_date:
        # Sum all movements from start_date through latest_snap_date
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
            SELECT txn_date AS date, quantity, is_inward, channel, voucher_type,
                   party_name, return_type
            FROM transactions
            WHERE stock_item_name = %s
            ORDER BY txn_date, id
        """, (stock_item_name,))
        cols = [desc[0] for desc in cur.description]
        rows = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["quantity"] = float(d["quantity"])
            rows.append(d)
        return rows


def fetch_snapshot_dates_for_item(db_conn, stock_item_name: str) -> dict:
    """Fetch all snapshot dates and available_stock for a SKU."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT snapshot_date, available_stock
            FROM daily_inventory_snapshots
            WHERE sku_code = %s
            ORDER BY snapshot_date
        """, (stock_item_name,))
        return {row[0]: float(row[1]) for row in cur.fetchall()}
