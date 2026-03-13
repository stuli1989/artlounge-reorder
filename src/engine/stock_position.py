"""
Daily stock position reconstruction using DUAL-ANCHOR method.

Two parallel reconstructions run in a single pass:

1. Backward (closing-anchored): implied_opening = closing - sum(inward) + sum(outward).
   Used for stored opening_qty/closing_qty — internally consistent with transactions.

2. Forward (opening-anchored): starts from Tally's authoritative opening_balance.
   Used ONLY for is_in_stock determination — gives the most accurate estimate of
   whether stock was actually available, since Tally may include stock from company
   mergers that have no corresponding vouchers in our extraction.

is_in_stock semantics:
  A day is "in stock" if forward_closing > 0 OR if real demand (wholesale/online/store
  sales) occurred that day.
"""
from datetime import date, timedelta
from collections import defaultdict

import psycopg2.extras


def reconstruct_daily_positions(
    stock_item_name: str,
    closing_balance: float,
    opening_date: date,
    transactions: list[dict],
    end_date: date,
    tally_opening: float | None = None,
) -> list[dict]:
    """
    Reconstruct daily stock positions by anchoring on closing_balance (from Tally)
    and replaying transactions to compute historical positions.

    Channel rules:
    - wholesale/online/store outward -> counted as demand
    - supplier inward -> stock in, not demand
    - internal -> SKIP entirely (doesn't affect balance)
    - ignore (Physical Stock) -> affects balance, NOT demand
    - Credit Note -> inward for balance, NOT demand
    - Debit Note -> outward for balance, NOT demand
    """
    # Group transactions by date
    txns_by_date = defaultdict(list)
    for t in transactions:
        txns_by_date[t["date"]].append(t)

    # First pass: compute total inward and outward to find implied opening
    total_inward = 0.0
    total_outward = 0.0
    for t in transactions:
        if t.get("channel") == "internal":
            continue
        if t["is_inward"]:
            total_inward += t["quantity"]
        else:
            total_outward += t["quantity"]

    implied_opening = closing_balance - total_inward + total_outward

    # Forward anchor: Tally's authoritative opening balance.
    # When available, gives a more accurate picture of actual stock levels
    # for is_in_stock determination, since Tally may include stock from
    # company mergers that have no corresponding vouchers in our data.
    forward_opening = tally_opening if tally_opening is not None else implied_opening

    # Second pass: walk forward from implied opening, recording daily positions
    positions = []
    running_balance = implied_opening       # backward: ensures closing matches Tally
    forward_balance = forward_opening       # forward: ensures opening matches Tally
    current = opening_date

    while current <= end_date:
        day_inward = 0.0
        day_outward = 0.0
        day_wholesale_out = 0.0
        day_online_out = 0.0
        day_store_out = 0.0

        for t in txns_by_date.get(current, []):
            channel = t.get("channel", "unclassified")
            voucher_type = t.get("voucher_type", "")

            # Skip internal transactions entirely
            if channel == "internal":
                continue

            if t["is_inward"]:
                day_inward += t["quantity"]
            else:
                day_outward += t["quantity"]

            # Demand tracking: only for real demand channels, not returns/adjustments
            is_return = voucher_type in ("Credit Note", "Debit Note")
            is_adjustment = channel == "ignore"

            if not t["is_inward"] and not is_return and not is_adjustment:
                if channel == "wholesale":
                    day_wholesale_out += t["quantity"]
                elif channel == "online":
                    day_online_out += t["quantity"]
                elif channel == "store":
                    day_store_out += t["quantity"]

        had_demand = (day_wholesale_out + day_online_out + day_store_out) > 0
        opening_qty = running_balance
        closing_qty = opening_qty + day_inward - day_outward
        running_balance = closing_qty

        # Forward reconstruction: tracks stock from Tally's opening
        forward_closing = forward_balance + day_inward - day_outward
        forward_balance = forward_closing

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
            "is_in_stock": forward_closing > 0 or had_demand,
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
            SELECT txn_date AS date, quantity, is_inward, channel, voucher_type, party_name
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
