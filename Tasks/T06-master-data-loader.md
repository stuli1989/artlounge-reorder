# T06: Master Data Loader

## Prerequisites
- T04 completed (database schema exists and tables created)
- T05 completed (XML parsers exist)

## Objective
Create a script/module that loads parsed stock categories, stock items, and ledgers into the PostgreSQL database. Also load supplier seed data.

## File to Create

### `extraction/data_loader.py`

Functions:

#### 1. `get_db_connection(database_url: str = None)`
- Use `psycopg2.connect()` with the DATABASE_URL from settings
- Return a connection object
- If no URL provided, use `config.settings.DATABASE_URL`

#### 2. `load_stock_categories(db_conn, categories: list[dict]) -> int`
- UPSERT into `stock_categories` table
- Use `ON CONFLICT (tally_name) DO UPDATE SET parent=EXCLUDED.parent, updated_at=NOW()`
- Return count of rows affected

#### 3. `load_stock_items(db_conn, items: list[dict]) -> int`
- UPSERT into `stock_items` table
- Map parsed fields to table columns:
  - `name` → `tally_name`
  - `category` → `category_name`
  - `stock_group` → `stock_group`
  - `base_unit` → `base_unit`
  - `closing_balance` → `closing_balance`
  - `closing_value` → `closing_value`
- Use `ON CONFLICT (tally_name) DO UPDATE` for all mutable fields
- Return count

#### 4. `load_ledgers_as_parties(db_conn, ledgers: list[dict]) -> int`
- INSERT into `parties` table with channel='unclassified'
- Use `ON CONFLICT (tally_name) DO NOTHING` — don't overwrite existing classifications
- Map: `name` → `tally_name`, `parent` → `tally_parent`
- Return count of NEW parties inserted (not existing ones)

#### 5. `load_suppliers_from_json(db_conn, json_path: str) -> int`
- Read `config/suppliers.json`
- UPSERT into `suppliers` table
- Return count

#### 6. `load_all_master_data(tally_client, db_conn) -> dict`
High-level orchestrator:
```python
def load_all_master_data(tally_client, db_conn) -> dict:
    """Pull master data from Tally and load into database. Returns counts."""
    from extraction.xml_requests import STOCK_CATEGORIES_REQUEST, STOCK_ITEMS_REQUEST, LEDGER_LIST_REQUEST
    from extraction.xml_parser import parse_stock_categories, parse_stock_items, parse_ledgers

    # Pull and load categories
    raw = tally_client.send_request_raw(STOCK_CATEGORIES_REQUEST)
    categories = parse_stock_categories(raw)
    cat_count = load_stock_categories(db_conn, categories)

    # Pull and load stock items
    raw = tally_client.send_request_raw(STOCK_ITEMS_REQUEST, timeout=600)
    items = parse_stock_items(raw)
    item_count = load_stock_items(db_conn, items)

    # Pull and load parties
    raw = tally_client.send_request_raw(LEDGER_LIST_REQUEST)
    ledgers = parse_ledgers(raw)
    party_count = load_ledgers_as_parties(db_conn, ledgers)

    return {
        'categories': cat_count,
        'items': item_count,
        'new_parties': party_count,
    }
```

## Important Notes
- All database operations should use parameterized queries (prevent SQL injection)
- Commit after each table's batch load, not after every row
- Use `cursor.executemany()` or batch inserts for performance with large datasets
- The ledger loader intentionally uses `DO NOTHING` on conflict — we never want to overwrite a manually classified party

## Acceptance Criteria
- [ ] All load functions use parameterized queries
- [ ] UPSERT logic correct: categories/items update on conflict, parties don't overwrite
- [ ] `load_all_master_data()` orchestrates full pull-parse-load cycle
- [ ] Supplier seed data loaded from JSON file
- [ ] Returns counts for logging/verification
- [ ] Commits after each table batch (not per-row)
