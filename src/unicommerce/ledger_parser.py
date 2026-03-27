# src/unicommerce/ledger_parser.py
"""
Parse UC Transaction Ledger CSVs into normalized transaction dicts.

Excludes INVOICES (billing documents, not physical movements).
Channel classification uses DB-backed rules table when available,
falls back to hardcoded defaults otherwise.
"""
import csv
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_EXCLUDED_ENTITIES = {"INVOICES"}

_FACILITY_MAP = {
    "PPETPL Bhiwandi": "ppetpl",
    "PPETPL Kala Ghoda": "PPETPLKALAGHODA",
    "Art Lounge Bhiwandi": "ALIBHIWANDI",
}

_DEMAND_ENTITY_TYPES = {"MANUAL", "SALE"}


def is_excluded_entity(entity):
    """Check if an entity type should be excluded from the pipeline."""
    return entity in _EXCLUDED_ENTITIES


def parse_ledger_row(row):
    """Parse a single CSV row into a normalized transaction dict.

    Returns None if the row should be skipped (empty SKU, bad date, excluded entity).
    """
    sku_code = row.get("SKU Code", "").lstrip("'").strip()
    if not sku_code:
        return None

    entity = row.get("Entity", "").strip()
    if is_excluded_entity(entity):
        return None

    entity_type = row.get("Entity Type", "").strip()
    entity_code = row.get("Entity Code", "").strip().rstrip(",")
    txn_type = row.get("Transaction Type", "").strip()  # IN or OUT
    from_facility = row.get("From Facility", "-").strip()
    to_facility = row.get("To Facility", "-").strip()
    sale_order = row.get("Sale Order Code", "-").strip().lstrip("'")

    units = float(row.get("Units", 0) or 0)

    # Parse date
    date_str = row.get("Inventory Updated At", "").strip()
    try:
        if " " in date_str:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date()
        else:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

    # Determine facility
    if txn_type == "OUT":
        facility_raw = from_facility
    else:
        facility_raw = to_facility
    facility = _FACILITY_MAP.get(facility_raw, facility_raw)

    # Compute stock_change (signed)
    if txn_type == "OUT":
        stock_change = -abs(units)
    else:
        stock_change = units  # preserves negative for REMOVE/REPLACE

    # Demand flag: only PICKLIST with MANUAL/SALE entity_type going OUT
    is_demand = (entity == "PICKLIST" and entity_type in _DEMAND_ENTITY_TYPES
                 and txn_type == "OUT")

    return {
        "sku_code": sku_code,
        "sku_name": row.get("SKU Name", "").strip(),
        "txn_date": txn_date,
        "entity": entity,
        "entity_type": entity_type,
        "entity_code": entity_code if entity_code != "-" else "",
        "txn_type": txn_type,
        "units": units,
        "stock_change": stock_change,
        "facility": facility,
        "is_demand": is_demand,
        "sale_order_code": sale_order if sale_order != "-" else None,
    }


def parse_ledger_csv(csv_text):
    """Parse CSV text content into a list of transaction dicts.

    Excludes INVOICES. Returns list sorted by txn_date.
    """
    rows = []
    reader = csv.DictReader(csv_text.splitlines())
    for row in reader:
        parsed = parse_ledger_row(row)
        if parsed:
            rows.append(parsed)
    rows.sort(key=lambda r: r["txn_date"])
    return rows


def parse_ledger_file(file_path):
    """Parse a CSV file from disk into a list of transaction dicts."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return parse_ledger_csv(f.read())


def classify_channel(parsed_row, rules=None):
    """Classify channel for a parsed transaction row.

    If rules are provided (from DB), apply them by priority (highest first).
    Otherwise use hardcoded defaults.

    Args:
        parsed_row: dict from parse_ledger_row()
        rules: list of channel_rules dicts, sorted by priority DESC (optional)

    Returns:
        str: channel name (supplier, wholesale, online, store, internal)
    """
    entity = parsed_row["entity"]
    sale_order = parsed_row.get("sale_order_code") or ""
    facility = parsed_row["facility"]

    if rules:
        for rule in rules:
            if not rule.get("is_active", True):
                continue

            rt = rule["rule_type"]
            mv = rule["match_value"]
            ff = rule.get("facility_filter")

            if rt == "entity" and entity == mv:
                return rule["channel"]
            if rt == "sale_order_prefix" and sale_order.startswith(mv):
                if ff and facility != ff:
                    continue
                return rule["channel"]
            if rt == "default" and entity == mv:
                return rule["channel"]

    # Hardcoded fallback (matches seed data)
    if entity == "GRN":
        return "supplier"
    if entity in ("INVENTORY_ADJUSTMENT", "INBOUND_GATEPASS", "OUTBOUND_GATEPASS",
                  "PUTAWAY_CANCELLED_ITEM", "PUTAWAY_PICKLIST_ITEM"):
        return "internal"
    if entity in ("PUTAWAY_CIR", "PUTAWAY_RTO"):
        return "online"
    if entity == "PICKLIST":
        if sale_order.startswith("MA-") or sale_order.startswith("B2C-"):
            return "online"
        if "KALAGHODA" in facility.upper():
            return "store"
        return "wholesale"
    return "internal"
