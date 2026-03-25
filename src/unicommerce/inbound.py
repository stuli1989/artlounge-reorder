"""
GRN/PO ingestion — pull Goods Receipt Notes from Unicommerce.

Uses createdBetween with textRange presets for listing.
Fetches detail per GRN code for SKU-level data and lead time computation.

Maps to: transactions (inward, supplier), grn_receipts table.
"""
import logging
from datetime import date, timedelta
import psycopg2.extras

from unicommerce.returns import _parse_uc_date

logger = logging.getLogger(__name__)

# textRange presets available in UC API
_TEXT_RANGES = [
    ("LAST_7_DAYS", 7),
    ("LAST_30_DAYS", 30),
    ("LAST_60_DAYS", 60),
    ("LAST_90_DAYS", 90),
]


def _quarterly_windows(since_date, end_date):
    """Yield (start, end) date tuples in ~90-day windows."""
    current = since_date
    while current < end_date:
        window_end = min(current + timedelta(days=90), end_date)
        yield current, window_end
        current = window_end + timedelta(days=1)


def pull_grns_since(client, since_date, end_date=None):
    """
    Pull GRN details created since last sync.

    Uses createdBetween with custom start/end dates in quarterly windows.
    Then fetches detail for each GRN code.

    Args:
        client: UnicommerceClient
        since_date: Start date
        end_date: End date (default: today)

    Returns:
        List of GRN detail dicts, tagged with _facility
    """
    if end_date is None:
        end_date = date.today()

    all_grns = []

    for facility in client.facilities:
        for win_start, win_end in _quarterly_windows(since_date, end_date):
            logger.info("  GRNs @ %s: %s to %s", facility, win_start, win_end)

            body = {"createdBetween": {
                "start": win_start.isoformat(),
                "end": win_end.isoformat(),
            }}
            try:
                data = client._request(
                    "POST",
                    "/services/rest/v1/purchase/inflowReceipt/getInflowReceipts",
                    json=body,
                    facility=facility,
                )
            except Exception as e:
                logger.warning("GRN list failed for %s: %s", facility, e)
                continue

            codes = data.get("inflowReceiptCodes", [])
            logger.info("    Found %d GRN codes", len(codes))

            for code in codes:
                try:
                    detail = client._request(
                        "POST",
                        "/services/rest/v1/purchase/inflowReceipt/getInflowReceipt",
                        json={"inflowReceiptCode": code},
                        facility=facility,
                    )
                    grn = detail.get("inflowReceipt", detail)
                    grn["_facility"] = facility
                    all_grns.append(grn)
                except Exception as e:
                    logger.warning("Failed to fetch GRN detail %s: %s", code, e)

    logger.info("Total GRNs fetched: %d", len(all_grns))
    return all_grns


def transform_grns_to_transactions(grns):
    """Convert GRN details to inward transaction rows (supplier channel)."""
    txns = []

    for grn in grns:
        code = grn.get("code", "")
        facility = grn.get("_facility", "")

        received_date = _parse_uc_date(grn.get("created"))
        if not received_date:
            logger.warning("Skipping GRN %s: no date", code)
            continue

        po = grn.get("purchaseOrder", {})
        vendor_name = po.get("vendorName", grn.get("vendorName", ""))

        items = grn.get("inflowReceiptItems", [])
        for item in items:
            # UC field is "itemSKU" (not "itemTypeSKU")
            sku = item.get("itemSKU", "")
            if not sku:
                continue
            qty = int(item.get("quantity", 0) or 0)
            rejected = int(item.get("rejectedQuantity", 0) or 0)
            accepted_qty = qty - rejected
            if accepted_qty <= 0:
                continue

            unit_price = item.get("unitPrice")
            amount = (unit_price * accepted_qty) if unit_price else None

            txns.append({
                "txn_date": received_date,
                "stock_item_name": sku,
                "quantity": accepted_qty,
                "is_inward": True,
                "channel": "supplier",
                "uc_channel": None,
                "party_name": vendor_name,
                "voucher_type": "GRN",
                "voucher_number": code,
                "rate": unit_price,
                "amount": amount,
                "return_type": None,
                "facility": facility,
                "shipping_package_code": None,
            })

    logger.info("Transformed %d GRNs into %d transaction rows", len(grns), len(txns))
    return txns


def store_grn_details(db_conn, grns):
    """Store GRN headers into grn_receipts table with lead time computation."""
    if not grns:
        return 0

    rows = []
    for grn in grns:
        code = grn.get("code", "")
        if not code:
            continue

        received_date = _parse_uc_date(grn.get("created"))
        po = grn.get("purchaseOrder", {})
        po_code = po.get("code")
        po_created = _parse_uc_date(po.get("created"))

        lead_days = None
        if received_date and po_created:
            lead_days = (received_date - po_created).days

        items = grn.get("inflowReceiptItems", [])
        total_qty = sum(int(i.get("quantity", 0) or 0) for i in items)
        total_rejected = sum(int(i.get("rejectedQuantity", 0) or 0) for i in items)

        rows.append({
            "code": code,
            "po_code": po_code,
            "vendor_code": po.get("vendorCode", grn.get("vendorCode")),
            "vendor_name": po.get("vendorName", grn.get("vendorName")),
            "facility_code": grn.get("_facility"),
            "received_date": received_date,
            "po_created_date": po_created,
            "total_quantity": total_qty,
            "total_rejected": total_rejected,
            "computed_lead_days": lead_days,
        })

    sql = """
        INSERT INTO grn_receipts (code, po_code, vendor_code, vendor_name, facility_code,
                                   received_date, po_created_date, total_quantity,
                                   total_rejected, computed_lead_days)
        VALUES (%(code)s, %(po_code)s, %(vendor_code)s, %(vendor_name)s, %(facility_code)s,
                %(received_date)s, %(po_created_date)s, %(total_quantity)s,
                %(total_rejected)s, %(computed_lead_days)s)
        ON CONFLICT (code) DO UPDATE SET
            po_created_date = EXCLUDED.po_created_date,
            total_quantity = EXCLUDED.total_quantity,
            total_rejected = EXCLUDED.total_rejected,
            computed_lead_days = EXCLUDED.computed_lead_days
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows)
    db_conn.commit()

    logger.info("Stored %d GRN receipt records", len(rows))
    return len(rows)
