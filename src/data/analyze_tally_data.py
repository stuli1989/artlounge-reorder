"""
Data Analysis Script — Validate Real Tally Data Before Building Pipeline

Parses all 4 sample XML files using T05 parsers and runs 10 analysis areas
to validate assumptions made in the specs.
"""
import sys
import os
from collections import Counter, defaultdict
from datetime import datetime

# Ensure src/ is on the path so parser imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from extraction.xml_parser import (
    parse_stock_categories,
    parse_stock_items,
    parse_ledgers,
    parse_vouchers,
)

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_responses")
REPORT_FILE = os.path.join(os.path.dirname(__file__), "analysis_report.txt")

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Collect all output lines for both console and file
_output_lines = []


def out(text=""):
    _output_lines.append(text)
    print(text)


def section(title):
    out("")
    out("=" * 80)
    out(f"  {title}")
    out("=" * 80)


def subsection(title):
    out("")
    out(f"--- {title} ---")


# ──────────────────────────────────────────────────────────────────
# Load data
# ──────────────────────────────────────────────────────────────────
def load_all():
    out("Loading XML files...")

    with open(os.path.join(SAMPLE_DIR, "stock_categories.xml"), "rb") as f:
        categories = parse_stock_categories(f.read())
    out(f"  Stock categories: {len(categories)}")

    with open(os.path.join(SAMPLE_DIR, "stock_items.xml"), "rb") as f:
        items = parse_stock_items(f.read())
    out(f"  Stock items:      {len(items)}")

    with open(os.path.join(SAMPLE_DIR, "ledgers.xml"), "rb") as f:
        ledgers = parse_ledgers(f.read())
    out(f"  Ledgers:          {len(ledgers)}")

    out("  Loading vouchers (190 MB, may take ~30s)...")
    with open(os.path.join(SAMPLE_DIR, "vouchers_full_fy.xml"), "rb") as f:
        vouchers = parse_vouchers(f.read())
    out(f"  Voucher line items: {len(vouchers)}")

    return categories, items, ledgers, vouchers


# ──────────────────────────────────────────────────────────────────
# Analysis 1: Stock Categories (Brands)
# ──────────────────────────────────────────────────────────────────
def analyze_categories(categories):
    section("1. STOCK CATEGORIES (BRANDS)")

    out(f"Total count: {len(categories)}")

    # Duplicates
    names = [c["name"] for c in categories]
    dupes = [n for n, cnt in Counter(names).items() if cnt > 1]
    out(f"Duplicates: {len(dupes)}")
    if dupes:
        for d in dupes:
            out(f"  DUPLICATE: {d}")

    # Blanks
    blanks = [c for c in categories if not c["name"].strip()]
    out(f"Blank names: {len(blanks)}")

    # Parent distribution
    parents = Counter(c["parent"] for c in categories)
    out(f"Parent distribution:")
    for p, cnt in parents.most_common():
        out(f"  {p or '(None)'}: {cnt}")

    # Sample names
    out(f"First 20 category names:")
    for c in sorted(categories, key=lambda x: x["name"])[:20]:
        out(f"  {c['name']} (parent={c['parent']})")


# ──────────────────────────────────────────────────────────────────
# Analysis 2: Stock Items — Completeness & Balances
# ──────────────────────────────────────────────────────────────────
def analyze_items(items, vouchers):
    section("2. STOCK ITEMS — COMPLETENESS & BALANCES")

    out(f"Total items: {len(items)}")

    # Category coverage
    with_cat = sum(1 for i in items if i["category"])
    without_cat = sum(1 for i in items if not i["category"])
    out(f"With category: {with_cat}")
    out(f"Without category: {without_cat}")
    if without_cat > 0:
        no_cat_examples = [i["name"] for i in items if not i["category"]][:10]
        out(f"  Examples without category: {no_cat_examples}")

    # Opening balance
    with_opening = sum(1 for i in items if i["opening_balance"] != 0)
    out(f"Items with opening_balance != 0: {with_opening}")
    neg_opening = [i for i in items if i["opening_balance"] < 0]
    out(f"Items with NEGATIVE opening balance: {len(neg_opening)}")
    if neg_opening:
        for i in neg_opening[:10]:
            out(f"  {i['name']}: opening={i['opening_balance']}")

    # Closing balance
    in_stock = sum(1 for i in items if i["closing_balance"] > 0)
    out_of_stock = sum(1 for i in items if i["closing_balance"] == 0)
    negative = sum(1 for i in items if i["closing_balance"] < 0)
    out(f"Closing balance > 0 (in stock): {in_stock}")
    out(f"Closing balance = 0 (out of stock): {out_of_stock}")
    out(f"Closing balance < 0 (NEGATIVE): {negative}")
    if negative > 0:
        neg_items = sorted([i for i in items if i["closing_balance"] < 0],
                           key=lambda x: x["closing_balance"])
        out(f"  Top 15 most negative:")
        for i in neg_items[:15]:
            out(f"    {i['name']}: closing={i['closing_balance']}, category={i['category']}")

    # Unit types
    units = Counter(i["base_unit"] for i in items)
    out(f"Distinct units: {len(units)}")
    for u, cnt in units.most_common():
        out(f"  {u or '(None)'}: {cnt}")

    # Items with transactions vs dead SKUs
    items_in_txns = set(v["stock_item"] for v in vouchers)
    items_set = set(i["name"] for i in items)
    active = items_set & items_in_txns
    dead = items_set - items_in_txns
    in_txn_not_master = items_in_txns - items_set
    out(f"Items with transactions: {len(active)}")
    out(f"Dead SKUs (no transactions): {len(dead)}")
    out(f"In transactions but NOT in stock items list: {len(in_txn_not_master)}")
    if in_txn_not_master:
        for name in sorted(in_txn_not_master)[:10]:
            out(f"  MISSING from master: {name}")


# ──────────────────────────────────────────────────────────────────
# Analysis 3: Opening Balance Verification (CRITICAL)
# ──────────────────────────────────────────────────────────────────
def analyze_balance_verification(items, vouchers):
    section("3. OPENING BALANCE VERIFICATION (CRITICAL)")

    # Build lookup: item name -> opening_balance, closing_balance
    item_lookup = {i["name"]: i for i in items}

    # Build per-item inward/outward sums
    item_inward = defaultdict(float)
    item_outward = defaultdict(float)
    for v in vouchers:
        if v["is_inward"]:
            item_inward[v["stock_item"]] += v["quantity"]
        else:
            item_outward[v["stock_item"]] += v["quantity"]

    # Test with items that have both opening balance AND transactions
    test_items = [
        name for name in item_lookup
        if item_lookup[name]["opening_balance"] != 0
        and (name in item_inward or name in item_outward)
    ]

    out(f"Items with opening balance AND transactions: {len(test_items)}")

    # Compute and compare
    matches = 0
    mismatches = []
    for name in test_items:
        item = item_lookup[name]
        computed = item["opening_balance"] + item_inward.get(name, 0) - item_outward.get(name, 0)
        actual = item["closing_balance"]
        diff = abs(computed - actual)
        if diff < 0.01:  # floating point tolerance
            matches += 1
        else:
            mismatches.append({
                "name": name,
                "opening": item["opening_balance"],
                "inward": item_inward.get(name, 0),
                "outward": item_outward.get(name, 0),
                "computed_closing": computed,
                "actual_closing": actual,
                "diff": computed - actual,
            })

    out(f"Matches (opening + inward - outward = closing): {matches}")
    out(f"Mismatches: {len(mismatches)}")

    if mismatches:
        out(f"\nFirst 20 mismatches:")
        for m in sorted(mismatches, key=lambda x: abs(x["diff"]), reverse=True)[:20]:
            out(f"  {m['name']}")
            out(f"    opening={m['opening']:.2f} + inward={m['inward']:.2f} - outward={m['outward']:.2f} = {m['computed_closing']:.2f}")
            out(f"    actual_closing={m['actual_closing']:.2f}, diff={m['diff']:.2f}")

    # Also check items with zero opening but have transactions
    zero_opening_items = [
        name for name in item_lookup
        if item_lookup[name]["opening_balance"] == 0
        and (name in item_inward or name in item_outward)
    ]
    out(f"\nItems with ZERO opening but have transactions: {len(zero_opening_items)}")

    zero_mismatches = 0
    for name in zero_opening_items:
        item = item_lookup[name]
        computed = item_inward.get(name, 0) - item_outward.get(name, 0)
        actual = item["closing_balance"]
        if abs(computed - actual) >= 0.01:
            zero_mismatches += 1

    out(f"Of those, mismatches: {zero_mismatches}")


# ──────────────────────────────────────────────────────────────────
# Analysis 4: Party / Channel Classification
# ──────────────────────────────────────────────────────────────────
def analyze_parties(vouchers, ledgers):
    section("4. PARTY / CHANNEL CLASSIFICATION")

    # All unique parties from vouchers
    voucher_parties = set(v["party"] for v in vouchers if v["party"])
    ledger_names = set(l["name"] for l in ledgers)
    ledger_parents = {l["name"]: l["parent"] for l in ledgers}

    out(f"Unique parties in vouchers: {len(voucher_parties)}")
    out(f"Unique ledgers: {len(ledger_names)}")

    # Parties in vouchers but not in ledger list
    missing = voucher_parties - ledger_names
    out(f"Parties in vouchers but NOT in ledger list: {len(missing)}")
    if missing:
        for p in sorted(missing)[:20]:
            out(f"  MISSING: {p}")

    # Ledger parent distribution for voucher parties
    subsection("Ledger group distribution for parties in vouchers")
    parent_counts = Counter()
    for p in voucher_parties:
        parent_counts[ledger_parents.get(p, "(not in ledgers)")] += 1
    for parent, cnt in parent_counts.most_common():
        out(f"  {parent}: {cnt}")

    # Auto-classification by voucher type
    subsection("Auto-classification by voucher type")
    type_parties = defaultdict(set)
    for v in vouchers:
        type_parties[v["voucher_type"]].add(v["party"])

    for vtype in sorted(type_parties):
        parties = type_parties[vtype]
        out(f"  {vtype}: {len(parties)} unique parties")

    # Auto-classification by party name patterns
    subsection("Auto-classification by party name patterns")
    online_patterns = ["MAGENTO", "Flipkart", "Amazon", "ARTLOUNGE.IN", "Meesho"]
    internal_patterns = ["Art Lounge India - Purchase", "Art Lounge India"]
    store_patterns = ["Store", "Walk-in", "Walk in", "Counter"]

    classified = defaultdict(list)
    for p in voucher_parties:
        p_upper = p.upper()
        found = False
        for pat in online_patterns:
            if pat.upper() in p_upper:
                classified["online"].append(p)
                found = True
                break
        if not found:
            for pat in internal_patterns:
                if pat.upper() in p_upper:
                    classified["internal"].append(p)
                    found = True
                    break
        if not found:
            parent = ledger_parents.get(p, "")
            if parent == "Sundry Creditors":
                classified["supplier"].append(p)
                found = True
        if not found:
            classified["unclassified"].append(p)

    for channel, parties in sorted(classified.items()):
        out(f"  {channel}: {len(parties)}")
        for p in sorted(parties)[:5]:
            out(f"    {p}")
        if len(parties) > 5:
            out(f"    ... and {len(parties) - 5} more")


# ──────────────────────────────────────────────────────────────────
# Analysis 5: Voucher Type → Channel Mapping
# ──────────────────────────────────────────────────────────────────
def analyze_voucher_types(vouchers):
    section("5. VOUCHER TYPE → CHANNEL MAPPING")

    # For each voucher type, list top parties by transaction count
    type_party_counts = defaultdict(Counter)
    type_line_counts = Counter()
    for v in vouchers:
        type_party_counts[v["voucher_type"]][v["party"]] += 1
        type_line_counts[v["voucher_type"]] += 1

    for vtype in sorted(type_party_counts, key=lambda t: type_line_counts[t], reverse=True):
        out(f"\n{vtype} ({type_line_counts[vtype]} line items):")
        for party, cnt in type_party_counts[vtype].most_common(10):
            out(f"  {cnt:>6}  {party}")

    # Non-inventory voucher types (should have been filtered out by parser)
    subsection("Voucher types with no inventory entries (from voucher XML)")
    # These would have been skipped by the parser since they have no ALLINVENTORYENTRIES
    # But we can check what types we DO have
    types_present = sorted(set(v["voucher_type"] for v in vouchers))
    out(f"Voucher types with inventory entries: {types_present}")


# ──────────────────────────────────────────────────────────────────
# Analysis 6: Transaction Dedup Analysis
# ──────────────────────────────────────────────────────────────────
def analyze_dedup(vouchers):
    section("6. TRANSACTION DEDUP ANALYSIS")

    # Current UNIQUE constraint: (txn_date, voucher_number, stock_item_name, quantity, is_inward)
    dedup_key_current = Counter()
    for v in vouchers:
        key = (v["date"], v["voucher_number"], v["stock_item"], v["quantity"], v["is_inward"])
        dedup_key_current[key] += 1

    dupes_current = {k: c for k, c in dedup_key_current.items() if c > 1}
    out(f"Total line items: {len(vouchers)}")
    out(f"Unique by (date, voucher_number, stock_item, qty, is_inward): {len(dedup_key_current)}")
    out(f"Duplicate groups: {len(dupes_current)}")
    out(f"Total duplicate rows: {sum(c - 1 for c in dupes_current.values())}")

    if dupes_current:
        out(f"\nFirst 10 duplicate groups:")
        for key, cnt in sorted(dupes_current.items(), key=lambda x: x[1], reverse=True)[:10]:
            out(f"  count={cnt}: date={key[0]}, vnum={key[1]}, item={key[2]}, qty={key[3]}, inward={key[4]}")

    # Alternative: tally_master_id + stock_item_name
    subsection("Alternative dedup: (tally_master_id, stock_item_name)")
    alt_key = Counter()
    for v in vouchers:
        key = (v["tally_master_id"], v["stock_item"])
        alt_key[key] += 1

    dupes_alt = {k: c for k, c in alt_key.items() if c > 1}
    out(f"Unique by (master_id, stock_item): {len(alt_key)}")
    out(f"Duplicate groups: {len(dupes_alt)}")
    out(f"Total duplicate rows: {sum(c - 1 for c in dupes_alt.values())}")

    if dupes_alt:
        out(f"\nFirst 10 duplicate groups (alt key):")
        for key, cnt in sorted(dupes_alt.items(), key=lambda x: x[1], reverse=True)[:10]:
            out(f"  count={cnt}: master_id={key[0]}, item={key[1]}")
            # Show details of the duplicates
            examples = [v for v in vouchers if v["tally_master_id"] == key[0] and v["stock_item"] == key[1]]
            for e in examples[:3]:
                out(f"    date={e['date']} party={e['party']} qty={e['quantity']} inward={e['is_inward']} vnum={e['voucher_number']}")

    # Voucher number uniqueness within a date
    subsection("Voucher number uniqueness")
    date_vnum = Counter()
    for v in vouchers:
        date_vnum[(v["date"], v["voucher_number"])] += 1

    # How many unique voucher instances per date
    vnum_counts = Counter(date_vnum.values())
    out(f"Distribution of line items per (date, voucher_number):")
    for cnt in sorted(vnum_counts):
        out(f"  {cnt} line items: {vnum_counts[cnt]} voucher instances")

    # Check: are there NULL voucher numbers?
    null_vnums = sum(1 for v in vouchers if not v["voucher_number"])
    out(f"Vouchers with NULL/empty voucher_number: {null_vnums}")

    # Check: same master_id always has same voucher_number?
    mid_vnums = defaultdict(set)
    for v in vouchers:
        if v["tally_master_id"]:
            mid_vnums[v["tally_master_id"]].add(v["voucher_number"])
    multi_vnum = {mid: vnums for mid, vnums in mid_vnums.items() if len(vnums) > 1}
    out(f"Master IDs with multiple voucher numbers: {len(multi_vnum)}")


# ──────────────────────────────────────────────────────────────────
# Analysis 7: Physical Stock Vouchers (CRITICAL)
# ──────────────────────────────────────────────────────────────────
def analyze_physical_stock(vouchers):
    section("7. PHYSICAL STOCK VOUCHERS (CRITICAL)")

    phys = [v for v in vouchers if v["voucher_type"] == "Physical Stock"]
    out(f"Physical Stock line items: {len(phys)}")

    if not phys:
        out("No Physical Stock vouchers found in data.")
        return

    # Unique vouchers
    phys_vouchers = set((v["date"], v["voucher_number"]) for v in phys)
    out(f"Unique Physical Stock vouchers: {len(phys_vouchers)}")

    # Dates
    dates = sorted(set(v["date"] for v in phys))
    out(f"Dates: {dates}")

    # Direction
    inward = sum(1 for v in phys if v["is_inward"])
    outward = sum(1 for v in phys if not v["is_inward"])
    out(f"Inward (ISDEEMEDPOSITIVE=Yes): {inward}")
    out(f"Outward (ISDEEMEDPOSITIVE=No): {outward}")

    # Quantities
    zero_qty = sum(1 for v in phys if v["quantity"] == 0)
    out(f"Zero quantity entries: {zero_qty}")

    # Rates and amounts
    has_rate = sum(1 for v in phys if v["rate"] != 0)
    has_amount = sum(1 for v in phys if v["amount"] != 0)
    out(f"Entries with rate: {has_rate}")
    out(f"Entries with amount: {has_amount}")

    # Show all entries (since there are only 6 vouchers)
    subsection("All Physical Stock entries")
    for v in phys:
        out(f"  date={v['date']} vnum={v['voucher_number']} item={v['stock_item']}")
        out(f"    qty={v['quantity']} inward={v['is_inward']} rate={v['rate']} amount={v['amount']}")
        out(f"    party={v['party']} master_id={v['tally_master_id']}")


# ──────────────────────────────────────────────────────────────────
# Analysis 8: Credit Notes & Debit Notes
# ──────────────────────────────────────────────────────────────────
def analyze_credit_debit(vouchers):
    section("8. CREDIT NOTES & DEBIT NOTES")

    for note_type in ["Credit Note", "Debit Note"]:
        subsection(note_type)
        notes = [v for v in vouchers if v["voucher_type"] == note_type]
        out(f"Total line items: {len(notes)}")

        if not notes:
            out(f"No {note_type} vouchers found.")
            continue

        # Direction
        inward = sum(1 for v in notes if v["is_inward"])
        outward = sum(1 for v in notes if not v["is_inward"])
        out(f"Inward: {inward}")
        out(f"Outward: {outward}")

        # Parties
        parties = Counter(v["party"] for v in notes)
        out(f"Unique parties: {len(parties)}")
        out(f"Top parties:")
        for party, cnt in parties.most_common(10):
            out(f"  {cnt:>4}  {party}")

        # Unique vouchers
        unique_v = set((v["date"], v["voucher_number"]) for v in notes)
        out(f"Unique vouchers: {len(unique_v)}")


# ──────────────────────────────────────────────────────────────────
# Analysis 9: Direction Logic Validation
# ──────────────────────────────────────────────────────────────────
def analyze_direction(vouchers):
    section("9. DIRECTION LOGIC VALIDATION")

    # For each voucher type, check ISDEEMEDPOSITIVE consistency
    type_direction = defaultdict(Counter)
    for v in vouchers:
        type_direction[v["voucher_type"]][v["is_inward"]] += 1

    for vtype in sorted(type_direction):
        dirs = type_direction[vtype]
        total = sum(dirs.values())
        inward = dirs.get(True, 0)
        outward = dirs.get(False, 0)

        if inward > 0 and outward > 0:
            label = "MIXED"
        elif inward > 0:
            label = "ALL INWARD"
        else:
            label = "ALL OUTWARD"

        out(f"  {vtype:25s}  inward={inward:>6}  outward={outward:>6}  [{label}]")

    # Check for mixed-direction types
    subsection("Detail on MIXED direction types")
    for vtype in sorted(type_direction):
        dirs = type_direction[vtype]
        if dirs.get(True, 0) > 0 and dirs.get(False, 0) > 0:
            out(f"\n{vtype} has MIXED directions:")
            # Show example entries
            examples_in = [v for v in vouchers if v["voucher_type"] == vtype and v["is_inward"]][:3]
            examples_out = [v for v in vouchers if v["voucher_type"] == vtype and not v["is_inward"]][:3]
            out("  Inward examples:")
            for e in examples_in:
                out(f"    date={e['date']} party={e['party']} item={e['stock_item']} qty={e['quantity']}")
            out("  Outward examples:")
            for e in examples_out:
                out(f"    date={e['date']} party={e['party']} item={e['stock_item']} qty={e['quantity']}")


# ──────────────────────────────────────────────────────────────────
# Analysis 10: Time Coverage & Volume
# ──────────────────────────────────────────────────────────────────
def analyze_time_coverage(vouchers):
    section("10. TIME COVERAGE & VOLUME")

    # Parse dates
    dates = []
    for v in vouchers:
        try:
            d = datetime.strptime(v["date"], "%Y%m%d")
            dates.append(d)
        except ValueError:
            pass

    if not dates:
        out("No valid dates found!")
        return

    min_date = min(dates)
    max_date = max(dates)
    out(f"Date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
    out(f"Total days span: {(max_date - min_date).days}")

    # Monthly volume
    subsection("Monthly volume (line items)")
    monthly = Counter()
    for d in dates:
        monthly[d.strftime("%Y-%m")] += 1

    for month in sorted(monthly):
        bar = "#" * (monthly[month] // 200)
        out(f"  {month}: {monthly[month]:>6}  {bar}")

    # Daily volume for spotting gaps
    subsection("Date gaps (days with 0 transactions)")
    from datetime import timedelta
    daily = set(d.date() for d in dates)
    current = min_date.date()
    end = max_date.date()
    gaps = []
    while current <= end:
        if current not in daily and current.weekday() < 6:  # Mon-Sat (skip Sunday)
            gaps.append(current)
        current += timedelta(days=1)

    out(f"Business days with no transactions: {len(gaps)}")
    if gaps:
        out(f"Gap dates (first 30):")
        for g in gaps[:30]:
            out(f"  {g.strftime('%Y-%m-%d')} ({g.strftime('%A')})")

    # Voucher-level count (not line items)
    subsection("Voucher count (unique vouchers, not line items)")
    voucher_keys = set((v["date"], v["voucher_number"], v["voucher_type"]) for v in vouchers)
    out(f"Total unique vouchers: {len(voucher_keys)}")

    monthly_vouchers = Counter()
    for date_str, vnum, vtype in voucher_keys:
        try:
            d = datetime.strptime(date_str, "%Y%m%d")
            monthly_vouchers[d.strftime("%Y-%m")] += 1
        except ValueError:
            pass
    for month in sorted(monthly_vouchers):
        out(f"  {month}: {monthly_vouchers[month]:>5} vouchers")


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────
def main():
    out("=" * 80)
    out("  TALLY DATA ANALYSIS REPORT")
    out(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out("=" * 80)

    categories, items, ledgers, vouchers = load_all()

    analyze_categories(categories)
    analyze_items(items, vouchers)
    analyze_balance_verification(items, vouchers)
    analyze_parties(vouchers, ledgers)
    analyze_voucher_types(vouchers)
    analyze_dedup(vouchers)
    analyze_physical_stock(vouchers)
    analyze_credit_debit(vouchers)
    analyze_direction(vouchers)
    analyze_time_coverage(vouchers)

    section("ANALYSIS COMPLETE")
    out(f"Report saved to: {REPORT_FILE}")

    # Save to file
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(_output_lines))


if __name__ == "__main__":
    main()
