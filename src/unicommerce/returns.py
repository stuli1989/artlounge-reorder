"""
Returns ingestion — pull CIR and RTO returns from Unicommerce.

Handles the 30-day window cap by looping in 30-day windows.
Fetches return detail for SKU-level data.

Maps to: transactions (inward), returns, return_items tables.
"""
import logging
from datetime import date, timedelta
import psycopg2.extras

from unicommerce.orders import CHANNEL_MAP

logger = logging.getLogger(__name__)


def date_windows(start_date, end_date, max_days=30):
    """Yield (window_start, window_end) tuples of at most max_days each."""
    current = start_date
    while current < end_date:
        window_end = min(current + timedelta(days=max_days), end_date)
        yield current, window_end
        current = window_end


def pull_returns_since(client, since_date, end_date=None):
    """
    Pull returns (CIR + RTO) since a given date.

    Uses 30-day window looping (UC API cap) with updated timestamps.
    Fetches detail for each return to get SKU-level data.

    Args:
        client: UnicommerceClient
        since_date: Start date
        end_date: End date (default: today)

    Returns:
        List of return detail dicts, tagged with _return_type and _facility
    """
    if end_date is None:
        end_date = date.today()

    all_returns = []

    for return_type in ["CIR", "RTO"]:
        for facility in client.facilities:
            for window_start, window_end in date_windows(since_date, end_date):
                logger.info("  Returns %s @ %s: %s to %s",
                           return_type, facility, window_start, window_end)
                try:
                    data = client._request(
                        "POST",
                        "/services/rest/v1/oms/return/search",
                        json={
                            "returnType": return_type,
                            "updatedFrom": window_start.strftime("%Y-%m-%dT00:00:00"),
                            "updatedTo": window_end.strftime("%Y-%m-%dT23:59:59"),
                        },
                        facility=facility,
                    )
                except Exception as e:
                    logger.warning("Return search failed for %s/%s: %s", return_type, facility, e)
                    continue

                return_orders = data.get("returnOrders", [])
                logger.info("    Found %d %s returns", len(return_orders), return_type)

                for ret in return_orders:
                    code = ret.get("code", "")
                    if not code:
                        continue
                    # CIR: code IS the reversePickupCode
                    # RTO: code IS the shipmentCode (not reversePickupCode)
                    detail_body = (
                        {"reversePickupCode": code}
                        if return_type == "CIR"
                        else {"shipmentCode": code}
                    )
                    try:
                        detail = client._request(
                            "POST",
                            "/services/rest/v1/oms/return/get",
                            json=detail_body,
                            facility=facility,
                        )
                        detail["_return_type"] = return_type
                        detail["_facility"] = facility
                        detail["_search_code"] = code
                        all_returns.append(detail)
                    except Exception as e:
                        logger.warning("Failed to fetch return detail %s: %s", code, e)

    logger.info("Total returns fetched: %d", len(all_returns))
    return all_returns


def transform_returns_to_transactions(returns):
    """
    Convert return details to inward transaction rows.

    Each return's SKU items become inward transactions that offset the
    original sale channel. Same-SKU quantities within a return are aggregated.
    """
    txns = []

    for ret in returns:
        return_type = ret.get("_return_type", "CIR")
        facility = ret.get("_facility", "")

        # Extract return metadata
        ret_value = ret.get("returnSaleOrderValue", ret)
        reverse_pickup_code = (
            ret.get("reversePickupCode")
            or ret_value.get("reversePickupCode")
            or ret.get("_search_code", "")  # fallback for RTO
        )
        sale_order_code = ret_value.get("saleOrderCode", "")

        # Parse return date
        ret_date_str = ret_value.get("returnCreatedDate") or ret_value.get("created")
        ret_date = _parse_uc_date(ret_date_str)
        if not ret_date:
            logger.warning("Skipping return %s: no date", reverse_pickup_code)
            continue

        # Get the original sale channel
        uc_channel = ret_value.get("channel", "")
        channel = CHANNEL_MAP.get(uc_channel, "unclassified")

        # Aggregate SKU quantities
        qty_by_sku = {}
        return_items = ret.get("returnSaleOrderItems", [])
        for item in return_items:
            sku = item.get("skuCode", "")
            if not sku:
                continue
            qty = int(item.get("quantity") or 1)
            qty_by_sku[sku] = qty_by_sku.get(sku, 0) + qty

        voucher_number = f"{return_type}-{reverse_pickup_code}"

        for sku, qty in qty_by_sku.items():
            txns.append({
                "txn_date": ret_date,
                "stock_item_name": sku,
                "quantity": qty,
                "is_inward": True,
                "channel": channel,
                "uc_channel": uc_channel,
                "party_name": "",
                "voucher_type": "Return",
                "voucher_number": voucher_number,
                "rate": None,
                "amount": None,
                "return_type": return_type,
                "facility": facility,
                "shipping_package_code": ret_value.get("shipmentCode"),
            })

    logger.info("Transformed %d returns into %d transaction rows", len(returns), len(txns))
    return txns


def store_return_details(db_conn, returns):
    """Store return headers and items into returns/return_items tables."""
    if not returns:
        return 0

    headers = []
    items = []

    for ret in returns:
        ret_value = ret.get("returnSaleOrderValue", ret)
        reverse_pickup_code = (
            ret.get("reversePickupCode")
            or ret_value.get("reversePickupCode")
            or ret.get("_search_code", "")  # fallback for RTO
        )
        if not reverse_pickup_code:
            continue

        uc_channel = ret_value.get("channel", "")

        headers.append({
            "reverse_pickup_code": reverse_pickup_code,
            "return_type": ret.get("_return_type", "CIR"),
            "sale_order_code": ret_value.get("saleOrderCode"),
            "facility_code": ret.get("_facility"),
            "channel": uc_channel,
            "return_created_date": _parse_uc_date(ret_value.get("returnCreatedDate")),
            "return_completed_date": _parse_uc_date(ret_value.get("returnCompletedDate")),
            "invoice_code": ret_value.get("returnInvoiceCode"),
        })

        for item in ret.get("returnSaleOrderItems", []):
            sku = item.get("skuCode", "")
            if not sku:
                continue
            items.append({
                "reverse_pickup_code": reverse_pickup_code,
                "sku_code": sku,
                "item_name": item.get("itemName"),
                "quantity": int(item.get("quantity") or 1),
                "inventory_type": item.get("inventoryType"),
            })

    # Upsert headers
    header_sql = """
        INSERT INTO returns (reverse_pickup_code, return_type, sale_order_code,
                             facility_code, channel, return_created_date,
                             return_completed_date, invoice_code)
        VALUES (%(reverse_pickup_code)s, %(return_type)s, %(sale_order_code)s,
                %(facility_code)s, %(channel)s, %(return_created_date)s,
                %(return_completed_date)s, %(invoice_code)s)
        ON CONFLICT (reverse_pickup_code) DO UPDATE SET
            return_completed_date = EXCLUDED.return_completed_date
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, header_sql, headers)
    db_conn.commit()

    # Upsert items
    if items:
        item_sql = """
            INSERT INTO return_items (reverse_pickup_code, sku_code, item_name,
                                      quantity, inventory_type)
            VALUES (%(reverse_pickup_code)s, %(sku_code)s, %(item_name)s,
                    %(quantity)s, %(inventory_type)s)
            ON CONFLICT (reverse_pickup_code, sku_code) DO UPDATE SET
                quantity = EXCLUDED.quantity,
                inventory_type = EXCLUDED.inventory_type
        """
        with db_conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, item_sql, items)
        db_conn.commit()

    logger.info("Stored %d return headers, %d return items", len(headers), len(items))
    return len(headers)


def _parse_uc_date(date_str):
    """Parse various UC date formats to date object."""
    if not date_str:
        return None
    if isinstance(date_str, (int, float)):
        from unicommerce.orders import epoch_to_date
        return epoch_to_date(date_str)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            from datetime import datetime
            return datetime.strptime(date_str[:19], fmt).date()
        except (ValueError, TypeError):
            continue
    logger.warning("Could not parse date: %s", date_str)
    return None
