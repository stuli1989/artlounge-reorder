"""
Daily stock position reconstruction using FORWARD method from Tally opening.

Walks forward from Tally's opening balance, applying each transaction:
- Sales (wholesale/online/store): decrease stock, count as demand
- Purchases (supplier/internal): increase stock, not demand
- Physical Stock: use BATCHPHYSDIFF (actual adjustment) when available,
  otherwise SET-TO the physical count (ACTUALQTY)
- Credit Note: inward for balance, not demand
- Debit Note: outward for balance, not demand

is_in_stock semantics:
  A day is "in stock" if closing balance > 0 OR if real demand occurred that day.
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
    Reconstruct daily stock positions by walking forward from Tally's opening
    balance, applying transactions day-by-day.

    Physical Stock handling (hybrid):
      - If phys_stock_diff is available: use as additive adjustment
      - If phys_stock_diff is None: treat quantity as SET-TO (replace balance)

    All transaction types affect balance (including internal).
    Only wholesale/online/store sales count as demand.
    """
    # Group transactions by date
    txns_by_date = defaultdict(list)
    for t in transactions:
        txns_by_date[t["date"]].append(t)

    # Use Tally's opening if available, otherwise compute implied opening
    if tally_opening is not None:
        forward_opening = tally_opening
    else:
        # Fallback: compute from closing and all transactions
        total_inward = 0.0
        total_outward = 0.0
        total_phys_diff = 0.0
        for t in transactions:
            if t.get("voucher_type") == "Physical Stock":
                psd = t.get("phys_stock_diff")
                if psd is not None:
                    total_phys_diff += psd
                # For SET-TO entries without diff, we can't compute backward
                # reliably — just skip and accept a gap
            elif t["is_inward"]:
                total_inward += t["quantity"]
            else:
                total_outward += t["quantity"]
        forward_opening = closing_balance - total_inward - total_phys_diff + total_outward

    # Walk forward from opening, recording daily positions
    positions = []
    balance = forward_opening
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

            # Physical Stock: hybrid handling
            if voucher_type == "Physical Stock":
                phys_diff = t.get("phys_stock_diff")
                if phys_diff is not None:
                    # BATCHPHYSDIFF available: use as adjustment
                    if phys_diff >= 0:
                        day_inward += phys_diff
                    else:
                        day_outward += abs(phys_diff)
                    balance += phys_diff
                else:
                    # No diff data: SET-TO the physical count
                    old_balance = balance
                    balance = t["quantity"]
                    diff = balance - old_balance
                    if diff >= 0:
                        day_inward += diff
                    else:
                        day_outward += abs(diff)
                # Physical Stock never counts as demand — skip demand section
                continue

            # All other transactions: apply to balance
            if t["is_inward"]:
                day_inward += t["quantity"]
                balance += t["quantity"]
            else:
                day_outward += t["quantity"]
                balance -= t["quantity"]

            # Demand tracking: only wholesale/online/store sales
            is_credit_note = voucher_type == "Credit Note"
            is_debit_note = voucher_type == "Debit Note"

            if is_credit_note and t["is_inward"]:
                # Credit Note = customer return — subtract from demand
                if channel == "wholesale":
                    day_wholesale_out -= t["quantity"]
                elif channel == "online":
                    day_online_out -= t["quantity"]
                elif channel == "store":
                    day_store_out -= t["quantity"]
            elif not t["is_inward"] and not is_debit_note:
                # Normal outward sale — add to demand
                if channel == "wholesale":
                    day_wholesale_out += t["quantity"]
                elif channel == "online":
                    day_online_out += t["quantity"]
                elif channel == "store":
                    day_store_out += t["quantity"]

        had_demand = (day_wholesale_out + day_online_out + day_store_out) > 0
        opening_qty = balance - day_inward + day_outward
        closing_qty = balance

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
            "is_in_stock": closing_qty > 0 or had_demand,
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
                   party_name, phys_stock_diff
            FROM transactions
            WHERE stock_item_name = %s
            ORDER BY txn_date, id
        """, (stock_item_name,))
        cols = [desc[0] for desc in cur.description]
        rows = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["quantity"] = float(d["quantity"])
            if d.get("phys_stock_diff") is not None:
                d["phys_stock_diff"] = float(d["phys_stock_diff"])
            rows.append(d)
        return rows
