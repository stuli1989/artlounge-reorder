"""
Party classification system — auto-classifies parties into channels
using a 5-priority ruleset derived from data analysis.

Priority 1: Voucher type auto-classification (Sales-Flipkart -> online, etc.)
Priority 2: Party name exact match (MAGENTO2 -> online, Art Lounge India -> internal)
Priority 3: Party name pattern match (*Counter Collection* -> store)
Priority 4: Ledger parent group (Sundry Creditors -> supplier, Sundry Debtors -> wholesale)
Priority 5: Fallback -> unclassified
"""
import csv
import os
from datetime import datetime

# Priority 2: Exact party name matches
EXACT_PARTY_RULES = {
    "MAGENTO2": "online",
    "AMAZON_IN_API": "online",
    "FLIPKART": "online",
    "Art Lounge India": "internal",
    "Art Lounge India - Purchase": "internal",
}

# Priority 3: Pattern matches (case-insensitive substring)
PATTERN_RULES = [
    ("Counter Collection", "store"),
]

# Priority 4: Ledger parent group rules
PARENT_RULES = {
    "Sundry Creditors": "supplier",
    "Sundry Debtors": "wholesale",
}

VALID_CHANNELS = {"supplier", "wholesale", "online", "store", "internal", "ignore", "unclassified"}


def classify_party(party_name: str, ledger_parent: str = None) -> tuple[str, str]:
    """
    Classify a single party into a channel.

    Returns (channel, confidence) tuple.
    """
    # Priority 2: Exact match
    if party_name in EXACT_PARTY_RULES:
        return EXACT_PARTY_RULES[party_name], "high"

    # Priority 3: Pattern match
    name_upper = party_name.upper()
    for pattern, channel in PATTERN_RULES:
        if pattern.upper() in name_upper:
            return channel, "high"

    # Priority 4: Ledger parent
    if ledger_parent in PARENT_RULES:
        return PARENT_RULES[ledger_parent], "medium"

    # Priority 5: Fallback
    return "unclassified", "low"


def classify_transaction_channel(voucher_type: str, party_name: str, party_channel: str) -> str:
    """
    Determine the channel for a specific transaction line item.

    Priority 1 (voucher type) overrides party-level classification for certain types.
    """
    # Priority 1: Voucher type auto-classification
    vtype_rules = {
        "Sales-Flipkart": "online",
        "Sales-Amazon": "online",
        "Sales-ALKG": "online",
        "Sales Store": "store",
        "Physical Stock": "ignore",
    }
    if voucher_type in vtype_rules:
        return vtype_rules[voucher_type]

    # Otherwise use party-level channel
    return party_channel


def auto_classify_all_parties(db_conn) -> dict:
    """
    Apply auto-classification rules to all unclassified parties in the database.

    Returns counts: {channel: count_updated}
    """
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT tally_name, tally_parent FROM parties
            WHERE channel = 'unclassified'
        """)
        unclassified = cur.fetchall()

    if not unclassified:
        return {}

    updates = []
    for tally_name, tally_parent in unclassified:
        channel, confidence = classify_party(tally_name, tally_parent)
        if channel != "unclassified":
            updates.append((channel, tally_name))

    if updates:
        with db_conn.cursor() as cur:
            # Update party classification
            cur.executemany("""
                UPDATE parties SET channel = %s, classified_at = NOW()
                WHERE tally_name = %s
            """, updates)
            # Backfill transactions with updated channel
            cur.executemany("""
                UPDATE transactions SET channel = %s
                WHERE party_name = %s
            """, updates)
        db_conn.commit()

    # Count by channel
    counts = {}
    for channel, _ in updates:
        counts[channel] = counts.get(channel, 0) + 1
    return counts


def export_parties_csv(db_conn, csv_path: str = None) -> int:
    """Export all parties to CSV with pre-classification for human review."""
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "party_classification.csv")

    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT tally_name, tally_parent, channel FROM parties
            ORDER BY channel, tally_name
        """)
        rows = cur.fetchall()

    parties = []
    for tally_name, tally_parent, current_channel in rows:
        if current_channel == "unclassified":
            suggested, confidence = classify_party(tally_name, tally_parent)
        else:
            suggested = current_channel
            confidence = "confirmed"
        parties.append({
            "tally_name": tally_name,
            "tally_parent": tally_parent or "",
            "channel": suggested,
            "confidence": confidence,
        })

    # Sort: unclassified/low confidence first
    confidence_order = {"low": 0, "medium": 1, "high": 2, "confirmed": 3}
    parties.sort(key=lambda p: (confidence_order.get(p["confidence"], 9), p["tally_name"]))

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["tally_name", "tally_parent", "channel", "confidence"])
        writer.writeheader()
        writer.writerows(parties)

    return len(parties)


def import_classified_csv(db_conn, csv_path: str = None) -> dict:
    """Import classified CSV back into database."""
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "party_classification.csv")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    updated = 0
    still_unclassified = 0

    with db_conn.cursor() as cur:
        for row in rows:
            channel = row["channel"].strip()
            if channel not in VALID_CHANNELS:
                continue
            if channel == "unclassified":
                still_unclassified += 1
                continue
            cur.execute("""
                UPDATE parties SET channel = %s, classified_at = NOW()
                WHERE tally_name = %s AND channel != %s
            """, (channel, row["tally_name"], channel))
            updated += cur.rowcount

    db_conn.commit()
    return {"updated": updated, "still_unclassified": still_unclassified}


def detect_new_parties(db_conn) -> list[str]:
    """Find parties in transactions not yet in the parties table, and insert them."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT t.party_name
            FROM transactions t
            LEFT JOIN parties p ON t.party_name = p.tally_name
            WHERE p.id IS NULL AND t.party_name != ''
        """)
        new_names = [row[0] for row in cur.fetchall()]

        if new_names:
            for name in new_names:
                cur.execute("""
                    INSERT INTO parties (tally_name, channel)
                    VALUES (%s, 'unclassified')
                    ON CONFLICT (tally_name) DO NOTHING
                """, (name,))

    db_conn.commit()
    return new_names


def get_unclassified_count(db_conn) -> int:
    """Return count of parties still unclassified."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM parties WHERE channel = 'unclassified'")
        return cur.fetchone()[0]
