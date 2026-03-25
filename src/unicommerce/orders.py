"""
Dispatch ingestion — pull shipped packages from Unicommerce.

Transforms shipping packages into outward transaction rows with channel mapping.

Maps to: transactions table (outward).
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# UC channel → our channel taxonomy
CHANNEL_MAP = {
    "MAGENTO2": "online",
    "FLIPKART": "online",
    "AMAZON_EASYSHIP_V2": "online",
    "AMAZON_IN_API": "online",
    "CUSTOM": "wholesale",
    "CUSTOM_SHOP": "store",
}


def epoch_to_date(epoch_ms):
    """Convert UC epoch milliseconds to date."""
    if not epoch_ms:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).date()


def pull_dispatched_since(client, minutes_since=1500):
    """
    Pull shipping packages dispatched/updated since last sync.

    Args:
        client: UnicommerceClient (authenticated, facilities discovered)
        minutes_since: Pull packages updated in last N minutes (default 25hrs)

    Returns:
        List of shipping package dicts, tagged with _facility
    """
    all_packages = []
    for facility in client.facilities:
        logger.info("Pulling dispatched packages from %s (last %d min)", facility, minutes_since)
        data = client._request(
            "POST",
            "/services/rest/v1/oms/shippingPackage/search",
            json={"statuses": ["DISPATCHED"], "updatedSinceInMinutes": minutes_since},
            facility=facility,
        )
        packages = data.get("elements", [])
        for pkg in packages:
            pkg["_facility"] = facility
        all_packages.extend(packages)
        logger.info("  %s: %d dispatched packages", facility, len(packages))

    logger.info("Total dispatched packages: %d", len(all_packages))
    return all_packages


def pull_dispatched_in_range(client, facility, start_date, end_date):
    """Pull dispatched packages in a date range (for backfill)."""
    data = client._request(
        "POST",
        "/services/rest/v1/oms/shippingPackage/search",
        json={
            "statuses": ["DISPATCHED"],
            "fromDate": start_date.strftime("%Y-%m-%dT00:00:00"),
            "toDate": end_date.strftime("%Y-%m-%dT23:59:59"),
        },
        facility=facility,
    )
    packages = data.get("elements", [])
    for pkg in packages:
        pkg["_facility"] = facility
    return packages


def transform_packages_to_transactions(packages):
    """
    Convert shipping packages to normalized transaction rows.

    Each item in a package becomes one transaction row (outward).
    Packages with the same code are deduplicated by aggregating quantities per SKU.
    """
    txns = []
    for pkg in packages:
        code = pkg.get("code", "")
        dispatch_date = epoch_to_date(pkg.get("dispatched"))
        if not dispatch_date:
            # Try alternative date fields
            dispatch_date = epoch_to_date(pkg.get("updated"))
        if not dispatch_date:
            logger.warning("Skipping package %s: no dispatch date", code)
            continue

        uc_channel = pkg.get("channel", "")
        channel = CHANNEL_MAP.get(uc_channel, "unclassified")
        customer = pkg.get("customer", "")
        facility = pkg.get("_facility", "")

        items = pkg.get("items", {})
        if isinstance(items, dict):
            item_list = items.values()
        elif isinstance(items, list):
            item_list = items
        else:
            continue

        # Aggregate same-SKU quantities within a package
        sku_qty = {}
        sku_names = {}
        for item in item_list:
            sku = item.get("itemSku", "")
            if not sku:
                continue
            qty = int(item.get("quantity", 1) or 1)
            sku_qty[sku] = sku_qty.get(sku, 0) + qty
            if sku not in sku_names:
                sku_names[sku] = item.get("itemName", "")

        for sku, qty in sku_qty.items():
            txns.append({
                "txn_date": dispatch_date,
                "stock_item_name": sku,
                "quantity": qty,
                "is_inward": False,
                "channel": channel,
                "uc_channel": uc_channel,
                "party_name": customer,
                "voucher_type": "Dispatch",
                "voucher_number": code,
                "rate": None,
                "amount": None,
                "return_type": None,
                "facility": facility,
                "shipping_package_code": code,
            })

    logger.info("Transformed %d packages into %d transaction rows", len(packages), len(txns))
    return txns
