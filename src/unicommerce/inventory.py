"""
Inventory snapshot ingestion — pull current stock levels from Unicommerce.

Uses conservative 1K SKU batches per facility to avoid payload/WAF issues.
Aggregates across all facilities. Implements F1 (available_stock).

Maps to: daily_inventory_snapshots, facility_inventory tables.
"""
import logging
from datetime import date
import psycopg2.extras

from unicommerce.catalog import get_all_sku_codes

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000  # SKUs per API call


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def pull_inventory_snapshot(client, db_conn):
    """
    Pull inventory for ALL SKUs across ALL facilities.

    Returns:
        dict: {sku_code: {inventory, blocked, putaway, openSale, openPurchase, bad}}
    """
    all_skus = get_all_sku_codes(db_conn)
    if not all_skus:
        logger.warning("No SKU codes in database — run catalog sync first")
        return {}, {}

    logger.info("Pulling inventory snapshot for %d SKUs across %d facilities",
                len(all_skus), len(client.facilities))

    aggregated = {}
    facility_data = {}

    for facility in client.facilities:
        logger.info("  Facility %s: %d chunks of %d SKUs",
                     facility, (len(all_skus) + CHUNK_SIZE - 1) // CHUNK_SIZE, CHUNK_SIZE)
        for i, chunk in enumerate(chunks(all_skus, CHUNK_SIZE)):
            data = client._request(
                "POST",
                "/services/rest/v1/inventory/inventorySnapshot/get",
                json={"itemTypeSKUs": chunk},
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

                # Aggregate across facilities
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

                # Per-facility data
                key = (facility, sku)
                facility_data[key] = {
                    "inventory": inv, "blocked": blocked, "putaway": putaway,
                    "openSale": open_sale, "openPurchase": open_purchase, "bad": bad,
                }

    logger.info("Snapshot complete: %d SKUs with inventory across %d facilities",
                len(aggregated), len(client.facilities))

    return aggregated, facility_data


def store_daily_snapshot(db_conn, snapshot_date, aggregated, facility_data=None):
    """
    Store today's inventory snapshot into DB.

    Args:
        db_conn: PostgreSQL connection
        snapshot_date: date object
        aggregated: {sku: {inventory, blocked, putaway, openSale, openPurchase, bad}}
        facility_data: {(facility, sku): {...}} for per-facility storage
    """
    if not aggregated:
        return 0

    # Upsert aggregated snapshots
    rows = []
    for sku, data in aggregated.items():
        rows.append({
            "snapshot_date": snapshot_date,
            "sku_code": sku,
            "inventory": data["inventory"],
            "inventory_blocked": data["blocked"],
            "putaway_pending": data["putaway"],
            "open_sale": data["openSale"],
            "open_purchase": data["openPurchase"],
            "bad_inventory": data["bad"],
        })

    sql = """
        INSERT INTO daily_inventory_snapshots
            (snapshot_date, sku_code, inventory, inventory_blocked, putaway_pending,
             open_sale, open_purchase, bad_inventory)
        VALUES (%(snapshot_date)s, %(sku_code)s, %(inventory)s, %(inventory_blocked)s,
                %(putaway_pending)s, %(open_sale)s, %(open_purchase)s, %(bad_inventory)s)
        ON CONFLICT (snapshot_date, sku_code) DO UPDATE SET
            inventory = EXCLUDED.inventory,
            inventory_blocked = EXCLUDED.inventory_blocked,
            putaway_pending = EXCLUDED.putaway_pending,
            open_sale = EXCLUDED.open_sale,
            open_purchase = EXCLUDED.open_purchase,
            bad_inventory = EXCLUDED.bad_inventory
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows, page_size=1000)
    db_conn.commit()
    logger.info("Stored %d aggregated inventory snapshots for %s", len(rows), snapshot_date)

    # Upsert per-facility data
    if facility_data:
        fac_rows = []
        for (facility, sku), data in facility_data.items():
            fac_rows.append({
                "snapshot_date": snapshot_date,
                "facility_code": facility,
                "sku_code": sku,
                "inventory": data["inventory"],
                "inventory_blocked": data["blocked"],
                "putaway_pending": data["putaway"],
                "open_sale": data["openSale"],
                "open_purchase": data["openPurchase"],
                "bad_inventory": data["bad"],
            })

        fac_sql = """
            INSERT INTO facility_inventory
                (snapshot_date, facility_code, sku_code, inventory, inventory_blocked,
                 putaway_pending, open_sale, open_purchase, bad_inventory)
            VALUES (%(snapshot_date)s, %(facility_code)s, %(sku_code)s, %(inventory)s,
                    %(inventory_blocked)s, %(putaway_pending)s, %(open_sale)s,
                    %(open_purchase)s, %(bad_inventory)s)
            ON CONFLICT (snapshot_date, facility_code, sku_code) DO UPDATE SET
                inventory = EXCLUDED.inventory,
                inventory_blocked = EXCLUDED.inventory_blocked,
                putaway_pending = EXCLUDED.putaway_pending,
                open_sale = EXCLUDED.open_sale,
                open_purchase = EXCLUDED.open_purchase,
                bad_inventory = EXCLUDED.bad_inventory
        """
        with db_conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, fac_sql, fac_rows, page_size=1000)
        db_conn.commit()
        logger.info("Stored %d facility-level inventory records", len(fac_rows))

    return len(rows)
