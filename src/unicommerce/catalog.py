"""
Catalog ingestion — pull SKU master data from Unicommerce.

Maps to: stock_items, stock_categories tables.
"""
import logging
import psycopg2.extras

logger = logging.getLogger(__name__)


def pull_all_skus(client):
    """Pull all SKUs from UC. Used for first sync (~23K items, single call)."""
    logger.info("Pulling all SKUs from Unicommerce...")
    data = client._request(
        "POST",
        "/services/rest/v1/product/itemType/search",
        json={},
        timeout=120,
    )
    items = data.get("elements", [])
    logger.info("Pulled %d SKUs", len(items))
    return items


def pull_updated_skus(client, hours_since=25):
    """Pull SKUs updated since N hours ago (incremental sync)."""
    logger.info("Pulling SKUs updated in last %d hours...", hours_since)
    data = client._request(
        "POST",
        "/services/rest/v1/product/itemType/search",
        json={"updatedSinceInHour": hours_since},
        timeout=120,
    )
    items = data.get("elements", [])
    logger.info("Pulled %d updated SKUs", len(items))
    return items


def extract_sku_fields(uc_item):
    """Extract relevant fields from a UC itemType response."""
    return {
        "sku_code": uc_item.get("skuCode", ""),
        "name": uc_item.get("name", uc_item.get("skuCode", "")),
        "category_code": uc_item.get("categoryCode", ""),
        "brand": uc_item.get("brand", ""),
        "cost_price": uc_item.get("costPrice"),
        "mrp": uc_item.get("maxRetailPrice"),
        "ean": uc_item.get("ean") or uc_item.get("upc") or uc_item.get("scanIdentifier"),
        "hsn_code": uc_item.get("hsnCode"),
        "enabled": uc_item.get("enabled", True),
    }


def load_catalog(db_conn, uc_items):
    """
    Load UC catalog items into stock_items and stock_categories tables.

    Args:
        db_conn: PostgreSQL connection
        uc_items: List of raw UC itemType dicts

    Returns:
        dict with counts of items and categories loaded
    """
    if not uc_items:
        return {"items": 0, "categories": 0}

    items = [extract_sku_fields(item) for item in uc_items]

    # Collect unique categories
    categories = {}
    for item in items:
        cat = item["category_code"]
        if cat and cat not in categories:
            categories[cat] = {"name": cat, "source_id": None}

    # Upsert categories
    cat_count = _upsert_categories(db_conn, list(categories.values()))

    # Upsert items
    item_count = _upsert_items(db_conn, items)

    logger.info("Loaded %d categories, %d items", cat_count, item_count)
    return {"items": item_count, "categories": cat_count}


def _upsert_categories(db_conn, categories):
    """Upsert stock categories."""
    if not categories:
        return 0
    sql = """
        INSERT INTO stock_categories (name, source_id)
        VALUES (%(name)s, %(source_id)s)
        ON CONFLICT (name) DO UPDATE SET
            source_id = COALESCE(EXCLUDED.source_id, stock_categories.source_id),
            updated_at = NOW()
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, categories)
    db_conn.commit()
    return len(categories)


def _upsert_items(db_conn, items):
    """Upsert stock items from extracted fields."""
    if not items:
        return 0
    sql = """
        INSERT INTO stock_items (name, sku_code, category_name, brand, cost_price,
                                 mrp, ean, hsn_code, is_active)
        VALUES (%(sku_code)s, %(sku_code)s, %(category_code)s, %(brand)s,
                %(cost_price)s, %(mrp)s, %(ean)s, %(hsn_code)s, %(enabled)s)
        ON CONFLICT (name) DO UPDATE SET
            sku_code = EXCLUDED.sku_code,
            category_name = EXCLUDED.category_name,
            brand = EXCLUDED.brand,
            cost_price = EXCLUDED.cost_price,
            mrp = EXCLUDED.mrp,
            ean = EXCLUDED.ean,
            hsn_code = EXCLUDED.hsn_code,
            is_active = EXCLUDED.is_active,
            updated_at = NOW()
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, items, page_size=1000)
    db_conn.commit()
    return len(items)


def get_all_sku_codes(db_conn):
    """Get all SKU codes from the database (for inventory snapshot chunking)."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT sku_code FROM stock_items WHERE sku_code IS NOT NULL ORDER BY sku_code")
        return [row[0] for row in cur.fetchall()]
