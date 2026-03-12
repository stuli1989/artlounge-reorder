"""
Deep investigation of dedup edge cases and channel classification in Tally data.

Builds on findings from analyze_tally_data.py to propose concrete rules.
"""
import sys
import os
from collections import Counter, defaultdict
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

# Ensure src/ is on the path so parser imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from extraction.xml_parser import parse_ledgers, parse_vouchers

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_responses")
REPORT_FILE = os.path.join(os.path.dirname(__file__), "dedup_channels_report.txt")

_output_lines = []


def out(text=""):
    _output_lines.append(text)
    print(text)


def section(title):
    out("")
    out("=" * 90)
    out(f"  {title}")
    out("=" * 90)


def subsection(title):
    out("")
    out(f"--- {title} ---")


# ──────────────────────────────────────────────────────────────────
# Load data
# ──────────────────────────────────────────────────────────────────
def load_data():
    out("Loading XML files...")

    with open(os.path.join(SAMPLE_DIR, "ledgers.xml"), "rb") as f:
        ledgers = parse_ledgers(f.read())
    out(f"  Ledgers:          {len(ledgers)}")

    out("  Loading vouchers (190 MB, may take ~30s)...")
    with open(os.path.join(SAMPLE_DIR, "vouchers_full_fy.xml"), "rb") as f:
        vouchers = parse_vouchers(f.read())
    out(f"  Voucher line items: {len(vouchers)}")

    return ledgers, vouchers


# ══════════════════════════════════════════════════════════════════
# SECTION 1: DEDUP DEEP DIVE
# ══════════════════════════════════════════════════════════════════
def dedup_deep_dive(vouchers):
    section("1. DEDUP DEEP DIVE — ALL 59 DUPLICATE GROUPS")

    # Build groups under current dedup key
    groups = defaultdict(list)
    for v in vouchers:
        key = (v["date"], v["voucher_number"], v["stock_item"], v["quantity"], v["is_inward"])
        groups[key].append(v)

    dup_groups = {k: rows for k, rows in groups.items() if len(rows) > 1}
    out(f"Total duplicate groups: {len(dup_groups)}")
    out(f"Total excess rows (would be removed): {sum(len(r) - 1 for r in dup_groups.values())}")

    # Check: do duplicates ALWAYS have identical party, rate, amount?
    subsection("1a. Are duplicate rows truly identical?")
    identical_count = 0
    differ_count = 0
    differ_details = []

    for key, rows in sorted(dup_groups.items(), key=lambda x: len(x[1]), reverse=True):
        # Check if all rows have the same party, rate, amount, master_id
        parties = set(r["party"] for r in rows)
        rates = set(r["rate"] for r in rows)
        amounts = set(r["amount"] for r in rows)
        master_ids = set(r["tally_master_id"] for r in rows)

        all_same = len(parties) == 1 and len(rates) == 1 and len(amounts) == 1 and len(master_ids) == 1
        if all_same:
            identical_count += 1
        else:
            differ_count += 1
            differ_details.append((key, rows, parties, rates, amounts, master_ids))

    out(f"Groups where ALL fields are identical: {identical_count}")
    out(f"Groups where fields DIFFER: {differ_count}")

    if differ_details:
        subsection("1b. GROUPS WITH DIFFERING FIELDS (these need special attention)")
        for key, rows, parties, rates, amounts, master_ids in differ_details:
            out(f"\n  Key: date={key[0]}, vnum={key[1]}, item={key[2]}, qty={key[3]}, inward={key[4]}")
            out(f"  Count: {len(rows)}")
            out(f"  Parties: {parties}")
            out(f"  Rates: {rates}")
            out(f"  Amounts: {amounts}")
            out(f"  Master IDs: {master_ids}")
            for i, r in enumerate(rows):
                out(f"    Row {i+1}: party={r['party']}, rate={r['rate']}, amount={r['amount']}, master_id={r['tally_master_id']}")
    else:
        out("\nAll duplicate groups have IDENTICAL data in every field — safe to dedup by dropping extras.")

    subsection("1c. FULL DETAIL OF ALL 59 DUPLICATE GROUPS")
    for idx, (key, rows) in enumerate(
        sorted(dup_groups.items(), key=lambda x: len(x[1]), reverse=True), 1
    ):
        out(f"\n  GROUP {idx}/{len(dup_groups)}: {len(rows)} rows")
        out(f"  Key: date={key[0]}, vnum={key[1]}, item={key[2]}, qty={key[3]}, inward={key[4]}")
        for i, r in enumerate(rows):
            out(f"    Row {i+1}: party={r['party']}, rate={r['rate']}, amount={r['amount']}, "
                f"voucher_type={r['voucher_type']}, master_id={r['tally_master_id']}")

    # Analyze by voucher type: which types produce duplicates?
    subsection("1d. Which voucher types produce duplicates?")
    type_dup_counts = Counter()
    for key, rows in dup_groups.items():
        vtypes = set(r["voucher_type"] for r in rows)
        for vt in vtypes:
            type_dup_counts[vt] += 1
    for vt, cnt in type_dup_counts.most_common():
        out(f"  {vt}: {cnt} duplicate groups")

    # Analyze by party: which parties produce duplicates?
    subsection("1e. Which parties produce duplicates?")
    party_dup_counts = Counter()
    for key, rows in dup_groups.items():
        parties = set(r["party"] for r in rows)
        for p in parties:
            party_dup_counts[p] += 1
    for p, cnt in party_dup_counts.most_common():
        out(f"  {p}: {cnt} duplicate groups")

    # Propose dedup strategy
    subsection("1f. PROPOSED DEDUP STRATEGY")
    out("Based on the analysis above:")
    if differ_count == 0:
        out("  - All duplicates are PERFECTLY IDENTICAL rows (same party, rate, amount, master_id)")
        out("  - Strategy: Simple DROP DUPLICATES on (date, voucher_number, stock_item, qty, is_inward)")
        out("  - This is safe — no data is lost because the duplicates carry no extra info")
        out("  - Alternative: could also dedup on (tally_master_id, stock_item) for voucher-level uniqueness")
    else:
        out("  - Some duplicates have differing fields — need row-level inspection or master_id-based dedup")

    # Check: would master_id + stock_item be a BETTER dedup key?
    subsection("1g. master_id + stock_item as alternative dedup key")
    alt_groups = defaultdict(list)
    for v in vouchers:
        alt_key = (v["tally_master_id"], v["stock_item"])
        alt_groups[alt_key].append(v)
    alt_dups = {k: rows for k, rows in alt_groups.items() if len(rows) > 1}
    out(f"Duplicate groups under (master_id, stock_item): {len(alt_dups)}")

    # Are there cases where master_id + stock_item groups LEGITIMATE different rows?
    legit_different = 0
    for key, rows in alt_dups.items():
        # If rows differ in date or voucher_number, they might be legit
        dates = set(r["date"] for r in rows)
        vnums = set(r["voucher_number"] for r in rows)
        if len(dates) > 1 or len(vnums) > 1:
            legit_different += 1
    out(f"Groups where date or voucher_number differs (possibly legit): {legit_different}")
    out(f"Groups that are pure duplicates: {len(alt_dups) - legit_different}")

    if legit_different > 0:
        out("\n  WARNING: master_id + stock_item merges rows from different vouchers!")
        out("  The current key (date, vnum, stock_item, qty, is_inward) is SAFER.")

    # What about using master_id + stock_item + voucher_number?
    subsection("1h. master_id + stock_item + voucher_number as key")
    alt2_groups = defaultdict(list)
    for v in vouchers:
        alt2_key = (v["tally_master_id"], v["stock_item"], v["voucher_number"])
        alt2_groups[alt2_key].append(v)
    alt2_dups = {k: rows for k, rows in alt2_groups.items() if len(rows) > 1}
    out(f"Duplicate groups under (master_id, stock_item, voucher_number): {len(alt2_dups)}")
    out(f"Total excess rows: {sum(len(r) - 1 for r in alt2_dups.values())}")


# ══════════════════════════════════════════════════════════════════
# SECTION 2: CHANNEL CLASSIFICATION DEEP DIVE
# ══════════════════════════════════════════════════════════════════
def channel_deep_dive(vouchers, ledgers):
    section("2. CHANNEL CLASSIFICATION DEEP DIVE")

    ledger_parents = {l["name"]: l["parent"] for l in ledgers}

    # ──── Sales-Tally breakdown ────
    subsection("2a. Sales-Tally vouchers — party breakdown (by line item count)")
    sales_tally = [v for v in vouchers if v["voucher_type"] == "Sales-Tally"]
    st_party_counts = Counter(v["party"] for v in sales_tally)
    out(f"Total Sales-Tally line items: {len(sales_tally)}")
    out(f"Unique parties: {len(st_party_counts)}")

    # Categorize
    magento_count = st_party_counts.get("MAGENTO2", 0)
    ali_count = st_party_counts.get("Art Lounge India", 0)
    other_wholesale = {p: c for p, c in st_party_counts.items() if p not in ("MAGENTO2", "Art Lounge India")}
    out(f"\n  MAGENTO2 (online): {magento_count} line items ({magento_count/len(sales_tally)*100:.1f}%)")
    out(f"  Art Lounge India (internal): {ali_count} line items ({ali_count/len(sales_tally)*100:.1f}%)")
    out(f"  Other wholesale parties: {sum(other_wholesale.values())} line items ({sum(other_wholesale.values())/len(sales_tally)*100:.1f}%)")
    out(f"  Number of other wholesale parties: {len(other_wholesale)}")

    out(f"\n  ALL Sales-Tally parties (full list):")
    for p, cnt in st_party_counts.most_common():
        parent = ledger_parents.get(p, "?")
        out(f"    {cnt:>6}  {p}  [ledger parent: {parent}]")

    # ──── Sales breakdown ────
    subsection("2b. Sales vouchers — party breakdown")
    sales = [v for v in vouchers if v["voucher_type"] == "Sales"]
    s_party_counts = Counter(v["party"] for v in sales)
    out(f"Total Sales line items: {len(sales)}")
    out(f"Unique parties: {len(s_party_counts)}")

    ali_sales = s_party_counts.get("Art Lounge India", 0)
    other_sales = {p: c for p, c in s_party_counts.items() if p != "Art Lounge India"}
    out(f"\n  Art Lounge India (internal): {ali_sales} line items ({ali_sales/len(sales)*100:.1f}%)")
    out(f"  Other parties: {sum(other_sales.values())} line items ({sum(other_sales.values())/len(sales)*100:.1f}%)")

    out(f"\n  ALL Sales parties (full list):")
    for p, cnt in s_party_counts.most_common():
        parent = ledger_parents.get(p, "?")
        out(f"    {cnt:>6}  {p}  [ledger parent: {parent}]")

    # ──── Purchase breakdown ────
    subsection("2c. Purchase vouchers — party breakdown")
    purchase = [v for v in vouchers if v["voucher_type"] == "Purchase"]
    pu_party_counts = Counter(v["party"] for v in purchase)
    out(f"Total Purchase line items: {len(purchase)}")
    out(f"Unique parties: {len(pu_party_counts)}")

    alip_count = pu_party_counts.get("Art Lounge India - Purchase", 0)
    other_purchase = {p: c for p, c in pu_party_counts.items() if p != "Art Lounge India - Purchase"}
    out(f"\n  Art Lounge India - Purchase (internal): {alip_count} line items ({alip_count/len(purchase)*100:.1f}%)")
    out(f"  Other suppliers: {sum(other_purchase.values())} line items ({sum(other_purchase.values())/len(purchase)*100:.1f}%)")

    out(f"\n  ALL Purchase parties (full list):")
    for p, cnt in pu_party_counts.most_common():
        parent = ledger_parents.get(p, "?")
        out(f"    {cnt:>6}  {p}  [ledger parent: {parent}]")

    # ──── Sales Store breakdown ────
    subsection("2d. Sales Store vouchers — ALL unique parties")
    sales_store = [v for v in vouchers if v["voucher_type"] == "Sales Store"]
    ss_party_counts = Counter(v["party"] for v in sales_store)
    out(f"Total Sales Store line items: {len(sales_store)}")
    out(f"Unique parties: {len(ss_party_counts)}")

    out(f"\n  ALL Sales Store parties (full list):")
    for p, cnt in ss_party_counts.most_common():
        parent = ledger_parents.get(p, "?")
        out(f"    {cnt:>6}  {p}  [ledger parent: {parent}]")

    # ──── Sales-ALKG breakdown ────
    subsection("2e. Sales-ALKG vouchers — ALL details")
    sales_alkg = [v for v in vouchers if v["voucher_type"] == "Sales-ALKG"]
    out(f"Total Sales-ALKG line items: {len(sales_alkg)}")

    alkg_party_counts = Counter(v["party"] for v in sales_alkg)
    out(f"Unique parties: {len(alkg_party_counts)}")
    out(f"\n  ALL Sales-ALKG parties:")
    for p, cnt in alkg_party_counts.most_common():
        parent = ledger_parents.get(p, "?")
        out(f"    {cnt:>6}  {p}  [ledger parent: {parent}]")

    out(f"\n  ALL Sales-ALKG line items:")
    for v in sales_alkg:
        out(f"    date={v['date']} party={v['party']} item={v['stock_item']} "
            f"qty={v['quantity']} rate={v['rate']} amount={v['amount']} vnum={v['voucher_number']}")

    # ──── Sales-Amazon & Sales-Flipkart ────
    subsection("2f. Sales-Amazon & Sales-Flipkart — parties")
    for vtype in ["Sales-Amazon", "Sales-Flipkart"]:
        items = [v for v in vouchers if v["voucher_type"] == vtype]
        pc = Counter(v["party"] for v in items)
        out(f"\n  {vtype}: {len(items)} line items, {len(pc)} unique parties")
        for p, cnt in pc.most_common():
            parent = ledger_parents.get(p, "?")
            out(f"    {cnt:>6}  {p}  [ledger parent: {parent}]")


# ══════════════════════════════════════════════════════════════════
# SECTION 3: INTERNAL TRANSACTION ANALYSIS
# ══════════════════════════════════════════════════════════════════
def internal_analysis(vouchers, ledgers):
    section("3. INTERNAL TRANSACTION ANALYSIS")

    ledger_parents = {l["name"]: l["parent"] for l in ledgers}

    # Find all parties containing "Art Lounge"
    subsection("3a. All parties containing 'Art Lounge'")
    art_lounge_parties = set()
    for v in vouchers:
        if "art lounge" in v["party"].lower():
            art_lounge_parties.add(v["party"])

    out(f"Parties containing 'Art Lounge': {len(art_lounge_parties)}")
    for p in sorted(art_lounge_parties):
        items = [v for v in vouchers if v["party"] == p]
        vtypes = Counter(v["voucher_type"] for v in items)
        parent = ledger_parents.get(p, "?")
        out(f"\n  Party: '{p}'  [ledger parent: {parent}]")
        out(f"  Total line items: {len(items)}")
        out(f"  Voucher type breakdown:")
        for vt, cnt in vtypes.most_common():
            out(f"    {cnt:>6}  {vt}")

    # Are internal transfers always between specific voucher types?
    subsection("3b. Internal transfer patterns")
    ali = [v for v in vouchers if v["party"] == "Art Lounge India"]
    alip = [v for v in vouchers if v["party"] == "Art Lounge India - Purchase"]

    out(f"\n  'Art Lounge India' transactions:")
    ali_vtypes = Counter(v["voucher_type"] for v in ali)
    ali_directions = Counter(v["is_inward"] for v in ali)
    for vt, cnt in ali_vtypes.most_common():
        inward = sum(1 for v in ali if v["voucher_type"] == vt and v["is_inward"])
        outward = sum(1 for v in ali if v["voucher_type"] == vt and not v["is_inward"])
        out(f"    {vt}: {cnt} items (inward={inward}, outward={outward})")
    out(f"  Overall direction: inward={ali_directions.get(True, 0)}, outward={ali_directions.get(False, 0)}")

    out(f"\n  'Art Lounge India - Purchase' transactions:")
    alip_vtypes = Counter(v["voucher_type"] for v in alip)
    alip_directions = Counter(v["is_inward"] for v in alip)
    for vt, cnt in alip_vtypes.most_common():
        inward = sum(1 for v in alip if v["voucher_type"] == vt and v["is_inward"])
        outward = sum(1 for v in alip if v["voucher_type"] == vt and not v["is_inward"])
        out(f"    {vt}: {cnt} items (inward={inward}, outward={outward})")
    out(f"  Overall direction: inward={alip_directions.get(True, 0)}, outward={alip_directions.get(False, 0)}")

    # Do Art Lounge India "Sales-Tally" entries correspond to Art Lounge India - Purchase "Purchase" entries?
    subsection("3c. Do internal transfers balance out? (same items, opposite direction)")
    ali_sales = [v for v in ali if v["voucher_type"] in ("Sales-Tally", "Sales")]
    alip_purchases = [v for v in alip if v["voucher_type"] == "Purchase"]

    ali_items_qtys = defaultdict(float)
    for v in ali_sales:
        ali_items_qtys[v["stock_item"]] += v["quantity"]

    alip_items_qtys = defaultdict(float)
    for v in alip_purchases:
        alip_items_qtys[v["stock_item"]] += v["quantity"]

    all_items = set(ali_items_qtys.keys()) | set(alip_items_qtys.keys())
    balanced = 0
    unbalanced = 0
    only_sale = 0
    only_purchase = 0
    for item in all_items:
        sold = ali_items_qtys.get(item, 0)
        purchased = alip_items_qtys.get(item, 0)
        if abs(sold - purchased) < 0.01:
            balanced += 1
        elif sold > 0 and purchased > 0:
            unbalanced += 1
        elif sold > 0:
            only_sale += 1
        else:
            only_purchase += 1

    out(f"  Items in internal sales: {len(ali_items_qtys)}")
    out(f"  Items in internal purchases: {len(alip_items_qtys)}")
    out(f"  Items with matching qty (balanced): {balanced}")
    out(f"  Items with both but different qty (unbalanced): {unbalanced}")
    out(f"  Items only in sale side: {only_sale}")
    out(f"  Items only in purchase side: {only_purchase}")

    # Should internal transfers be excluded completely or just from velocity?
    subsection("3d. RECOMMENDATION: How to handle internal transfers")
    total_internal = len(ali) + len(alip)
    total_vouchers = len(vouchers)
    out(f"  Internal line items: {total_internal} ({total_internal/total_vouchers*100:.1f}% of all)")
    out(f"  Art Lounge India (sale side): {len(ali)} items")
    out(f"  Art Lounge India - Purchase (purchase side): {len(alip)} items")
    out("")
    out("  RECOMMENDATION:")
    out("  - EXCLUDE from velocity calculation (they don't represent real demand)")
    out("  - EXCLUDE from balance calculation IF they are balanced (net zero effect)")
    out("  - If including in balance: include BOTH sides so they cancel out")
    out("  - Safest approach: mark channel='internal', skip in velocity, include in balance")
    out("    because Tally's closing balance already accounts for them")


# ══════════════════════════════════════════════════════════════════
# SECTION 4: COMPLETE CHANNEL CLASSIFICATION RULESET
# ══════════════════════════════════════════════════════════════════
def propose_channel_rules(vouchers, ledgers):
    section("4. PROPOSED COMPLETE CHANNEL CLASSIFICATION RULESET")

    ledger_parents = {l["name"]: l["parent"] for l in ledgers}

    # Gather all unique (party, voucher_type) combos and their line item counts
    party_vtype_counts = defaultdict(lambda: defaultdict(int))
    for v in vouchers:
        party_vtype_counts[v["party"]][v["voucher_type"]] += 1

    all_parties = set(v["party"] for v in vouchers if v["party"])
    out(f"Total unique parties in vouchers: {len(all_parties)}")

    # ──── Rule 1: Voucher-type-based auto-classification ────
    subsection("Rule 1: Voucher-type-based auto-classification")
    type_rules = {
        "Sales-Flipkart": "online",
        "Sales-Amazon": "online",
        "Sales-ALKG": "online",       # unclear but seems to be an online/external channel
        "Sales Store": "store",
        "Physical Stock": "ignore",    # balance adjustment only
    }
    out("  These voucher types auto-classify regardless of party:")
    for vtype, channel in type_rules.items():
        items = [v for v in vouchers if v["voucher_type"] == vtype]
        out(f"    {vtype} -> {channel} ({len(items)} line items)")

    type_classified_parties = set()
    for v in vouchers:
        if v["voucher_type"] in type_rules:
            type_classified_parties.add(v["party"])

    # ──── Rule 2: Party-name-based exact match ────
    subsection("Rule 2: Party-name-based exact match")
    party_rules = {
        "MAGENTO2": "online",
        "Art Lounge India": "internal",
        "Art Lounge India - Purchase": "internal",
    }
    out("  Exact party name matches:")
    for party, channel in party_rules.items():
        items = [v for v in vouchers if v["party"] == party]
        out(f"    '{party}' -> {channel} ({len(items)} line items)")

    party_classified = set(party_rules.keys())

    # ──── Rule 3: Ledger-parent-based rules ────
    subsection("Rule 3: Ledger-parent-based rules")
    out("  Sundry Creditors -> supplier (for Purchase vouchers)")
    out("  Sundry Debtors -> wholesale (for Sales-Tally/Sales vouchers, AFTER removing online/internal)")

    # Count how many Sundry Creditor parties appear in Purchase vouchers
    creditor_parties = {p for p in all_parties if ledger_parents.get(p) == "Sundry Creditors"}
    debtor_parties = {p for p in all_parties if ledger_parents.get(p) == "Sundry Debtors"}
    out(f"  Sundry Creditor parties in vouchers: {len(creditor_parties)}")
    out(f"  Sundry Debtor parties in vouchers: {len(debtor_parties)}")

    # ──── Rule 4: Counter Collection parties ────
    subsection("Rule 4: Counter Collection parties (Sales Store walk-ins)")
    counter_parties = {p for p in all_parties if "counter collection" in p.lower()}
    out(f"  Counter Collection parties: {counter_parties}")
    out("  These are walk-in cash/card/QR payments — classified as 'store'")

    # ──── Now apply all rules and count unclassified ────
    subsection("APPLYING ALL RULES — Classification Result")

    classified = {}  # party -> channel
    classification_reasons = {}  # party -> reason

    for party in all_parties:
        if not party:
            continue

        # Rule 2: exact match first
        if party in party_rules:
            classified[party] = party_rules[party]
            classification_reasons[party] = f"exact_match -> {party_rules[party]}"
            continue

        # Check voucher types this party appears in
        vtypes = set(party_vtype_counts[party].keys())

        # Rule 1: if party ONLY appears in auto-classified voucher types
        auto_types = vtypes & set(type_rules.keys())
        non_auto_types = vtypes - set(type_rules.keys())

        if auto_types and not non_auto_types:
            # Party only appears in auto-classified types
            channels = set(type_rules[vt] for vt in auto_types)
            if len(channels) == 1:
                classified[party] = channels.pop()
                classification_reasons[party] = f"vtype_only ({auto_types}) -> {classified[party]}"
                continue

        # Counter Collection -> store
        if "counter collection" in party.lower():
            classified[party] = "store"
            classification_reasons[party] = "counter_collection -> store"
            continue

        # Rule 3: ledger parent
        lp = ledger_parents.get(party, "")
        if lp == "Sundry Creditors":
            classified[party] = "supplier"
            classification_reasons[party] = f"ledger_parent=Sundry Creditors -> supplier"
            continue

        if lp == "Sundry Debtors":
            # Check if it's a wholesale customer (appears in Sales-Tally or Sales)
            if "Sales-Tally" in vtypes or "Sales" in vtypes:
                classified[party] = "wholesale"
                classification_reasons[party] = f"ledger_parent=Sundry Debtors + sales_vtype -> wholesale"
                continue

        # Credit Note / Debit Note parties — check their ledger parent
        if vtypes <= {"Credit Note", "Debit Note"}:
            if lp == "Sundry Debtors":
                classified[party] = "wholesale"  # return from wholesale customer
                classification_reasons[party] = f"credit/debit_note + Sundry Debtors -> wholesale"
            elif lp == "Sundry Creditors":
                classified[party] = "supplier"
                classification_reasons[party] = f"credit/debit_note + Sundry Creditors -> supplier"
            else:
                classified[party] = "unclassified"
                classification_reasons[party] = f"credit/debit_note + unknown parent '{lp}'"
            continue

        # Fallback
        classified[party] = "unclassified"
        classification_reasons[party] = f"no_rule_matched (vtypes={vtypes}, ledger_parent='{lp}')"

    # Summary
    channel_summary = Counter(classified.values())
    out(f"\n  Classification summary:")
    for channel, cnt in channel_summary.most_common():
        out(f"    {channel}: {cnt} parties")

    out(f"\n  Total classified: {sum(cnt for ch, cnt in channel_summary.items() if ch != 'unclassified')}")
    out(f"  Unclassified: {channel_summary.get('unclassified', 0)}")

    # Show unclassified parties
    unclassified = [p for p, ch in classified.items() if ch == "unclassified"]
    if unclassified:
        out(f"\n  UNCLASSIFIED PARTIES ({len(unclassified)}):")
        for p in sorted(unclassified):
            vtypes = party_vtype_counts[p]
            lp = ledger_parents.get(p, "?")
            total = sum(vtypes.values())
            out(f"    '{p}' — ledger_parent='{lp}', {total} line items, vtypes={dict(vtypes)}")

    # Line-item-level classification summary
    subsection("LINE ITEM LEVEL CLASSIFICATION")
    channel_line_items = Counter()
    unclassified_line_items = 0
    for v in vouchers:
        party = v["party"]
        vtype = v["voucher_type"]

        # Type-based override
        if vtype in type_rules:
            channel_line_items[type_rules[vtype]] += 1
        elif party in classified:
            channel_line_items[classified[party]] += 1
        else:
            channel_line_items["unclassified"] += 1
            unclassified_line_items += 1

    out(f"\n  Line item classification:")
    for channel, cnt in channel_line_items.most_common():
        pct = cnt / len(vouchers) * 100
        out(f"    {channel}: {cnt} line items ({pct:.1f}%)")

    # ──── Full ruleset summary ────
    subsection("COMPLETE RULESET SUMMARY (in priority order)")
    out("""
  PRIORITY 1 — Voucher Type Auto-Classification:
    Sales-Flipkart    -> online
    Sales-Amazon      -> online
    Sales-ALKG        -> online (external sales channel)
    Sales Store       -> store
    Physical Stock    -> ignore (balance adjustment only, no velocity)

  PRIORITY 2 — Party Name Exact Match:
    MAGENTO2                    -> online
    Art Lounge India            -> internal
    Art Lounge India - Purchase -> internal

  PRIORITY 3 — Party Name Pattern Match:
    *Counter Collection*        -> store

  PRIORITY 4 — Ledger Parent + Voucher Type:
    Sundry Creditors            -> supplier
    Sundry Debtors + (Sales-Tally or Sales) -> wholesale
    Sundry Debtors + Credit/Debit Note      -> wholesale (returns)
    Sundry Creditors + Credit/Debit Note    -> supplier (returns)

  PRIORITY 5 — Fallback:
    Everything else             -> unclassified (flag for manual review)

  VELOCITY RULES:
    - wholesale, online, store  -> count toward velocity (real demand)
    - supplier, internal        -> exclude from velocity
    - ignore (Physical Stock)   -> exclude from velocity
    - Credit Note / Debit Note  -> exclude from velocity (returns)

  BALANCE RULES:
    - All channels affect balance (including internal)
    - Physical Stock affects balance (stock adjustment)
    - Credit Notes are inward (returned goods)
    - Debit Notes are outward
    """)

    # Show which parties fall into each channel
    subsection("PARTIES BY CHANNEL (for reference)")
    channel_parties = defaultdict(list)
    for p, ch in classified.items():
        channel_parties[ch].append(p)

    for ch in ["online", "wholesale", "store", "supplier", "internal", "ignore", "unclassified"]:
        parties = sorted(channel_parties.get(ch, []))
        out(f"\n  {ch.upper()} ({len(parties)} parties):")
        for p in parties:
            vtypes = party_vtype_counts[p]
            total = sum(vtypes.values())
            out(f"    {p} ({total} line items)")


# ──────────────────────────────────────────────────────────────────
# SECTION 5: CROSS-CUTTING EDGE CASES
# ──────────────────────────────────────────────────────────────────
def edge_cases(vouchers, ledgers):
    section("5. CROSS-CUTTING EDGE CASES")

    ledger_parents = {l["name"]: l["parent"] for l in ledgers}

    # Parties that appear in MULTIPLE voucher types
    subsection("5a. Parties appearing in multiple voucher types")
    party_vtypes = defaultdict(set)
    for v in vouchers:
        if v["party"]:
            party_vtypes[v["party"]].add(v["voucher_type"])

    multi_type = {p: vtypes for p, vtypes in party_vtypes.items() if len(vtypes) > 1}
    out(f"Parties appearing in multiple voucher types: {len(multi_type)}")
    for p, vtypes in sorted(multi_type.items(), key=lambda x: len(x[1]), reverse=True):
        lp = ledger_parents.get(p, "?")
        items_per_type = {vt: sum(1 for v in vouchers if v["party"] == p and v["voucher_type"] == vt) for vt in vtypes}
        out(f"  {p} [parent={lp}]: {items_per_type}")

    # Empty party names
    subsection("5b. Vouchers with empty party name")
    empty_party = [v for v in vouchers if not v["party"]]
    out(f"Line items with empty party: {len(empty_party)}")
    if empty_party:
        ep_vtypes = Counter(v["voucher_type"] for v in empty_party)
        out(f"  By voucher type: {dict(ep_vtypes)}")
        out(f"  First 10 examples:")
        for v in empty_party[:10]:
            out(f"    date={v['date']} vtype={v['voucher_type']} vnum={v['voucher_number']} "
                f"item={v['stock_item']} qty={v['quantity']}")

    # Parties in vouchers but NOT in ledger list
    subsection("5c. Parties in vouchers but NOT in ledger master")
    voucher_parties = set(v["party"] for v in vouchers if v["party"])
    ledger_names = set(l["name"] for l in ledgers)
    missing_from_ledger = voucher_parties - ledger_names
    out(f"Parties in vouchers but missing from ledger master: {len(missing_from_ledger)}")
    for p in sorted(missing_from_ledger):
        items = [v for v in vouchers if v["party"] == p]
        vtypes = Counter(v["voucher_type"] for v in items)
        out(f"  '{p}' — {len(items)} line items, vtypes={dict(vtypes)}")


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────
def main():
    out("=" * 90)
    out("  DEDUP & CHANNEL CLASSIFICATION DEEP INVESTIGATION")
    out(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out("=" * 90)

    ledgers, vouchers = load_data()

    dedup_deep_dive(vouchers)
    channel_deep_dive(vouchers, ledgers)
    internal_analysis(vouchers, ledgers)
    propose_channel_rules(vouchers, ledgers)
    edge_cases(vouchers, ledgers)

    section("INVESTIGATION COMPLETE")
    out(f"Report saved to: {REPORT_FILE}")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(_output_lines))


if __name__ == "__main__":
    main()
