"""
Master data loader — loads stock categories, stock items, ledgers,
and supplier seed data into PostgreSQL.
"""
import json
import os
import psycopg2
import psycopg2.extras


def get_db_connection(database_url: str = None):
    """Get a PostgreSQL connection."""
    if database_url is None:
        from config.settings import DATABASE_URL
        database_url = DATABASE_URL
    return psycopg2.connect(database_url)


def load_stock_categories(db_conn, categories: list[dict]) -> int:
    """UPSERT stock categories into database. Returns count."""
    if not categories:
        return 0
    sql = """
        INSERT INTO stock_categories (tally_name, parent, tally_master_id)
        VALUES (%(name)s, %(parent)s, %(tally_master_id)s)
        ON CONFLICT (tally_name) DO UPDATE SET
            parent = EXCLUDED.parent,
            tally_master_id = EXCLUDED.tally_master_id,
            updated_at = NOW()
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, categories)
    db_conn.commit()
    return len(categories)


def load_stock_items(db_conn, items: list[dict]) -> int:
    """UPSERT stock items into database. Returns count."""
    if not items:
        return 0
    sql = """
        INSERT INTO stock_items (tally_name, stock_group, category_name, base_unit,
                                 tally_master_id, opening_balance, closing_balance, closing_value, part_no)
        VALUES (%(name)s, %(stock_group)s, %(category)s, %(base_unit)s,
                %(tally_master_id)s, %(opening_balance)s, %(closing_balance)s, %(closing_value)s, %(part_no)s)
        ON CONFLICT (tally_name) DO UPDATE SET
            stock_group = EXCLUDED.stock_group,
            category_name = EXCLUDED.category_name,
            base_unit = EXCLUDED.base_unit,
            tally_master_id = EXCLUDED.tally_master_id,
            opening_balance = EXCLUDED.opening_balance,
            closing_balance = EXCLUDED.closing_balance,
            closing_value = EXCLUDED.closing_value,
            part_no = EXCLUDED.part_no,
            updated_at = NOW()
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, items, page_size=1000)
    db_conn.commit()
    return len(items)


def load_ledgers_as_parties(db_conn, ledgers: list[dict]) -> int:
    """INSERT ledgers as parties. DO NOTHING on conflict (never overwrite classifications)."""
    if not ledgers:
        return 0
    sql = """
        INSERT INTO parties (tally_name, tally_parent)
        VALUES (%(name)s, %(parent)s)
        ON CONFLICT (tally_name) DO NOTHING
    """
    with db_conn.cursor() as cur:
        before_count = _count_parties(cur)
        psycopg2.extras.execute_batch(cur, sql, ledgers)
        after_count = _count_parties(cur)
    db_conn.commit()
    return after_count - before_count


def _count_parties(cur) -> int:
    cur.execute("SELECT COUNT(*) FROM parties")
    return cur.fetchone()[0]


def load_suppliers_from_json(db_conn, json_path: str = None) -> int:
    """Load supplier seed data from JSON file."""
    if json_path is None:
        json_path = os.path.join(os.path.dirname(__file__), "..", "config", "suppliers.json")
    with open(json_path, "r") as f:
        suppliers = json.load(f)
    if not suppliers:
        return 0
    sql = """
        INSERT INTO suppliers (name, tally_party, lead_time_sea, lead_time_air,
                               lead_time_default, currency, typical_order_months, notes)
        VALUES (%(name)s, %(tally_party)s, %(lead_time_sea)s, %(lead_time_air)s,
                %(lead_time_default)s, %(currency)s, %(typical_order_months)s, %(notes)s)
        ON CONFLICT (name) DO UPDATE SET
            tally_party = EXCLUDED.tally_party,
            lead_time_sea = EXCLUDED.lead_time_sea,
            lead_time_air = EXCLUDED.lead_time_air,
            lead_time_default = EXCLUDED.lead_time_default,
            currency = EXCLUDED.currency,
            typical_order_months = EXCLUDED.typical_order_months,
            notes = EXCLUDED.notes,
            updated_at = NOW()
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, suppliers)
    db_conn.commit()
    return len(suppliers)


def load_all_master_data(tally_client, db_conn) -> dict:
    """Pull master data from Tally and load into database. Returns counts."""
    from extraction.xml_requests import (
        STOCK_CATEGORIES_REQUEST, STOCK_ITEMS_REQUEST, LEDGER_LIST_REQUEST,
    )
    from extraction.xml_parser import parse_stock_categories, parse_stock_items, parse_ledgers

    print("Loading stock categories...")
    raw = tally_client.send_request_raw(STOCK_CATEGORIES_REQUEST)
    categories = parse_stock_categories(raw)
    cat_count = load_stock_categories(db_conn, categories)
    print(f"  {cat_count} categories loaded")

    print("Loading stock items...")
    raw = tally_client.send_request_raw(STOCK_ITEMS_REQUEST, timeout=600)
    items = parse_stock_items(raw)
    item_count = load_stock_items(db_conn, items)
    print(f"  {item_count} items loaded")

    print("Loading ledgers as parties...")
    raw = tally_client.send_request_raw(LEDGER_LIST_REQUEST)
    ledgers = parse_ledgers(raw)
    party_count = load_ledgers_as_parties(db_conn, ledgers)
    print(f"  {party_count} new parties loaded")

    print("Loading supplier seed data...")
    sup_count = load_suppliers_from_json(db_conn)
    print(f"  {sup_count} suppliers loaded")

    return {
        "categories": cat_count,
        "items": item_count,
        "new_parties": party_count,
        "suppliers": sup_count,
    }


def load_master_data_from_files(db_conn, sample_dir: str = None) -> dict:
    """Load master data from cached XML files (for POC / no Tally connection)."""
    from extraction.xml_parser import parse_stock_categories, parse_stock_items, parse_ledgers

    if sample_dir is None:
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample_responses")

    print("Loading stock categories from file...")
    with open(os.path.join(sample_dir, "stock_categories.xml"), "rb") as f:
        categories = parse_stock_categories(f.read())
    cat_count = load_stock_categories(db_conn, categories)
    print(f"  {cat_count} categories loaded")

    print("Loading stock items from file...")
    with open(os.path.join(sample_dir, "stock_items.xml"), "rb") as f:
        items = parse_stock_items(f.read())
    item_count = load_stock_items(db_conn, items)
    print(f"  {item_count} items loaded")

    print("Loading ledgers from file...")
    with open(os.path.join(sample_dir, "ledgers.xml"), "rb") as f:
        ledgers = parse_ledgers(f.read())
    party_count = load_ledgers_as_parties(db_conn, ledgers)
    print(f"  {party_count} new parties loaded")

    print("Loading supplier seed data...")
    sup_count = load_suppliers_from_json(db_conn)
    print(f"  {sup_count} suppliers loaded")

    return {
        "categories": cat_count,
        "items": item_count,
        "new_parties": party_count,
        "suppliers": sup_count,
    }
