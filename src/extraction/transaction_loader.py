"""
Transaction data loader — loads inventory voucher line items into PostgreSQL,
enriched with channel classification.
"""
import os
from datetime import datetime, date

import psycopg2.extras

from extraction.party_classifier import classify_transaction_channel


def build_party_channel_cache(db_conn) -> dict:
    """Build a dict of {party_name: channel} for fast lookup during loading."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT tally_name, channel FROM parties")
        return {row[0]: row[1] for row in cur.fetchall()}


def _parse_tally_date(date_str: str) -> date:
    """Parse YYYYMMDD date string to Python date."""
    return datetime.strptime(date_str, "%Y%m%d").date()


def load_transactions(db_conn, parsed_vouchers: list[dict], channel_cache: dict = None) -> int:
    """
    Insert parsed voucher line items into transactions table.

    Uses ON CONFLICT DO NOTHING to handle duplicates safely.
    Returns count of newly inserted rows.
    """
    if not parsed_vouchers:
        return 0

    if channel_cache is None:
        channel_cache = build_party_channel_cache(db_conn)

    sql = """
        INSERT INTO transactions (txn_date, party_name, voucher_type, voucher_number,
                                  stock_item_name, quantity, is_inward, rate, amount,
                                  channel, tally_master_id)
        VALUES (%(txn_date)s, %(party_name)s, %(voucher_type)s, %(voucher_number)s,
                %(stock_item_name)s, %(quantity)s, %(is_inward)s, %(rate)s, %(amount)s,
                %(channel)s, %(tally_master_id)s)
        ON CONFLICT (txn_date, voucher_number, stock_item_name, quantity, is_inward, rate)
        DO NOTHING
    """

    rows = []
    for v in parsed_vouchers:
        party_channel = channel_cache.get(v["party"], "unclassified")
        txn_channel = classify_transaction_channel(v["voucher_type"], v["party"], party_channel)

        rows.append({
            "txn_date": _parse_tally_date(v["date"]),
            "party_name": v["party"],
            "voucher_type": v["voucher_type"],
            "voucher_number": v["voucher_number"],
            "stock_item_name": v["stock_item"],
            "quantity": v["quantity"],
            "is_inward": v["is_inward"],
            "rate": v["rate"],
            "amount": v["amount"],
            "channel": txn_channel,
            "tally_master_id": v.get("tally_master_id"),
        })

    with db_conn.cursor() as cur:
        before = _count_transactions(cur)
        psycopg2.extras.execute_batch(cur, sql, rows, page_size=1000)
        after = _count_transactions(cur)

    db_conn.commit()
    return after - before


def _count_transactions(cur) -> int:
    cur.execute("SELECT COUNT(*) FROM transactions")
    return cur.fetchone()[0]


def load_transactions_from_file(db_conn, xml_path: str = None) -> int:
    """Load transactions from a cached voucher XML file (for POC / no Tally)."""
    from extraction.xml_parser import parse_vouchers

    if xml_path is None:
        xml_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "sample_responses", "vouchers_full_fy.xml"
        )

    print(f"Loading vouchers from {os.path.basename(xml_path)}...")
    with open(xml_path, "rb") as f:
        vouchers = parse_vouchers(f.read())
    print(f"  Parsed {len(vouchers)} line items")

    channel_cache = build_party_channel_cache(db_conn)
    inserted = load_transactions(db_conn, vouchers, channel_cache)
    print(f"  Inserted {inserted} new transactions")
    return inserted


def sync_transactions_from_tally(tally_client, db_conn) -> int:
    """
    Pull all vouchers from Tally and load into database.

    Note: TDL Collections ignore SVFROMDATE/SVTODATE, so we always get the
    full FY. Date filtering is done in Python. ON CONFLICT DO NOTHING handles
    re-syncing safely — already-imported rows are skipped.
    """
    from extraction.xml_requests import inventory_vouchers_request
    from extraction.xml_parser import parse_vouchers

    print("Pulling vouchers from Tally (full FY, ~190 MB)...")
    xml_request = inventory_vouchers_request()
    raw = tally_client.send_request_raw(xml_request, timeout=600)
    vouchers = parse_vouchers(raw)
    print(f"  Parsed {len(vouchers)} line items")

    channel_cache = build_party_channel_cache(db_conn)
    inserted = load_transactions(db_conn, vouchers, channel_cache)
    print(f"  Inserted {inserted} new transactions ({len(vouchers) - inserted} already existed)")
    return inserted
