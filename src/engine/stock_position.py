"""
Daily stock position — forward-computed from UC inventory snapshots + transactions.

No backward reconstruction. No Physical Stock SET-TO logic.
The nightly snapshot IS the daily position.

is_in_stock semantics (F4):
  A day is "in stock" if available_stock > 0 OR if demand occurred that day.
  The OR-demand clause catches sell-to-zero days.
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
    """
    Build daily stock positions by combining inventory snapshots with
    transaction data. For dates with a snapshot, use the snapshot's
    available_stock as closing_qty. For dates without, carry forward
    from the last known position.

    Args:
        stock_item_name: SKU identifier
        snapshot_by_date: {date: available_stock} from daily_inventory_snapshots
        transactions: list of transaction dicts with date, quantity, is_inward, channel
        start_date: first date to compute
        end_date: last date to compute

    Returns:
        list of position dicts ready for upsert
    """
    # Group transactions by date
    txns_by_date = defaultdict(list)
    for t in transactions:
        d = t.get("date") or t.get("txn_date")
        if d:
            txns_by_date[d].append(t)

    positions = []
    last_known_stock = 0
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

            # Demand tracking: dispatches (outward) and returns (inward)
            if not t.get("is_inward"):
                if channel == "wholesale":
                    day_wholesale_out += qty
                elif channel == "online":
                    day_online_out += qty
                elif channel == "store":
                    day_store_out += qty
            elif t.get("return_type"):
                # Returns reduce demand (inward but from a demand channel)
                if channel == "wholesale":
                    day_wholesale_out -= qty
                elif channel == "online":
                    day_online_out -= qty
                elif channel == "store":
                    day_store_out -= qty

        # Use snapshot if available, otherwise carry forward
        if current in snapshot_by_date:
            closing_qty = float(snapshot_by_date[current])
            last_known_stock = closing_qty
        else:
            # Estimate: carry forward from last known, apply today's movements
            closing_qty = last_known_stock + day_inward - day_outward
            last_known_stock = closing_qty

        opening_qty = closing_qty - day_inward + day_outward

        # F4: is_in_stock = available_stock > 0 OR had_demand_that_day
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


def store_snapshot_as_position(db_conn, snapshot_date, aggregated_inventory):
    """
    Store today's UC inventory snapshot as daily stock positions.

    For each SKU in the snapshot, creates/updates a daily_stock_positions row
    using the available_stock as the closing_qty. Transaction-based inward/outward
    are filled from the transactions table separately during the full pipeline.

    Args:
        db_conn: PostgreSQL connection
        snapshot_date: date
        aggregated_inventory: {sku: {inventory, blocked, putaway, ...}}
    """
    if not aggregated_inventory:
        return 0

    rows = []
    for sku, data in aggregated_inventory.items():
        # UC's inventory field = available quantity (already excludes blocked)
        available = (data.get("inventory", 0) or 0) + (data.get("putaway", 0) or 0)
        rows.append({
            "stock_item_name": sku,
            "position_date": snapshot_date,
            "opening_qty": available,  # approximation — will be refined by pipeline
            "inward_qty": 0,
            "outward_qty": 0,
            "closing_qty": available,
            "wholesale_out": 0,
            "online_out": 0,
            "store_out": 0,
            "is_in_stock": available > 0,
        })

    upsert_daily_positions(db_conn, rows)
    return len(rows)


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
