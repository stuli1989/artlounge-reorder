"""
Historical backfill — one-time pull of data from FY start to first sync date.

Phase 1: Backfill transactions (dispatches, returns, GRNs)
Phase 2: Backfill stock positions (Option B — from transactions + anchor snapshot)
Phase 3: Full pipeline recompute

CLI usage:
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.backfill --transactions
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.backfill --positions
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.backfill --full
"""
import argparse
import logging
from datetime import date, timedelta
from collections import defaultdict

from config.settings import UC_TENANT, UC_USERNAME, UC_PASSWORD, FY_START_DATE
from extraction.data_loader import get_db_connection
from unicommerce.client import UnicommerceClient
from unicommerce.orders import pull_dispatched_in_range, transform_packages_to_transactions
from unicommerce.returns import pull_returns_since, transform_returns_to_transactions, store_return_details
from unicommerce.inbound import pull_grns_since, transform_grns_to_transactions, store_grn_details
from unicommerce.transaction_loader import load_transactions
from engine.stock_position import upsert_daily_positions
from engine.pipeline import run_computation_pipeline

logger = logging.getLogger(__name__)


def monthly_windows(start_date, end_date):
    """Yield (month_start, month_end) tuples."""
    current = start_date
    while current < end_date:
        month_end = min(
            date(current.year + (current.month // 12), (current.month % 12) + 1, 1) - timedelta(days=1),
            end_date,
        )
        yield current, month_end
        current = month_end + timedelta(days=1)


def backfill_transactions(client, db_conn, fy_start, end_date):
    """Phase 1: Pull all historical transactions from FY start."""

    print("=== Phase 1: Backfill Transactions ===")

    # 1. Dispatches — paginate by month
    print("\n1a. Backfilling dispatches...")
    total_dispatches = 0
    for month_start, month_end in monthly_windows(fy_start, end_date):
        print(f"  {month_start} to {month_end}...", end=" ")
        for facility in client.facilities:
            packages = pull_dispatched_in_range(client, facility, month_start, month_end)
            txns = transform_packages_to_transactions(packages)
            load_transactions(db_conn, txns)
            total_dispatches += len(packages)
        print(f"done")
    print(f"  Total dispatches: {total_dispatches}")

    # 2. Returns — 30-day windows
    print("\n1b. Backfilling returns...")
    returns = pull_returns_since(client, fy_start, end_date)
    return_txns = transform_returns_to_transactions(returns)
    load_transactions(db_conn, return_txns)
    store_return_details(db_conn, returns)
    print(f"  Total returns: {len(returns)}")

    # 3. GRNs — bounded windows
    print("\n1c. Backfilling GRNs...")
    grns = pull_grns_since(client, fy_start, end_date)
    grn_txns = transform_grns_to_transactions(grns)
    load_transactions(db_conn, grn_txns)
    store_grn_details(db_conn, grns)
    print(f"  Total GRNs: {len(grns)}")

    return {"dispatches": total_dispatches, "returns": len(returns), "grns": len(grns)}


def backfill_stock_positions(db_conn, fy_start, end_date):
    """Phase 2 (Option B): Reconstruct historical stock positions.

    Uses transactions + today's anchor snapshot.
    Walks backwards from anchor to fill in historical daily positions.
    """
    print("\n=== Phase 2: Backfill Stock Positions (Option B) ===")

    # Get today's snapshot as anchor
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT sku_code, available_stock
            FROM daily_inventory_snapshots
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM daily_inventory_snapshots)
        """)
        anchor = {row[0]: float(row[1]) for row in cur.fetchall()}

    if not anchor:
        print("  ERROR: No inventory snapshots found. Run a sync first.")
        return

    anchor_date = end_date
    print(f"  Anchor: {len(anchor)} SKUs at {anchor_date}")

    # Get all transactions grouped by SKU and date
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT stock_item_name, txn_date, quantity, is_inward, channel, return_type
            FROM transactions
            WHERE txn_date >= %s AND txn_date <= %s
            ORDER BY stock_item_name, txn_date DESC
        """, (fy_start, anchor_date))
        cols = [d[0] for d in cur.description]
        all_txns = defaultdict(list)
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["quantity"] = float(d["quantity"])
            all_txns[d["stock_item_name"]].append(d)

    # Walk backwards from anchor for each SKU
    total_positions = 0
    skus = set(anchor.keys()) | set(all_txns.keys())
    print(f"  Processing {len(skus)} SKUs...")

    for idx, sku in enumerate(sorted(skus)):
        current_stock = anchor.get(sku, 0)
        positions = []

        current_date = anchor_date
        while current_date >= fy_start:
            # Get today's transactions (sorted desc, so we process in reverse)
            day_txns = [t for t in all_txns.get(sku, []) if t["txn_date"] == current_date]

            day_inward = sum(float(t["quantity"]) for t in day_txns if t["is_inward"])
            day_outward = sum(float(t["quantity"]) for t in day_txns if not t["is_inward"])

            day_wholesale = sum(float(t["quantity"]) for t in day_txns
                               if not t["is_inward"] and t.get("channel") == "wholesale")
            day_online = sum(float(t["quantity"]) for t in day_txns
                            if not t["is_inward"] and t.get("channel") == "online")
            day_store = sum(float(t["quantity"]) for t in day_txns
                          if not t["is_inward"] and t.get("channel") == "store")

            # Subtract returns from demand channels
            for t in day_txns:
                if t["is_inward"] and t.get("return_type"):
                    ch = t.get("channel", "")
                    qty = float(t["quantity"])
                    if ch == "wholesale":
                        day_wholesale -= qty
                    elif ch == "online":
                        day_online -= qty
                    elif ch == "store":
                        day_store -= qty

            closing_qty = current_stock
            opening_qty = closing_qty - day_inward + day_outward

            had_demand = (day_wholesale + day_online + day_store) > 0
            is_in_stock = closing_qty > 0 or had_demand

            positions.append({
                "stock_item_name": sku,
                "position_date": current_date,
                "opening_qty": opening_qty,
                "inward_qty": day_inward,
                "outward_qty": day_outward,
                "closing_qty": closing_qty,
                "wholesale_out": max(0, day_wholesale),
                "online_out": max(0, day_online),
                "store_out": max(0, day_store),
                "is_in_stock": is_in_stock,
            })

            # Walk backwards: undo today's transactions to get previous day's closing
            current_stock = opening_qty
            current_date -= timedelta(days=1)

        upsert_daily_positions(db_conn, positions)
        total_positions += len(positions)

        if (idx + 1) % 1000 == 0:
            db_conn.commit()
            print(f"  {idx + 1}/{len(skus)} SKUs processed...")

    db_conn.commit()
    print(f"  Backfilled {total_positions} daily positions for {len(skus)} SKUs")


def main():
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Unicommerce historical backfill")
    parser.add_argument("--transactions", action="store_true", help="Backfill transactions from FY start")
    parser.add_argument("--positions", action="store_true", help="Backfill stock positions (Option B)")
    parser.add_argument("--full", action="store_true", help="Full backfill (transactions + positions + recompute)")
    args = parser.parse_args()

    if not (args.transactions or args.positions or args.full):
        parser.print_help()
        return

    db_conn = get_db_connection()
    end_date = date.today()

    try:
        if args.transactions or args.full:
            client = UnicommerceClient(UC_TENANT, UC_USERNAME, UC_PASSWORD)
            client.authenticate()
            client.discover_facilities()
            backfill_transactions(client, db_conn, FY_START_DATE, end_date)

        if args.positions or args.full:
            backfill_stock_positions(db_conn, FY_START_DATE, end_date)

        if args.full:
            print("\n=== Phase 3: Full Pipeline Recompute ===")
            run_computation_pipeline(db_conn, incremental=False)
            print("  Pipeline complete.")

    finally:
        db_conn.close()


if __name__ == "__main__":
    main()
