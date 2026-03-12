"""
Investigate SKU rename/merge patterns in Tally data.

Hypothesis: ~95% of items fail opening + inward - outward = closing because
items were renamed in Tally during the FY. Old names carry opening balances,
new names accumulate transactions.
"""
import sys
import os
from collections import defaultdict, Counter
from datetime import datetime
from difflib import SequenceMatcher

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8")

# Ensure src/ is on the path so parser imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from extraction.xml_parser import parse_stock_items, parse_vouchers

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_responses")


def section(title):
    print()
    print("=" * 90)
    print(f"  {title}")
    print("=" * 90)


def subsection(title):
    print()
    print(f"--- {title} ---")


# ──────────────────────────────────────────────────────────────────
# Load data
# ──────────────────────────────────────────────────────────────────
print("Loading stock_items.xml...")
with open(os.path.join(SAMPLE_DIR, "stock_items.xml"), "rb") as f:
    items = parse_stock_items(f.read())
print(f"  Loaded {len(items)} stock items")

print("Loading vouchers_full_fy.xml (190 MB, ~30-60s)...")
with open(os.path.join(SAMPLE_DIR, "vouchers_full_fy.xml"), "rb") as f:
    vouchers = parse_vouchers(f.read())
print(f"  Loaded {len(vouchers)} voucher line items")

# ──────────────────────────────────────────────────────────────────
# Build lookup structures
# ──────────────────────────────────────────────────────────────────
print("\nBuilding lookup structures...")

# Item name -> item dict
item_by_name = {it["name"]: it for it in items}

# Items grouped by category
items_by_category = defaultdict(list)
for it in items:
    cat = it.get("category") or "UNCATEGORIZED"
    items_by_category[cat].append(it)

# Aggregate voucher quantities per stock item
inward_by_item = defaultdict(float)
outward_by_item = defaultdict(float)
txn_count_by_item = defaultdict(int)
txn_dates_by_item = defaultdict(list)

for v in vouchers:
    name = v["stock_item"]
    qty = v["quantity"]
    txn_count_by_item[name] += 1
    txn_dates_by_item[name].append(v["date"])
    if v["is_inward"]:
        inward_by_item[name] += qty
    else:
        outward_by_item[name] += qty

# Compute mismatch for every item
mismatches = []
for it in items:
    name = it["name"]
    opening = it["opening_balance"]
    closing = it["closing_balance"]
    inward = inward_by_item.get(name, 0)
    outward = outward_by_item.get(name, 0)
    computed_closing = opening + inward - outward
    diff = computed_closing - closing
    mismatches.append({
        "name": name,
        "category": it.get("category") or "UNCATEGORIZED",
        "opening": opening,
        "inward": inward,
        "outward": outward,
        "computed_closing": computed_closing,
        "actual_closing": closing,
        "diff": diff,
        "abs_diff": abs(diff),
        "txn_count": txn_count_by_item.get(name, 0),
    })

# Sort by abs_diff descending
mismatches.sort(key=lambda x: x["abs_diff"], reverse=True)


# ──────────────────────────────────────────────────────────────────
# 1. Top 20 mismatched items with fuzzy name search
# ──────────────────────────────────────────────────────────────────
section("1. TOP 20 MISMATCHED ITEMS (by abs(diff))")

def find_similar_names(target_name, category, threshold=0.55):
    """Find items in the same category with similar names (fuzzy match)."""
    candidates = []
    cat_items = items_by_category.get(category, [])
    for other in cat_items:
        other_name = other["name"]
        if other_name == target_name:
            continue
        ratio = SequenceMatcher(None, target_name.upper(), other_name.upper()).ratio()
        if ratio >= threshold:
            candidates.append((other_name, ratio, other))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:5]


def extract_key_tokens(name):
    """Extract significant tokens from a name for substring matching."""
    # Remove common prefixes and split
    import re
    tokens = re.split(r'[\s/\-_,]+', name.upper())
    # Filter short tokens and common words
    skip = {"THE", "OF", "AND", "IN", "FOR", "A", "AN", "WITH", "MM", "CM", "ML",
            "G", "KG", "PCS", "NOS", "SET", "PACK", "BOX", "X", "M2"}
    return [t for t in tokens if len(t) > 2 and t not in skip]


for i, m in enumerate(mismatches[:20]):
    print(f"\n{'─' * 80}")
    print(f"  #{i+1}: {m['name']}")
    print(f"  Category: {m['category']}")
    print(f"  Opening: {m['opening']:,.0f}  |  Inward: {m['inward']:,.0f}  |  Outward: {m['outward']:,.0f}")
    print(f"  Computed closing: {m['computed_closing']:,.0f}  |  Actual closing: {m['actual_closing']:,.0f}")
    print(f"  DIFF: {m['diff']:+,.0f}  (abs: {m['abs_diff']:,.0f})  |  Transactions: {m['txn_count']}")

    # Search for similar names in same category
    similar = find_similar_names(m["name"], m["category"])
    if similar:
        print(f"  Possible rename matches in [{m['category']}]:")
        for sname, ratio, sitem in similar:
            s_inward = inward_by_item.get(sname, 0)
            s_outward = outward_by_item.get(sname, 0)
            s_txn = txn_count_by_item.get(sname, 0)
            print(f"    -> {sname}  (similarity: {ratio:.2f})")
            print(f"       open={sitem['opening_balance']:,.0f} close={sitem['closing_balance']:,.0f}"
                  f" in={s_inward:,.0f} out={s_outward:,.0f} txns={s_txn}")
    else:
        print(f"  No similar names found in category [{m['category']}]")


# ──────────────────────────────────────────────────────────────────
# 2. Specific pair: ART ESSENTIALS TONED GREY
# ──────────────────────────────────────────────────────────────────
section("2. SPECIFIC PAIR: ART ESSENTIALS TONED GREY")

old_name = "ART ESSENTIALS TONED GREY 120 G/M2 50.8X63.5"
new_name = "AE TONED GREY50.8 CM X 63.5 CM25 SHEET"

for name in [old_name, new_name]:
    it = item_by_name.get(name)
    if it:
        inw = inward_by_item.get(name, 0)
        outw = outward_by_item.get(name, 0)
        txn = txn_count_by_item.get(name, 0)
        computed = it["opening_balance"] + inw - outw
        print(f"\n  Name: {name}")
        print(f"  Category: {it.get('category')}")
        print(f"  Opening: {it['opening_balance']:,.0f}")
        print(f"  Inward:  {inw:,.0f}   Outward: {outw:,.0f}   Txns: {txn}")
        print(f"  Computed closing: {computed:,.0f}")
        print(f"  Actual closing:   {it['closing_balance']:,.0f}")
        print(f"  Diff: {computed - it['closing_balance']:+,.0f}")
    else:
        print(f"\n  Name: {name} -- NOT FOUND in stock items!")

# Check similarity
if old_name in item_by_name and new_name in item_by_name:
    ratio = SequenceMatcher(None, old_name.upper(), new_name.upper()).ratio()
    print(f"\n  String similarity: {ratio:.3f}")
    old_tokens = set(extract_key_tokens(old_name))
    new_tokens = set(extract_key_tokens(new_name))
    shared = old_tokens & new_tokens
    print(f"  Old tokens: {old_tokens}")
    print(f"  New tokens: {new_tokens}")
    print(f"  Shared tokens: {shared}")


# ──────────────────────────────────────────────────────────────────
# 3. Items with opening > 0, closing = 0, zero transactions
#    (likely fully renamed away)
# ──────────────────────────────────────────────────────────────────
section("3. ITEMS WITH OPENING > 0, CLOSING = 0, ZERO TRANSACTIONS (renamed away?)")

renamed_away = [m for m in mismatches
                if m["opening"] > 0 and m["actual_closing"] == 0 and m["txn_count"] == 0]
print(f"\n  Count: {len(renamed_away)} items")
print(f"  (These had stock at FY start but disappeared with no transactions — strong rename signal)")

subsection("Top 20 by opening balance")
renamed_away.sort(key=lambda x: x["opening"], reverse=True)
for r in renamed_away[:20]:
    print(f"  {r['name']}")
    print(f"    Category: {r['category']}  |  Opening: {r['opening']:,.0f}")

# Also count: opening > 0, closing = 0, HAS transactions
renamed_with_txns = [m for m in mismatches
                     if m["opening"] > 0 and m["actual_closing"] == 0 and m["txn_count"] > 0]
subsection(f"Items with opening > 0, closing = 0, WITH transactions: {len(renamed_with_txns)}")
print("  (Sold down to zero OR renamed mid-FY after some transactions)")


# ──────────────────────────────────────────────────────────────────
# 4. Items with opening = 0, closing < 0 (new names, oversold)
# ──────────────────────────────────────────────────────────────────
section("4. ITEMS WITH OPENING = 0, CLOSING < 0 (new names receiving sales?)")

new_names_negative = [m for m in mismatches
                      if m["opening"] == 0 and m["actual_closing"] < 0]
print(f"\n  Count: {len(new_names_negative)} items")
print(f"  (No opening stock but closing balance is negative — sold without purchase, likely renamed TO)")

subsection("Top 20 by most negative closing")
new_names_negative.sort(key=lambda x: x["actual_closing"])
for r in new_names_negative[:20]:
    print(f"  {r['name']}")
    print(f"    Category: {r['category']}  |  Closing: {r['actual_closing']:,.0f}  |  Txns: {r['txn_count']}")

# Also: opening = 0, closing > 0, inward > 0 (new name with purchases but could be legit new item)
new_with_stock = [m for m in mismatches
                  if m["opening"] == 0 and m["actual_closing"] != 0 and m["inward"] > 0]
subsection(f"Items with opening = 0, closing != 0, with inward transactions: {len(new_with_stock)}")


# ──────────────────────────────────────────────────────────────────
# 5. Category distribution of mismatched items
# ──────────────────────────────────────────────────────────────────
section("5. CATEGORY/BRAND DISTRIBUTION OF MISMATCHES")

# Only consider items with significant mismatch (abs_diff > 1 to exclude rounding)
significant = [m for m in mismatches if m["abs_diff"] > 1]
total_mismatched = len(significant)
total_items = len(mismatches)
total_matched = total_items - total_mismatched

print(f"\n  Total items: {total_items}")
print(f"  Matched (abs_diff <= 1): {total_matched}  ({100*total_matched/total_items:.1f}%)")
print(f"  Mismatched (abs_diff > 1): {total_mismatched}  ({100*total_mismatched/total_items:.1f}%)")

# Count mismatches per category
cat_mismatch = Counter()
cat_total = Counter()
cat_total_abs_diff = defaultdict(float)

for m in mismatches:
    cat_total[m["category"]] += 1
    if m["abs_diff"] > 1:
        cat_mismatch[m["category"]] += 1
        cat_total_abs_diff[m["category"]] += m["abs_diff"]

subsection("Top 20 categories by NUMBER of mismatched items")
for cat, count in cat_mismatch.most_common(20):
    total_cat = cat_total[cat]
    pct = 100 * count / total_cat if total_cat else 0
    print(f"  {cat}: {count}/{total_cat} mismatched ({pct:.0f}%)  |  Sum abs_diff: {cat_total_abs_diff[cat]:,.0f}")

subsection("Top 20 categories by TOTAL abs_diff (magnitude)")
ranked_by_magnitude = sorted(cat_total_abs_diff.items(), key=lambda x: x[1], reverse=True)
for cat, total_diff in ranked_by_magnitude[:20]:
    mc = cat_mismatch[cat]
    tc = cat_total[cat]
    print(f"  {cat}: sum_abs_diff={total_diff:,.0f}  |  {mc}/{tc} mismatched")

# Categories where 100% of items mismatch
subsection("Categories with 100% mismatch rate (all items broken)")
perfect_mismatch = [(cat, cat_mismatch[cat], cat_total[cat])
                    for cat in cat_mismatch
                    if cat_mismatch[cat] == cat_total[cat] and cat_total[cat] >= 5]
perfect_mismatch.sort(key=lambda x: x[1], reverse=True)
for cat, mc, tc in perfect_mismatch[:20]:
    print(f"  {cat}: {mc}/{tc} items (100% mismatch)")


# ──────────────────────────────────────────────────────────────────
# 6. Overall stats summary
# ──────────────────────────────────────────────────────────────────
section("6. OVERALL MISMATCH STATISTICS")

# Items with zero diff
zero_diff = sum(1 for m in mismatches if m["abs_diff"] <= 0.01)
small_diff = sum(1 for m in mismatches if 0.01 < m["abs_diff"] <= 1)
medium_diff = sum(1 for m in mismatches if 1 < m["abs_diff"] <= 100)
large_diff = sum(1 for m in mismatches if m["abs_diff"] > 100)

print(f"\n  Zero diff (abs <= 0.01):    {zero_diff:,}  ({100*zero_diff/total_items:.1f}%)")
print(f"  Tiny diff (0.01 < abs <= 1): {small_diff:,}  ({100*small_diff/total_items:.1f}%)")
print(f"  Medium diff (1 < abs <= 100): {medium_diff:,}  ({100*medium_diff/total_items:.1f}%)")
print(f"  Large diff (abs > 100):       {large_diff:,}  ({100*large_diff/total_items:.1f}%)")

# Items with no transactions at all
no_txn = sum(1 for m in mismatches if m["txn_count"] == 0)
print(f"\n  Items with ZERO transactions: {no_txn:,}  ({100*no_txn/total_items:.1f}%)")

# Items where formula works perfectly
perfect = sum(1 for m in mismatches if m["abs_diff"] <= 0.01)
print(f"  Items where formula matches perfectly: {perfect:,}  ({100*perfect/total_items:.1f}%)")

# Items referenced in vouchers but NOT in stock_items
voucher_item_names = set(txn_count_by_item.keys())
stock_item_names = set(item_by_name.keys())
orphan_voucher_items = voucher_item_names - stock_item_names
print(f"\n  Items in vouchers but NOT in stock_items.xml: {len(orphan_voucher_items)}")
if orphan_voucher_items:
    for name in sorted(orphan_voucher_items)[:20]:
        inw = inward_by_item.get(name, 0)
        outw = outward_by_item.get(name, 0)
        print(f"    {name}  (in={inw:,.0f} out={outw:,.0f} txns={txn_count_by_item[name]})")

# Items in stock_items but never appear in vouchers
no_voucher_items = stock_item_names - voucher_item_names
print(f"\n  Items in stock_items but NEVER in vouchers: {len(no_voucher_items):,}")
# Of these, how many have non-zero opening?
no_voucher_with_opening = [item_by_name[n] for n in no_voucher_items if item_by_name[n]["opening_balance"] != 0]
print(f"    Of these, with non-zero opening: {len(no_voucher_with_opening)}")
no_voucher_with_closing = [item_by_name[n] for n in no_voucher_items if item_by_name[n]["closing_balance"] != 0]
print(f"    Of these, with non-zero closing: {len(no_voucher_with_closing)}")


# ──────────────────────────────────────────────────────────────────
# 7. Option A: Work backwards from closing balance (5 examples)
# ──────────────────────────────────────────────────────────────────
section("7. OPTION A: RECONSTRUCT STOCK POSITION WORKING BACKWARDS FROM CLOSING BALANCE")

print("""
  Strategy: Instead of opening + inward - outward, use the CLOSING balance
  from Tally (which IS correct) and replay transactions to build daily positions.

  For each day working BACKWARDS from today:
    stock[day] = stock[day+1] + outward[day] - inward[day]
  OR equivalently, FORWARD from closing:
    stock[day] = closing - sum(inward after day) + sum(outward after day)
""")

# Pick 5 items with significant transactions and a non-zero closing balance
example_candidates = [m for m in mismatches
                      if m["txn_count"] >= 10 and m["actual_closing"] != 0 and m["abs_diff"] > 1]
example_candidates.sort(key=lambda x: x["txn_count"], reverse=True)

for ex in example_candidates[:5]:
    name = ex["name"]
    closing = ex["actual_closing"]

    subsection(f"Item: {name}")
    print(f"  Category: {ex['category']}")
    print(f"  Opening: {ex['opening']:,.0f}  |  Actual Closing: {closing:,.0f}")
    print(f"  Inward: {ex['inward']:,.0f}  |  Outward: {ex['outward']:,.0f}  |  Txns: {ex['txn_count']}")
    print(f"  Formula diff: {ex['diff']:+,.0f}")
    print()

    # Collect daily transactions for this item
    daily_in = defaultdict(float)
    daily_out = defaultdict(float)
    daily_details = defaultdict(list)

    for v in vouchers:
        if v["stock_item"] != name:
            continue
        date_str = v["date"]
        qty = v["quantity"]
        if v["is_inward"]:
            daily_in[date_str] += qty
        else:
            daily_out[date_str] += qty
        daily_details[date_str].append(
            f"{'IN' if v['is_inward'] else 'OUT'} {qty:,.0f} ({v['voucher_type']}, {v['party'][:30]})"
        )

    # Get all dates sorted
    all_dates = sorted(set(list(daily_in.keys()) + list(daily_out.keys())))

    if not all_dates:
        print("  No transactions found!")
        continue

    # Build FORWARD from FY start using closing balance as anchor:
    # closing_balance = opening + total_inward - total_outward + rename_adjustment
    # Since we trust closing, work backwards:
    # position_at_end_of_day(last_date) = closing_balance (if last_date is FY end)
    # But we don't know exact FY end, so we reconstruct day by day FROM closing.

    # Forward reconstruction: start from closing, then go backwards through dates
    # stock_before_last_txn = closing - inward_on_last_day + outward_on_last_day

    print(f"  {'DATE':<12} {'IN':>8} {'OUT':>8} {'BALANCE':>10}  DETAILS")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*10}  {'-'*40}")

    # Work backwards from closing balance
    running = closing
    daily_positions = []
    for date in reversed(all_dates):
        # After this day's transactions, balance was 'running'
        end_of_day = running
        # Before this day's transactions:
        # balance_before + inward - outward = balance_after
        # balance_before = balance_after - inward + outward
        in_qty = daily_in.get(date, 0)
        out_qty = daily_out.get(date, 0)
        start_of_day = running - in_qty + out_qty
        daily_positions.append((date, in_qty, out_qty, end_of_day, start_of_day))
        running = start_of_day

    # Print forward (chronological)
    daily_positions.reverse()
    implied_opening = daily_positions[0][4] if daily_positions else closing

    print(f"  {'(implied)':12} {'':>8} {'':>8} {implied_opening:>10,.0f}  <- implied opening from backward calc")

    # Show at most 15 rows (first 8, last 7 if more)
    if len(daily_positions) <= 15:
        show = daily_positions
    else:
        show = daily_positions[:8] + [None] + daily_positions[-7:]

    for entry in show:
        if entry is None:
            print(f"  {'  ... ':^12} {'':>8} {'':>8} {'':>10}  ({len(daily_positions) - 15} more days)")
            continue
        date, in_qty, out_qty, end_bal, start_bal = entry
        details = "; ".join(daily_details.get(date, [])[:3])
        if len(daily_details.get(date, [])) > 3:
            details += f" (+{len(daily_details[date])-3} more)"
        print(f"  {date:<12} {in_qty:>8,.0f} {out_qty:>8,.0f} {end_bal:>10,.0f}  {details[:70]}")

    # Summary
    print(f"\n  Implied opening (from backward calc): {implied_opening:,.0f}")
    print(f"  Actual opening (from stock_items.xml): {ex['opening']:,.0f}")
    print(f"  Discrepancy: {ex['opening'] - implied_opening:+,.0f}")
    if abs(ex['opening'] - implied_opening) > 1:
        print(f"  -> This discrepancy likely represents a RENAME adjustment.")
        print(f"     Stock was moved to/from this item name during the FY.")


# ──────────────────────────────────────────────────────────────────
# 8. Find potential rename PAIRS by category
# ──────────────────────────────────────────────────────────────────
section("8. POTENTIAL RENAME PAIRS (opening>0/closing=0 + opening=0/closing<0 in same category)")

# For each category, find "disappeared" items and "appeared" items
pair_count = 0
for cat in sorted(items_by_category.keys()):
    cat_items = items_by_category[cat]
    if len(cat_items) < 2:
        continue

    # Disappeared: had opening, now zero closing, few/no transactions
    disappeared = []
    for it in cat_items:
        name = it["name"]
        if it["opening_balance"] > 0 and it["closing_balance"] == 0 and txn_count_by_item.get(name, 0) <= 2:
            disappeared.append(it)

    # Appeared: no opening, has closing or transactions
    appeared = []
    for it in cat_items:
        name = it["name"]
        if it["opening_balance"] == 0 and (it["closing_balance"] != 0 or txn_count_by_item.get(name, 0) > 0):
            appeared.append(it)

    if not disappeared or not appeared:
        continue

    # Try to match them by fuzzy name
    for old_item in disappeared:
        old_name = old_item["name"]
        best_match = None
        best_ratio = 0
        for new_item in appeared:
            new_name_val = new_item["name"]
            ratio = SequenceMatcher(None, old_name.upper(), new_name_val.upper()).ratio()
            if ratio > best_ratio and ratio > 0.45:
                best_ratio = ratio
                best_match = new_item

        if best_match:
            pair_count += 1
            if pair_count <= 30:  # Show first 30 pairs
                new_nm = best_match["name"]
                inw = inward_by_item.get(new_nm, 0)
                outw = outward_by_item.get(new_nm, 0)
                print(f"\n  [{cat}]")
                print(f"    OLD: {old_name}")
                print(f"      opening={old_item['opening_balance']:,.0f}  closing={old_item['closing_balance']:,.0f}"
                      f"  txns={txn_count_by_item.get(old_name, 0)}")
                print(f"    NEW: {new_nm}  (similarity: {best_ratio:.2f})")
                print(f"      opening={best_match['opening_balance']:,.0f}  closing={best_match['closing_balance']:,.0f}"
                      f"  in={inw:,.0f}  out={outw:,.0f}  txns={txn_count_by_item.get(new_nm, 0)}")

print(f"\n  Total potential rename pairs found: {pair_count}")


# ──────────────────────────────────────────────────────────────────
# Final summary
# ──────────────────────────────────────────────────────────────────
section("SUMMARY & RECOMMENDATIONS")

# Recount key numbers
items_with_opening_no_closing_no_txn = len(renamed_away)
items_no_opening_negative_closing = len(new_names_negative)

print(f"""
  KEY FINDINGS:
  - Total items: {total_items:,}
  - Formula matches perfectly: {perfect:,} ({100*perfect/total_items:.1f}%)
  - Formula mismatches: {total_mismatched:,} ({100*total_mismatched/total_items:.1f}%)

  RENAME EVIDENCE:
  - Items that "disappeared" (opening>0, closing=0, no txns): {items_with_opening_no_closing_no_txn:,}
  - Items that "appeared" (opening=0, closing<0): {items_no_opening_negative_closing:,}
  - Potential rename pairs (fuzzy matched): {pair_count}
  - Items in vouchers but NOT in stock_items: {len(orphan_voucher_items)}

  RECOMMENDATION:
  If closing_balance is authoritative (Tally computes it correctly even across renames):
    -> Use Option A: work backwards from closing balance
    -> opening_balance is UNRELIABLE for renamed items
    -> The backward-reconstructed "implied opening" will differ from the XML opening
       by exactly the rename adjustment amount
""")

print("\nDone.")
