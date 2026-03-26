"""
Transaction Ledger CSV import — ingests UC Transaction Ledger exports
for complete historical backfill.

The transaction ledger contains ALL inventory movements including:
- Initial stock load (INVENTORY_ADJUSTMENT / ADD)
- GRN receipts (PUTAWAY_GRN_ITEM)
- Sales dispatches (MANUAL picklists + SALE invoices)
- Stock transfers between facilities (STOCK_TRANSFER)
- Stock audit adjustments (ADD / REMOVE / REPLACE)
- Returns putaway (CIR / RTO)
- Cancelled pick putbacks

This data is richer than the REST API, which only exposes GRNs and
shipping package dispatches.

Usage:
  cd src && PYTHONPATH=. ./venv/Scripts/python -m unicommerce.ledger_import
"""
import csv
import glob
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta

import psycopg2.extras

from extraction.data_loader import get_db_connection
from engine.stock_position import upsert_daily_positions
from engine.pipeline import run_computation_pipeline

logger = logging.getLogger(__name__)

# Map ledger Entity/EntityType to our channel taxonomy
# Entity types that represent demand (sales to customers)
_DEMAND_ENTITY_TYPES = {"MANUAL", "SALE"}

# Map facility names from ledger to our facility codes
_FACILITY_MAP = {
    "PPETPL Bhiwandi": "ppetpl",
    "PPETPL Kala Ghoda": "PPETPLKALAGHODA",
    "Art Lounge Bhiwandi": "ALIBHIWANDI",
}


def parse_ledger_row(row):
    """Parse a single CSV row into a normalized dict."""
    sku_code = row["SKU Code"].lstrip("'").strip()
    if not sku_code:
        return None

    units = float(row.get("Units", 0) or 0)
    txn_type = row.get("Transaction Type", "").strip()  # IN or OUT
    entity = row.get("Entity", "").strip()
    entity_type = row.get("Entity Type", "").strip()
    entity_code = row.get("Entity Code", "").strip().rstrip(",")
    from_facility = row.get("From Facility", "-").strip()
    to_facility = row.get("To Facility", "-").strip()
    sale_order = row.get("Sale Order Code", "-").strip().lstrip("'")

    # Parse date
    date_str = row.get("Inventory Updated At", "").strip()
    try:
        if " " in date_str:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date()
        else:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

    # Determine the facility this movement applies to
    if txn_type == "OUT":
        facility = from_facility
    else:
        facility = to_facility
    facility_code = _FACILITY_MAP.get(facility, facility)

    # Compute actual stock change (signed)
    # For OUT: units are positive in CSV, but represent a decrease
    # For IN: units can be positive (increase) or negative (REMOVE/REPLACE)
    if txn_type == "OUT":
        stock_change = -abs(units)
    else:
        stock_change = units  # already signed correctly (negative for REMOVE)

    # Determine channel for demand tracking
    channel = _classify_channel(entity, entity_type, sale_order, from_facility, to_facility)

    # Is this a demand transaction (affects velocity)?
    is_demand = entity_type in _DEMAND_ENTITY_TYPES and txn_type == "OUT"

    return {
        "sku_code": sku_code,
        "sku_name": row.get("SKU Name", "").strip(),
        "txn_date": txn_date,
        "entity": entity,
        "entity_type": entity_type,
        "entity_code": entity_code,
        "facility": facility_code,
        "units": units,
        "stock_change": stock_change,
        "txn_type": txn_type,
        "is_demand": is_demand,
        "channel": channel,
        "sale_order_code": sale_order if sale_order != "-" else None,
    }


def _classify_channel(entity, entity_type, sale_order, from_fac, to_fac):
    """Classify the channel for a ledger row."""
    if entity == "GRN":
        return "supplier"
    if entity == "INVENTORY_ADJUSTMENT":
        return "internal"
    if entity in ("OUTBOUND_GATEPASS", "INBOUND_GATEPASS"):
        return "internal"  # inter-facility transfers
    if entity == "INVOICES":
        return "store"  # direct invoiced sales (B2B or walk-in)
    if entity == "PICKLIST":
        # Picklists could be wholesale, online, or store
        # Sale order codes starting with certain prefixes indicate channel
        # but we don't have a reliable mapping here — mark as wholesale
        # (the nightly sync uses shipping package channel which is more accurate)
        if "Kala Ghoda" in (from_fac or ""):
            return "store"
        return "wholesale"  # default for picklists from Bhiwandi
    if entity in ("PUTAWAY_CIR", "PUTAWAY_RTO"):
        return "online"  # returns are mostly from online
    if entity == "PUTAWAY_CANCELLED_ITEM":
        return "internal"
    if entity == "PUTAWAY_PICKLIST_ITEM":
        return "internal"
    return "internal"


def load_all_ledger_files(directory):
    """Load and parse all Transaction Ledger CSV files from a directory.

    Returns list of parsed rows sorted by date.
    """
    all_rows = []
    files = sorted(glob.glob(os.path.join(directory, "*.csv")))

    for filepath in files:
        filename = os.path.basename(filepath)
        count = 0
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                parsed = parse_ledger_row(row)
                if parsed:
                    all_rows.append(parsed)
                    count += 1
        logger.info("  %s: %d rows", filename, count)

    all_rows.sort(key=lambda r: r["txn_date"])
    logger.info("Total ledger rows: %d", len(all_rows))
    return all_rows


def build_daily_positions_from_ledger(ledger_rows, snapshot_data, start_date, end_date):
    """Build daily stock positions per SKU from ledger data.

    Uses today's inventory snapshot as the ground truth anchor.
    Computes opening balance: snapshot - net_movements_after_start = opening.
    Then walks forward day by day applying real movements.

    Args:
        ledger_rows: parsed ledger rows (all SKUs, sorted by date)
        snapshot_data: {sku: available_stock} from today's snapshot
        start_date: first date to compute positions for
        end_date: last date (today)

    Returns:
        list of position dicts ready for upsert
    """
    # Group ledger rows by SKU
    by_sku = defaultdict(list)
    for row in ledger_rows:
        by_sku[row["sku_code"]].append(row)

    all_positions = []
    skus_processed = 0

    # Also include SKUs that have snapshot data but no ledger rows
    all_skus = set(by_sku.keys()) | set(snapshot_data.keys())

    for sku in all_skus:
        rows = by_sku.get(sku, [])
        today_stock = snapshot_data.get(sku, 0)

        # Group movements by date
        movements_by_date = defaultdict(list)
        for r in rows:
            if start_date <= r["txn_date"] <= end_date:
                movements_by_date[r["txn_date"]].append(r)

        # Compute total net movement from start_date to end_date
        total_net = sum(r["stock_change"] for r in rows if start_date <= r["txn_date"] <= end_date)

        # Opening balance = today's stock - all net movements
        opening_balance = today_stock - total_net

        # Walk forward day by day
        balance = opening_balance
        current = start_date

        while current <= end_date:
            day_movements = movements_by_date.get(current, [])

            day_inward = 0.0
            day_outward = 0.0
            day_wholesale_out = 0.0
            day_online_out = 0.0
            day_store_out = 0.0

            for m in day_movements:
                if m["stock_change"] > 0:
                    day_inward += m["stock_change"]
                elif m["stock_change"] < 0:
                    day_outward += abs(m["stock_change"])

                # Track demand by channel (only for actual sales, not transfers)
                if m["is_demand"]:
                    qty = abs(m["stock_change"])
                    ch = m["channel"]
                    if ch == "wholesale":
                        day_wholesale_out += qty
                    elif ch == "online":
                        day_online_out += qty
                    elif ch == "store":
                        day_store_out += qty

            opening_qty = balance
            balance = balance + day_inward - day_outward
            closing_qty = balance

            had_demand = (day_wholesale_out + day_online_out + day_store_out) > 0
            is_in_stock = closing_qty > 0 or had_demand

            all_positions.append({
                "stock_item_name": sku,
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

        skus_processed += 1
        if skus_processed % 2000 == 0:
            logger.info("  Processed %d/%d SKUs...", skus_processed, len(all_skus))

    return all_positions


def run_ledger_backfill(ledger_dir, db_conn):
    """Full backfill from Transaction Ledger CSVs.

    1. Load all CSV files
    2. Get today's inventory snapshot as anchor
    3. Build daily positions for every SKU
    4. Upsert positions into daily_stock_positions
    5. Run computation pipeline
    """
    print("=== LEDGER BACKFILL ===")
    print()

    # 1. Load ledger data
    print("Step 1: Loading ledger CSVs...")
    ledger_rows = load_all_ledger_files(ledger_dir)
    print(f"  {len(ledger_rows)} total rows loaded")

    # Determine date range from ledger
    dates = [r["txn_date"] for r in ledger_rows]
    ledger_start = min(dates)
    ledger_end = max(dates)
    print(f"  Date range: {ledger_start} to {ledger_end}")

    # Count unique SKUs
    unique_skus = set(r["sku_code"] for r in ledger_rows)
    print(f"  Unique SKUs in ledger: {len(unique_skus)}")

    # 2. Get today's snapshot as anchor
    print()
    print("Step 2: Loading today's inventory snapshot as anchor...")
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (sku_code)
                sku_code, available_stock
            FROM daily_inventory_snapshots
            ORDER BY sku_code, snapshot_date DESC
        """)
        snapshot_data = {row[0]: float(row[1]) for row in cur.fetchall()}
    print(f"  {len(snapshot_data)} SKUs with snapshot data")

    # 3. Build daily positions
    print()
    print("Step 3: Building daily positions from ledger + snapshot...")
    today = date.today()
    # Use FY start or ledger start, whichever is earlier
    from config.settings import FY_START_DATE
    start_date = min(FY_START_DATE, ledger_start)

    positions = build_daily_positions_from_ledger(
        ledger_rows, snapshot_data, start_date, today
    )
    print(f"  {len(positions)} daily position rows built")

    # 4. Upsert positions in chunks
    print()
    print("Step 4: Upserting positions to database...")
    chunk_size = 50000
    for i in range(0, len(positions), chunk_size):
        chunk = positions[i:i + chunk_size]
        upsert_daily_positions(db_conn, chunk)
        db_conn.commit()
        print(f"  Upserted {min(i + chunk_size, len(positions))}/{len(positions)}...")

    # 5. Verify with test SKU
    print()
    print("Step 5: Verification...")
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT position_date, opening_qty, closing_qty, inward_qty, outward_qty
            FROM daily_stock_positions
            WHERE stock_item_name = '2320617'
            AND (inward_qty > 0 OR outward_qty > 0)
            ORDER BY position_date
        """)
        print("  SKU 2320617 (WN PAC 60ML SILVER) movements:")
        for row in cur.fetchall():
            print(f"    {row[0]}: open={row[1]}, close={row[2]}, in={row[3]}, out={row[4]}")

        cur.execute("""
            SELECT position_date, closing_qty FROM daily_stock_positions
            WHERE stock_item_name = '2320617'
            ORDER BY position_date DESC LIMIT 1
        """)
        latest = cur.fetchone()
        if latest:
            print(f"  Latest position: {latest[0]} closing={latest[1]}")
            print(f"  Snapshot today: {snapshot_data.get('2320617', 'N/A')}")

        # Check for any negative positions
        cur.execute("SELECT COUNT(*) FROM daily_stock_positions WHERE closing_qty < 0")
        neg = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM daily_stock_positions")
        total = cur.fetchone()[0]
        print(f"  Total positions: {total}, Negative: {neg}")

    # 6. Run pipeline
    print()
    print("Step 6: Running computation pipeline...")
    run_computation_pipeline(db_conn, incremental=False)

    print()
    print("LEDGER BACKFILL COMPLETE.")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    ledger_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "transactionLedger"
    )
    ledger_dir = os.path.abspath(ledger_dir)

    if not os.path.exists(ledger_dir):
        print(f"Ledger directory not found: {ledger_dir}")
        return

    db_conn = get_db_connection()
    try:
        run_ledger_backfill(ledger_dir, db_conn)
    finally:
        db_conn.close()


if __name__ == "__main__":
    main()
