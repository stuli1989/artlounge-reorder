"""
Test extraction script — validates Tally connectivity and pulls sample data.

Run from src/ directory:
    python extraction/test_extraction.py

Saves raw XML responses to data/sample_responses/ for manual inspection.
This is NOT part of the nightly sync — it's a one-time validation tool.
"""
import os
import sys
import time
from collections import Counter

# Ensure src/ is on the path when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.tally_client import TallyClient
from extraction.xml_requests import (
    STOCK_CATEGORIES_REQUEST,
    STOCK_ITEMS_REQUEST,
    LEDGER_LIST_REQUEST,
    inventory_vouchers_request,
)
from config.settings import TALLY_HOST, TALLY_PORT

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sample_responses")


def save_raw(filename: str, data: bytes):
    """Save raw bytes to output directory."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)
    size_kb = len(data) / 1024
    print(f"  Saved to {path} ({size_kb:.1f} KB)")


def step_1_test_connection(client: TallyClient) -> bool:
    print("=" * 60)
    print("STEP 1: Test Connection")
    print("=" * 60)
    ok = client.test_connection()
    if not ok:
        print("\nFATAL: Cannot connect to Tally. Exiting.")
    print()
    return ok


def step_2_stock_categories(client: TallyClient):
    print("=" * 60)
    print("STEP 2: Stock Categories (Brands)")
    print("=" * 60)
    try:
        raw = client.send_request_raw(STOCK_CATEGORIES_REQUEST, timeout=60)
        save_raw("stock_categories.xml", raw)

        root = client.send_request(STOCK_CATEGORIES_REQUEST, timeout=60)
        categories = root.findall(".//STOCKCATEGORY")
        print(f"  Total categories: {len(categories)}")
        print(f"  First 10:")
        for cat in categories[:10]:
            name = cat.get("NAME") or "(unnamed)"
            parent = (cat.findtext("PARENT") or "").strip()
            print(f"    - {name} (parent: {parent or 'N/A'})")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()


def step_3_stock_items(client: TallyClient):
    print("=" * 60)
    print("STEP 3: Stock Items (SKUs)")
    print("=" * 60)
    try:
        raw = client.send_request_raw(STOCK_ITEMS_REQUEST, timeout=600)
        save_raw("stock_items.xml", raw)

        root = client.send_request(STOCK_ITEMS_REQUEST, timeout=600)
        items = root.findall(".//STOCKITEM")
        print(f"  Total stock items: {len(items)}")

        # Count by category (brand)
        category_counts = Counter()
        for item in items:
            cat = (item.findtext("CATEGORY") or "").strip()
            category_counts[cat or "(no category)"] += 1

        print(f"  Unique categories: {len(category_counts)}")
        print(f"  Top 15 categories by item count:")
        for cat_name, count in category_counts.most_common(15):
            print(f"    - {cat_name}: {count} items")

        # Check for items with closing balance info
        with_balance = 0
        for item in items[:100]:  # sample first 100
            cb = (item.findtext("CLOSINGBALANCE") or "").strip()
            if cb:
                with_balance += 1
        print(f"  Items with closing balance (sample of 100): {with_balance}")
    except Exception as e:
        print(f"  ERROR: {e}")
        if "timeout" in str(e).lower():
            print("  TIP: Stock items response may be very large. Consider pulling per-brand.")
    print()


def step_4_ledgers(client: TallyClient):
    print("=" * 60)
    print("STEP 4: Ledger List (Parties)")
    print("=" * 60)
    try:
        raw = client.send_request_raw(LEDGER_LIST_REQUEST, timeout=60)
        save_raw("ledgers.xml", raw)

        root = client.send_request(LEDGER_LIST_REQUEST, timeout=60)
        ledgers = root.findall(".//LEDGER")
        print(f"  Total ledgers: {len(ledgers)}")

        # Group by parent
        parent_counts = Counter()
        for ledger in ledgers:
            parent = (ledger.findtext("PARENT") or "").strip()
            parent_counts[parent or "(no parent)"] += 1

        print(f"  By parent group:")
        for parent_name, count in parent_counts.most_common():
            print(f"    - {parent_name}: {count}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()


def step_5_vouchers(client: TallyClient):
    print("=" * 60)
    print("STEP 5: Vouchers with Inventory Entries (Full FY)")
    print("=" * 60)
    print("  Note: TDL collections return all FY vouchers (date filtering")
    print("  is not supported at the Tally level; filter in Python).")
    print()

    try:
        xml_req = inventory_vouchers_request()
        print("  Sending request to Tally (may take 1-2 minutes)...")
        start = time.time()
        raw = client.send_request_raw(xml_req, timeout=600)
        elapsed = time.time() - start
        size_mb = len(raw) / 1024 / 1024
        print(f"  Response: {size_mb:.1f} MB in {elapsed:.0f}s")
        save_raw("vouchers_full_fy.xml", raw)

        print("  Parsing XML...")
        root = client.send_request(xml_req, timeout=600) if size_mb < 50 else None
        if root is None:
            # For very large responses, parse from saved raw
            sanitized = client._sanitize_xml(raw)
            from lxml import etree
            root = etree.fromstring(sanitized)

        vouchers = root.findall(".//VOUCHER")
        print(f"  Total vouchers: {len(vouchers)}")

        # Analyze voucher types, dates, parties, inventory
        type_counts = Counter()
        inv_type_counts = Counter()
        date_set = set()
        party_set = set()
        total_inv_entries = 0

        for v in vouchers:
            vtype = v.findtext("VOUCHERTYPENAME") or v.get("VCHTYPE") or "(unknown)"
            type_counts[vtype] += 1

            vdate = (v.findtext("DATE") or "").strip()
            if vdate:
                date_set.add(vdate)

            party = (v.findtext("PARTYLEDGERNAME") or "").strip()
            if party:
                party_set.add(party)

            # Count inventory entries (non-empty ones)
            inv_entries = v.findall(".//ALLINVENTORYENTRIES.LIST")
            real_inv = [e for e in inv_entries if (e.findtext("STOCKITEMNAME") or "").strip()]
            if real_inv:
                inv_type_counts[vtype] += 1
                total_inv_entries += len(real_inv)

        print(f"\n  Date range: {min(date_set) if date_set else 'N/A'} to {max(date_set) if date_set else 'N/A'}")
        print(f"  Unique parties: {len(party_set)}")
        print(f"  Total inventory line items: {total_inv_entries}")

        print(f"\n  By voucher type:")
        for vtype, count in type_counts.most_common():
            inv_c = inv_type_counts.get(vtype, 0)
            print(f"    {vtype}: {count} total, {inv_c} with inventory")

        # Show sample inventory voucher
        print(f"\n  Sample voucher with inventory entries:")
        for v in vouchers:
            inv_entries = v.findall(".//ALLINVENTORYENTRIES.LIST")
            real_inv = [e for e in inv_entries if (e.findtext("STOCKITEMNAME") or "").strip()]
            if real_inv:
                vtype = v.findtext("VOUCHERTYPENAME") or "?"
                vdate = (v.findtext("DATE") or "?").strip()
                party = (v.findtext("PARTYLEDGERNAME") or "?").strip()
                vnum = (v.findtext("VOUCHERNUMBER") or "?").strip()
                amt = (v.findtext("AMOUNT") or "?").strip()
                print(f"    {vdate} | {vtype} | {party} | #{vnum} | Rs.{amt}")
                print(f"    Line items ({len(real_inv)}):")
                for ie in real_inv[:5]:
                    sname = (ie.findtext("STOCKITEMNAME") or "?").strip()
                    qty = (ie.findtext("ACTUALQTY") or "?").strip()
                    rate = (ie.findtext("RATE") or "?").strip()
                    iamt = (ie.findtext("AMOUNT") or "?").strip()
                    print(f"      {sname} | Qty: {qty} | Rate: {rate} | Amt: {iamt}")
                if len(real_inv) > 5:
                    print(f"      ... and {len(real_inv) - 5} more")
                break

        # Show sample parties for channel classification
        print(f"\n  Sample parties (first 20 unique):")
        for p in sorted(party_set)[:20]:
            print(f"    - {p}")

    except Exception as e:
        print(f"  ERROR: {e}")
        if "timeout" in str(e).lower():
            print("  TIP: Voucher response is very large (~190 MB). Increase timeout or check Tally.")
    print()


def main():
    print()
    print("=" * 60)
    print("  ART LOUNGE — Tally Data Extraction Test")
    print(f"  Target: {TALLY_HOST}:{TALLY_PORT}")
    print("=" * 60)
    print()

    client = TallyClient(host=TALLY_HOST, port=TALLY_PORT)

    # Step 1: Test connection (abort if fails)
    if not step_1_test_connection(client):
        sys.exit(1)

    # Steps 2-5: Pull each data type
    step_2_stock_categories(client)
    step_3_stock_items(client)
    step_4_ledgers(client)
    step_5_vouchers(client)

    # Summary
    print("=" * 60)
    print("  EXTRACTION TEST COMPLETE")
    print("=" * 60)
    print(f"  Raw XML files saved to: {OUTPUT_DIR}")
    print()
    print("  NEXT STEPS:")
    print("  1. Open the saved XML files and inspect the structure")
    print("  2. Check that stock items have Category (brand) fields")
    print("  3. Check that vouchers have party, stock item, quantity fields")
    print("  4. Note any unexpected XML element names for parser development (T05)")
    print()


if __name__ == "__main__":
    main()
