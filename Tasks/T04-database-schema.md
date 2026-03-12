# T04: Database Schema

## Prerequisites
- T01 completed (project structure exists)
- **Manual:** PostgreSQL installed, database `artlounge_reorder` created with user `reorder_app`

## Objective
Create the complete PostgreSQL schema file with all tables, indexes, and constraints.

## File to Create

### `db/schema.sql`

Create these tables in this order (respecting foreign key dependencies):

#### 1. `suppliers` — International brands/suppliers
```sql
CREATE TABLE suppliers (
    id              SERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,       -- Display name (e.g., "Speedball")
    tally_party     TEXT,                        -- Corresponding Tally party name
    lead_time_sea   INTEGER,                    -- Sea freight lead time in days (e.g., 180)
    lead_time_air   INTEGER,                    -- Air freight lead time in days (e.g., 30)
    lead_time_default INTEGER NOT NULL,         -- Default lead time to use
    currency        TEXT DEFAULT 'USD',
    min_order_value NUMERIC,
    typical_order_months INTEGER DEFAULT 6,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### 2. `stock_categories` — Brands (Tally stock categories)
```sql
CREATE TABLE stock_categories (
    id              SERIAL PRIMARY KEY,
    tally_name      TEXT UNIQUE NOT NULL,      -- Brand name from Tally
    parent          TEXT,                       -- Usually "Primary"
    tally_master_id TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_stock_categories_name ON stock_categories(tally_name);
```

#### 3. `stock_items` — SKUs
```sql
CREATE TABLE stock_items (
    id              SERIAL PRIMARY KEY,
    tally_name      TEXT UNIQUE NOT NULL,      -- Full SKU name
    stock_group     TEXT,                       -- Product sub-type
    category_name   TEXT NOT NULL,             -- Brand (FK to stock_categories.tally_name)
    base_unit       TEXT,                       -- "pcs", "nos"
    tally_master_id TEXT,
    closing_balance NUMERIC DEFAULT 0,         -- Current stock qty
    closing_value   NUMERIC DEFAULT 0,         -- Current stock value (INR)
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_stock_items_category ON stock_items(category_name);
CREATE INDEX idx_stock_items_name ON stock_items(tally_name);
```

#### 4. `parties` — Customers, suppliers, internal entities
```sql
CREATE TABLE parties (
    id              SERIAL PRIMARY KEY,
    tally_name      TEXT UNIQUE NOT NULL,
    tally_parent    TEXT,                        -- Ledger group (Sundry Debtors, etc.)
    channel         TEXT NOT NULL DEFAULT 'unclassified',
    supplier_id     INTEGER REFERENCES suppliers(id),
    classified_at   TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_channel CHECK (channel IN (
        'supplier', 'wholesale', 'online', 'store', 'internal', 'ignore', 'unclassified'
    ))
);
CREATE INDEX idx_parties_channel ON parties(channel);
CREATE INDEX idx_parties_name ON parties(tally_name);
```

Channel definitions:
- `supplier` — International brand you import from (Speedball Art Products LLC)
- `wholesale` — Retail shops/distributors buying from you (Hindustan Trading)
- `online` — E-commerce platform (MAGENTO2)
- `store` — Own retail store (Art Lounge India, Counter Collection - QR)
- `internal` — Accounting entries (Art Lounge India - Purchase)
- `ignore` — System adjustments (Physical Stock)
- `unclassified` — New party, needs human review

#### 5. `transactions` — Inventory vouchers from Tally
```sql
CREATE TABLE transactions (
    id              SERIAL PRIMARY KEY,
    txn_date        DATE NOT NULL,
    party_name      TEXT NOT NULL,
    voucher_type    TEXT NOT NULL,              -- "Sales", "Sales-Tally", "Purchase", etc.
    voucher_number  TEXT,
    stock_item_name TEXT NOT NULL,
    quantity        NUMERIC NOT NULL,           -- Always positive
    is_inward       BOOLEAN NOT NULL,           -- TRUE = purchase/inward, FALSE = sale/outward
    rate            NUMERIC,
    amount          NUMERIC,
    channel         TEXT,                        -- Denormalized from parties.channel
    tally_master_id TEXT,
    tally_alter_id  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(txn_date, voucher_number, stock_item_name, quantity, is_inward)
);
CREATE INDEX idx_txn_date ON transactions(txn_date);
CREATE INDEX idx_txn_stock_item ON transactions(stock_item_name);
CREATE INDEX idx_txn_party ON transactions(party_name);
CREATE INDEX idx_txn_channel ON transactions(channel);
CREATE INDEX idx_txn_item_date ON transactions(stock_item_name, txn_date);
```

#### 6. `daily_stock_positions` — Reconstructed daily stock levels
```sql
CREATE TABLE daily_stock_positions (
    id              SERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    position_date   DATE NOT NULL,
    opening_qty     NUMERIC NOT NULL,
    inward_qty      NUMERIC DEFAULT 0,
    outward_qty     NUMERIC DEFAULT 0,
    closing_qty     NUMERIC NOT NULL,
    wholesale_out   NUMERIC DEFAULT 0,
    online_out      NUMERIC DEFAULT 0,
    store_out       NUMERIC DEFAULT 0,
    is_in_stock     BOOLEAN NOT NULL,           -- closing_qty > 0
    UNIQUE(stock_item_name, position_date)
);
CREATE INDEX idx_daily_pos_item ON daily_stock_positions(stock_item_name);
CREATE INDEX idx_daily_pos_date ON daily_stock_positions(position_date);
CREATE INDEX idx_daily_pos_in_stock ON daily_stock_positions(stock_item_name, is_in_stock);
```

#### 7. `sku_metrics` — Per-SKU computed metrics
```sql
CREATE TABLE sku_metrics (
    id                      SERIAL PRIMARY KEY,
    stock_item_name         TEXT UNIQUE NOT NULL,
    category_name           TEXT NOT NULL,
    current_stock           NUMERIC NOT NULL,
    wholesale_velocity      NUMERIC DEFAULT 0,
    online_velocity         NUMERIC DEFAULT 0,
    total_velocity          NUMERIC DEFAULT 0,
    total_in_stock_days     INTEGER DEFAULT 0,
    velocity_start_date     DATE,
    velocity_end_date       DATE,
    days_to_stockout        NUMERIC,
    estimated_stockout_date DATE,
    last_import_date        DATE,
    last_import_qty         NUMERIC,
    last_import_supplier    TEXT,
    reorder_status          TEXT DEFAULT 'ok',
    reorder_qty_suggested   NUMERIC,
    computed_at             TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_reorder_status CHECK (reorder_status IN (
        'critical', 'warning', 'ok', 'out_of_stock', 'no_data'
    ))
);
CREATE INDEX idx_sku_metrics_category ON sku_metrics(category_name);
CREATE INDEX idx_sku_metrics_status ON sku_metrics(reorder_status);
CREATE INDEX idx_sku_metrics_stockout ON sku_metrics(days_to_stockout);
```

#### 8. `brand_metrics` — Per-brand rollup
```sql
CREATE TABLE brand_metrics (
    id                      SERIAL PRIMARY KEY,
    category_name           TEXT UNIQUE NOT NULL,
    total_skus              INTEGER DEFAULT 0,
    in_stock_skus           INTEGER DEFAULT 0,
    out_of_stock_skus       INTEGER DEFAULT 0,
    critical_skus           INTEGER DEFAULT 0,
    warning_skus            INTEGER DEFAULT 0,
    ok_skus                 INTEGER DEFAULT 0,
    no_data_skus            INTEGER DEFAULT 0,
    avg_days_to_stockout    NUMERIC,
    primary_supplier        TEXT,
    supplier_lead_time      INTEGER,
    computed_at             TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_brand_metrics_name ON brand_metrics(category_name);
```

#### 9. `sync_log` — Sync audit trail
```sql
CREATE TABLE sync_log (
    id              SERIAL PRIMARY KEY,
    sync_started    TIMESTAMPTZ NOT NULL,
    sync_completed  TIMESTAMPTZ,
    status          TEXT DEFAULT 'running',
    categories_synced   INTEGER DEFAULT 0,
    items_synced        INTEGER DEFAULT 0,
    transactions_synced INTEGER DEFAULT 0,
    new_parties_found   INTEGER DEFAULT 0,
    txn_from_date   DATE,
    txn_to_date     DATE,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

## Additional: Seed Data File

### `config/suppliers.json`
```json
[
  {
    "name": "Speedball Art Products",
    "tally_party": "Speedball Art Products, LLC",
    "lead_time_sea": 90,
    "lead_time_air": 30,
    "lead_time_default": 90,
    "currency": "USD",
    "typical_order_months": 3,
    "notes": "Default 90-day lead time — update with actual values via Supplier Management"
  },
  {
    "name": "Winsor & Newton",
    "tally_party": "Winsor & Newton",
    "lead_time_sea": 90,
    "lead_time_air": 21,
    "lead_time_default": 90,
    "currency": "GBP",
    "typical_order_months": 3,
    "notes": "Default 90-day lead time — update with actual values via Supplier Management"
  }
]
```

**Note:** All suppliers are seeded with a default 90-day (3-month) lead time. Actual lead times should be updated per-supplier via the Supplier Management UI once the system is running.

## Acceptance Criteria
- [ ] `db/schema.sql` creates all 9 tables in correct dependency order
- [ ] All indexes defined
- [ ] Channel CHECK constraint on parties table
- [ ] Reorder status CHECK constraint on sku_metrics table
- [ ] UNIQUE constraints on transactions (dedup) and daily_stock_positions
- [ ] `config/suppliers.json` has seed data for known suppliers
- [ ] Schema can be run with: `psql -U reorder_app -d artlounge_reorder -f db/schema.sql`
