"""
Parsers for Tally Prime XML responses.

Converts raw XML bytes into Python dicts ready for database insertion.
All parsers accept bytes input (as returned by TallyClient.send_request_raw)
and handle XML sanitization internally.
"""
import re
from lxml import etree
from extraction.tally_client import TallyClient

# Regex to extract a leading number from strings like "45 pcs", "-12 nos", "0.5 kg"
_QTY_RE = re.compile(r"^\s*([-]?\d+\.?\d*)")
# Regex to extract a number from rate strings like "216.10/PCS"
_RATE_RE = re.compile(r"^\s*([-]?\d+\.?\d*)")


def _parse_xml(raw: bytes) -> etree._Element:
    """Sanitize and parse raw Tally XML bytes."""
    sanitized = TallyClient._sanitize_xml(raw)
    return etree.fromstring(sanitized)


def parse_tally_quantity(qty_str: str | None) -> float:
    """Parse Tally quantity string like '45 pcs', '-12 nos', ' 1 PCS' into a float."""
    if not qty_str:
        return 0.0
    m = _QTY_RE.search(qty_str.strip())
    if m:
        return float(m.group(1))
    return 0.0


def parse_tally_rate(rate_str: str | None) -> float:
    """Parse Tally rate string like '216.10/PCS' into a float."""
    if not rate_str:
        return 0.0
    m = _RATE_RE.search(rate_str.strip())
    if m:
        return float(m.group(1))
    return 0.0


def parse_tally_amount(amount_str: str | None) -> float:
    """Parse Tally amount string into a float."""
    if not amount_str:
        return 0.0
    try:
        return float(amount_str.strip())
    except (ValueError, AttributeError):
        return 0.0


def parse_stock_categories(xml_bytes: bytes) -> list[dict]:
    """Parse stock categories (brands) from Tally XML."""
    root = _parse_xml(xml_bytes)
    results = []
    for cat in root.iter("STOCKCATEGORY"):
        name = cat.get("NAME") or (cat.findtext("NAME") or "").strip()
        if not name:
            continue
        parent = (cat.findtext("PARENT") or "").strip()
        master_id = (cat.findtext("MASTERID") or "").strip()
        results.append({
            "name": name,
            "parent": parent or None,
            "tally_master_id": master_id or None,
        })
    return results


def parse_stock_items(xml_bytes: bytes) -> list[dict]:
    """Parse stock items (SKUs) from Tally XML."""
    root = _parse_xml(xml_bytes)
    results = []
    for item in root.iter("STOCKITEM"):
        name = item.get("NAME") or (item.findtext("NAME") or "").strip()
        if not name:
            continue
        stock_group = (item.findtext("PARENT") or "").strip()
        category = (item.findtext("CATEGORY") or "").strip()
        base_unit = (item.findtext("BASEUNITS") or "").strip()
        master_id = (item.findtext("MASTERID") or "").strip()
        closing_balance = parse_tally_quantity(item.findtext("CLOSINGBALANCE"))
        closing_value = parse_tally_amount(item.findtext("CLOSINGVALUE"))
        opening_balance = parse_tally_quantity(item.findtext("OPENINGBALANCE"))

        # PartNo is stored as MAILINGNAME in Tally's XML export
        mailing = item.find("MAILINGNAME.LIST")
        if mailing is not None:
            part_no = (mailing.findtext("MAILINGNAME") or "").strip() or None
        else:
            part_no = None

        results.append({
            "name": name,
            "stock_group": stock_group or None,
            "category": category or None,
            "base_unit": base_unit or None,
            "tally_master_id": master_id or None,
            "closing_balance": closing_balance,
            "closing_value": closing_value,
            "opening_balance": opening_balance,
            "part_no": part_no,
        })
    return results


def parse_ledgers(xml_bytes: bytes) -> list[dict]:
    """Parse ledgers (parties) from Tally XML."""
    root = _parse_xml(xml_bytes)
    results = []
    for ledger in root.iter("LEDGER"):
        name = ledger.get("NAME") or (ledger.findtext("NAME") or "").strip()
        if not name:
            continue
        parent = (ledger.findtext("PARENT") or "").strip()
        master_id = (ledger.findtext("MASTERID") or "").strip()
        results.append({
            "name": name,
            "parent": parent or None,
            "tally_master_id": master_id or None,
        })
    return results


def parse_vouchers(xml_bytes: bytes) -> list[dict]:
    """
    Parse vouchers with inventory entries from Tally XML.

    Each voucher can have multiple ALLINVENTORYENTRIES.LIST elements.
    Returns one dict per inventory line item (not per voucher).

    Direction logic uses ISDEEMEDPOSITIVE:
      - "Yes" = inward (purchase, credit note return)
      - "No"  = outward (sale)
    """
    root = _parse_xml(xml_bytes)
    results = []
    for v in root.iter("VOUCHER"):
        # Voucher-level fields
        vdate = (v.findtext("DATE") or "").strip()
        if not vdate:
            continue
        party = (v.findtext("PARTYLEDGERNAME") or "").strip()
        voucher_type = (v.findtext("VOUCHERTYPENAME") or v.get("VCHTYPE") or "").strip()
        voucher_number = (v.findtext("VOUCHERNUMBER") or "").strip()
        master_id = (v.findtext("MASTERID") or "").strip()

        # Inventory line items
        for ie in v.findall(".//ALLINVENTORYENTRIES.LIST"):
            stock_item = (ie.findtext("STOCKITEMNAME") or "").strip()
            if not stock_item:
                continue

            # Direction: ISDEEMEDPOSITIVE "Yes" = inward, "No" = outward
            deemed_positive = (ie.findtext("ISDEEMEDPOSITIVE") or "").strip()
            is_inward = deemed_positive == "Yes"

            qty = abs(parse_tally_quantity(ie.findtext("ACTUALQTY")))
            if qty == 0:
                qty = abs(parse_tally_quantity(ie.findtext("BILLEDQTY")))

            rate = abs(parse_tally_rate(ie.findtext("RATE")))
            amount = abs(parse_tally_amount(ie.findtext("AMOUNT")))

            results.append({
                "date": vdate,
                "party": party,
                "voucher_type": voucher_type,
                "voucher_number": voucher_number or None,
                "stock_item": stock_item,
                "quantity": qty,
                "is_inward": is_inward,
                "rate": rate,
                "amount": amount,
                "tally_master_id": master_id or None,
            })

    return results
