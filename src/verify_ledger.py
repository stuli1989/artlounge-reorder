"""
Verify ledger reconciliation: start from 0, sum all movements, compare to UC snapshot.

Tests the hypothesis that the ledger contains ALL movements from the beginning,
so sum(IN) - sum(OUT) should equal today's available stock.
"""
import csv
import glob
import os
import sys
import logging
from collections import defaultdict
from datetime import date

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from unicommerce.client import UnicommerceClient
from unicommerce.ledger_parser import parse_ledger_row, _FACILITY_MAP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def load_all_ledger_rows(ledger_dir):
    """Load all CSV files and return parsed rows."""
    all_rows = []
    files = sorted(glob.glob(os.path.join(ledger_dir, "*.csv")))
    print(f"Found {len(files)} CSV files")

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
        print(f"  {filename}: {count} rows")

    all_rows.sort(key=lambda r: r["txn_date"])
    print(f"\nTotal: {len(all_rows)} parsed rows")
    return all_rows


def pull_fresh_snapshot_for_skus(client, sku_codes):
    """Pull live UC inventory snapshot for specific SKUs."""
    print(f"\nPulling fresh UC snapshot for {len(sku_codes)} SKUs...")
    aggregated = {}

    for facility in client.facilities:
        data = client._request(
            "POST",
            "/services/rest/v1/inventory/inventorySnapshot/get",
            json={"itemTypeSKUs": list(sku_codes)},
            facility=facility,
            timeout=120,
        )
        snapshots = data.get("inventorySnapshots", [])
        for snap in snapshots:
            sku = snap.get("itemTypeSKU")
            if not sku:
                continue
            inv = snap.get("inventory", 0) or 0
            blocked = snap.get("inventoryBlocked", 0) or 0
            putaway = snap.get("putawayPending", 0) or 0
            open_sale = snap.get("openSale", 0) or 0
            open_purchase = snap.get("openPurchase", 0) or 0
            bad = snap.get("badInventory", 0) or 0

            if sku not in aggregated:
                aggregated[sku] = {
                    "inventory": 0, "blocked": 0, "putaway": 0,
                    "openSale": 0, "openPurchase": 0, "bad": 0,
                }
            aggregated[sku]["inventory"] += inv
            aggregated[sku]["blocked"] += blocked
            aggregated[sku]["putaway"] += putaway
            aggregated[sku]["openSale"] += open_sale
            aggregated[sku]["openPurchase"] += open_purchase
            aggregated[sku]["bad"] += bad

    # Compute available_stock = inventory - blocked + putaway (F1)
    result = {}
    for sku, d in aggregated.items():
        result[sku] = {
            "inventory": d["inventory"],
            "blocked": d["blocked"],
            "putaway": d["putaway"],
            "available_stock": d["inventory"] - d["blocked"] + d["putaway"],
            "openSale": d["openSale"],
            "openPurchase": d["openPurchase"],
            "bad": d["bad"],
        }
    return result


def analyze_sku(sku_code, rows):
    """Analyze a single SKU's ledger movements."""
    total_in = 0.0
    total_out = 0.0
    first_date = None
    last_date = None
    entity_breakdown = defaultdict(lambda: {"in": 0.0, "out": 0.0, "count": 0})

    # Check for duplicates
    seen_keys = set()
    dupes = 0

    for r in rows:
        # Dedup key: entity_code + sku + txn_type + date
        key = (r["entity_code"], r["sku_code"], r["txn_type"], r["txn_date"], r["units"])
        if key in seen_keys:
            dupes += 1
            continue
        seen_keys.add(key)

        if first_date is None or r["txn_date"] < first_date:
            first_date = r["txn_date"]
        if last_date is None or r["txn_date"] > last_date:
            last_date = r["txn_date"]

        change = r["stock_change"]
        entity = r["entity"]

        if change > 0:
            total_in += change
            entity_breakdown[entity]["in"] += change
        else:
            total_out += abs(change)
            entity_breakdown[entity]["out"] += abs(change)
        entity_breakdown[entity]["count"] += 1

    net = total_in - total_out

    return {
        "total_in": total_in,
        "total_out": total_out,
        "net_balance": net,
        "first_date": first_date,
        "last_date": last_date,
        "row_count": len(seen_keys),
        "duplicate_rows": dupes,
        "entity_breakdown": dict(entity_breakdown),
    }


def main():
    ledger_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "transactionLedger"))

    # SKUs to verify:
    # 3 from negative_stock_skus.csv (heavily negative in Tally)
    negative_skus = ["6312", "8811-2", "1414644"]

    # We'll also pick 7+ more from the ledger data for variety
    # (selected after loading data)

    # Step 1: Load all ledger data
    print("=" * 70)
    print("LEDGER RECONCILIATION VERIFICATION")
    print("=" * 70)
    all_rows = load_all_ledger_rows(ledger_dir)

    # Group by SKU
    by_sku = defaultdict(list)
    for r in all_rows:
        by_sku[r["sku_code"]].append(r)

    print(f"\nUnique SKUs in ledger: {len(by_sku)}")

    # Pick additional SKUs: high activity, medium activity, low activity
    sku_counts = [(sku, len(rows)) for sku, rows in by_sku.items()]
    sku_counts.sort(key=lambda x: x[1], reverse=True)

    # Top 3 by activity (high volume)
    high_activity = [s[0] for s in sku_counts[:3]]
    # Middle range
    mid_idx = len(sku_counts) // 2
    mid_activity = [s[0] for s in sku_counts[mid_idx:mid_idx+2]]
    # Low activity (but not single-row)
    low_activity = [s[0] for s in sku_counts if s[1] >= 5][-2:]

    test_skus = list(set(negative_skus + high_activity + mid_activity + low_activity))

    # Make sure negative SKUs are in the ledger
    for sku in negative_skus:
        if sku not in by_sku:
            print(f"  WARNING: {sku} (negative stock) not found in ledger!")

    print(f"\nTest SKUs selected ({len(test_skus)}):")
    for sku in test_skus:
        count = len(by_sku.get(sku, []))
        label = " [NEGATIVE STOCK]" if sku in negative_skus else ""
        print(f"  {sku}: {count} ledger rows{label}")

    # Step 2: Pull fresh UC snapshot
    print("\n" + "=" * 70)
    print("PULLING LIVE UC SNAPSHOT")
    print("=" * 70)

    client = UnicommerceClient()
    client.authenticate()
    client.discover_facilities()

    snapshot = pull_fresh_snapshot_for_skus(client, test_skus)
    print(f"Got snapshot for {len(snapshot)} SKUs")

    # Step 3: Analyze and compare
    print("\n" + "=" * 70)
    print("RECONCILIATION RESULTS")
    print("=" * 70)

    results = []
    for sku in sorted(test_skus):
        rows = by_sku.get(sku, [])
        analysis = analyze_sku(sku, rows)
        snap = snapshot.get(sku, {})
        available = snap.get("available_stock", "N/A")

        if available != "N/A":
            diff = analysis["net_balance"] - available
            match = "MATCH" if abs(diff) < 0.01 else f"DIFF: {diff:+.1f}"
        else:
            diff = None
            match = "NO SNAPSHOT"

        results.append({
            "sku": sku,
            "analysis": analysis,
            "snapshot": snap,
            "available_stock": available,
            "diff": diff,
            "match": match,
        })

        neg_label = " ** NEGATIVE STOCK SKU **" if sku in negative_skus else ""
        print(f"\n--- {sku}{neg_label} ---")
        print(f"  Ledger rows: {analysis['row_count']} (dupes skipped: {analysis['duplicate_rows']})")
        print(f"  Date range: {analysis['first_date']} to {analysis['last_date']}")
        print(f"  Total IN:  {analysis['total_in']:>10.1f}")
        print(f"  Total OUT: {analysis['total_out']:>10.1f}")
        print(f"  Net (from 0): {analysis['net_balance']:>10.1f}")
        print(f"  UC Snapshot:  {available if available != 'N/A' else 'N/A':>10}")
        if available != "N/A":
            print(f"  UC breakdown: inventory={snap['inventory']}, blocked={snap['blocked']}, putaway={snap['putaway']}")
        print(f"  >>> {match}")

        # Show entity breakdown
        print(f"  Entity breakdown:")
        for entity, vals in sorted(analysis["entity_breakdown"].items()):
            parts = []
            if vals["in"] > 0:
                parts.append(f"IN={vals['in']:.0f}")
            if vals["out"] > 0:
                parts.append(f"OUT={vals['out']:.0f}")
            print(f"    {entity:30s} {', '.join(parts):>30s} ({vals['count']} rows)")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    matches = sum(1 for r in results if r["match"] == "MATCH")
    mismatches = [r for r in results if r["diff"] is not None and abs(r["diff"]) >= 0.01]
    no_snap = sum(1 for r in results if r["match"] == "NO SNAPSHOT")

    print(f"  Total SKUs tested: {len(results)}")
    print(f"  Perfect matches:   {matches}")
    print(f"  Mismatches:        {len(mismatches)}")
    print(f"  No snapshot:       {no_snap}")

    if mismatches:
        print(f"\n  MISMATCHES:")
        for r in mismatches:
            print(f"    {r['sku']}: ledger_net={r['analysis']['net_balance']:.1f}, "
                  f"snapshot={r['available_stock']:.1f}, diff={r['diff']:+.1f}")


if __name__ == "__main__":
    main()
