"""
Catalog ingestion — pull SKU master data from Unicommerce.

Brand mapping: UC's `brand` field = real brand (WINSOR & NEWTON, PEBEO, etc.)
              UC's `categoryCode` = product category (ACRYLIC PAINTS, OIL PAINTS, etc.)

Our `stock_categories` table = brands (for reorder grouping by supplier/brand).
Our `stock_items.category_name` = brand name.
Our `stock_items.stock_group` = UC product category (for reference).

Maps to: stock_items, stock_categories tables.
"""
import logging
import psycopg2.extras

logger = logging.getLogger(__name__)

# Fallback brand for items with no brand field
UNKNOWN_BRAND = "UNBRANDED"


def pull_all_skus(client):
    """Pull all SKUs from UC (~23K items, single call)."""
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
    brand = (uc_item.get("brand") or "").strip()
    if not brand:
        # Try to infer brand from name (e.g. "Pebeo Studio Acrylics..." -> PEBEO)
        brand = UNKNOWN_BRAND
    return {
        "sku_code": uc_item.get("skuCode", ""),
        "display_name": uc_item.get("name", ""),  # actual product name for display
        "category_code": brand.upper(),  # brand = our category (for grouping)
        "product_category": uc_item.get("categoryCode", ""),  # UC product category
        "brand": brand,
        "cost_price": uc_item.get("costPrice") or uc_item.get("basePrice"),
        "mrp": uc_item.get("maxRetailPrice") or uc_item.get("price"),
        "ean": uc_item.get("ean") or uc_item.get("upc") or uc_item.get("scanIdentifier"),
        "hsn_code": uc_item.get("hsnCode"),
        "enabled": uc_item.get("enabled", True),
    }


def load_catalog(db_conn, uc_items):
    """Load UC catalog items into stock_items and stock_categories tables.

    stock_categories = brands (WINSOR & NEWTON, PEBEO, etc.)
    stock_items.category_name = brand name (for grouping)
    stock_items.stock_group = UC product category (ACRYLIC PAINTS, etc.)
    """
    if not uc_items:
        return {"items": 0, "categories": 0}

    items = [extract_sku_fields(item) for item in uc_items]

    # Collect unique brands as categories
    categories = {}
    for item in items:
        brand = item["category_code"]  # brand name uppercased
        if brand and brand not in categories:
            categories[brand] = {"name": brand, "source_id": None}

    cat_count = _upsert_categories(db_conn, list(categories.values()))
    item_count = _upsert_items(db_conn, items)

    logger.info("Loaded %d brands (categories), %d items", cat_count, item_count)
    return {"items": item_count, "categories": cat_count}


def _upsert_categories(db_conn, categories):
    """Upsert stock categories (= brands)."""
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
    """Upsert stock items. category_name = brand, stock_group = UC product category."""
    if not items:
        return 0
    sql = """
        INSERT INTO stock_items (name, sku_code, part_no, category_name, stock_group, brand,
                                 cost_price, mrp, ean, hsn_code, is_active)
        VALUES (%(sku_code)s, %(sku_code)s, %(display_name)s, %(category_code)s,
                %(product_category)s, %(brand)s, %(cost_price)s, %(mrp)s, %(ean)s,
                %(hsn_code)s, %(enabled)s)
        ON CONFLICT (name) DO UPDATE SET
            sku_code = EXCLUDED.sku_code,
            part_no = EXCLUDED.part_no,
            category_name = EXCLUDED.category_name,
            stock_group = EXCLUDED.stock_group,
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
