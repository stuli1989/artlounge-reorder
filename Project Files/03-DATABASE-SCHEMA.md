# 03 — Database Schema

## Overview

PostgreSQL database that stores:
1. Master data synced from Tally (stock items, categories, parties)
2. Transaction data synced from Tally (inventory vouchers)
3. Computed data (daily positions, velocities, reorder alerts)
4. Configuration data (party classification, supplier lead times)

## Schema

```sql
-- =============================================================
-- MASTER DATA (synced from Tally)
-- =============================================================

CREATE TABLE stock_categories (
    id              SERIAL PRIMARY KEY,
    tally_name      TEXT UNIQUE NOT NULL,      -- Exact name from Tally (= brand name)
    parent          TEXT,                       -- Parent category if nested, usually "Primary"
    tally_master_id TEXT,                       -- Tally's internal MasterId
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for lookups
CREATE INDEX idx_stock_categories_name ON stock_categories(tally_name);


CREATE TABLE stock_items (
    id              SERIAL PRIMARY KEY,
    tally_name      TEXT UNIQUE NOT NULL,      -- Full SKU name from Tally
    stock_group     TEXT,                       -- Tally stock group (product sub-type)
    category_name   TEXT NOT NULL,             -- FK reference by name to stock_categories.tally_name (= BRAND)
    base_unit       TEXT,                       -- "pcs", "nos", etc.
    tally_master_id TEXT,                       -- Tally's internal MasterId
    
    -- Current state (updated by nightly sync)
    closing_balance NUMERIC DEFAULT 0,         -- Current stock quantity
    closing_value   NUMERIC DEFAULT 0,         -- Current stock value (₹)
    
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stock_items_category ON stock_items(category_name);
CREATE INDEX idx_stock_items_name ON stock_items(tally_name);


-- =============================================================
-- CONFIGURATION DATA (manually maintained)
-- =============================================================

CREATE TABLE parties (
    id              SERIAL PRIMARY KEY,
    tally_name      TEXT UNIQUE NOT NULL,       -- Exact party/ledger name from Tally
    tally_parent    TEXT,                        -- Tally ledger group (Sundry Debtors, etc.)
    
    -- Manual classification
    channel         TEXT NOT NULL DEFAULT 'unclassified',
    -- Allowed values:
    --   'supplier'     — Speedball Art Products LLC, Winsor & Newton, etc.
    --   'wholesale'    — Hindustan Trading, A N Commtrade, etc.
    --   'online'       — MAGENTO2
    --   'store'        — Art Lounge India, Counter Collection - QR
    --   'internal'     — Art Lounge India - Purchase
    --   'ignore'       — Physical Stock, system adjustments
    --   'unclassified' — New party, needs manual tagging
    
    -- Optional: link supplier parties to a supplier record
    supplier_id     INTEGER REFERENCES suppliers(id),
    
    classified_at   TIMESTAMPTZ,               -- When was this party classified
    notes           TEXT,                        -- Any notes about this party
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_channel CHECK (channel IN (
        'supplier', 'wholesale', 'online', 'store', 'internal', 'ignore', 'unclassified'
    ))
);

CREATE INDEX idx_parties_channel ON parties(channel);
CREATE INDEX idx_parties_name ON parties(tally_name);


CREATE TABLE suppliers (
    id              SERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,       -- Display name (e.g., "Speedball")
    tally_party     TEXT,                        -- Corresponding Tally party name
    
    -- Lead times in days
    lead_time_sea   INTEGER,                    -- Sea freight lead time (e.g., 180)
    lead_time_air   INTEGER,                    -- Air freight lead time (e.g., 30)
    lead_time_default INTEGER NOT NULL,         -- Which one to use by default
    
    -- Ordering info
    currency        TEXT DEFAULT 'USD',
    min_order_value NUMERIC,                    -- Minimum order amount if any
    typical_order_months INTEGER DEFAULT 6,     -- How often you typically order
    
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);


-- =============================================================
-- TRANSACTION DATA (synced from Tally)
-- =============================================================

CREATE TABLE transactions (
    id              SERIAL PRIMARY KEY,
    
    -- From Tally voucher
    txn_date        DATE NOT NULL,
    party_name      TEXT NOT NULL,              -- Links to parties.tally_name
    voucher_type    TEXT NOT NULL,              -- "Sales", "Sales-Tally", "Purchase", etc.
    voucher_number  TEXT,
    stock_item_name TEXT NOT NULL,              -- Links to stock_items.tally_name
    
    -- Quantities (always positive; direction indicated by is_inward)
    quantity        NUMERIC NOT NULL,
    is_inward       BOOLEAN NOT NULL,           -- TRUE = purchase/inward, FALSE = sale/outward
    
    -- Value
    rate            NUMERIC,
    amount          NUMERIC,
    
    -- Denormalized channel (from parties table, for fast queries)
    channel         TEXT,                        -- Copied from parties.channel at sync time
    
    -- Tally tracking
    tally_master_id TEXT,                        -- Voucher MasterId for dedup
    tally_alter_id  TEXT,                        -- AlterId for delta detection
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    -- Prevent duplicate imports
    UNIQUE(txn_date, voucher_number, stock_item_name, quantity, is_inward)
);

CREATE INDEX idx_txn_date ON transactions(txn_date);
CREATE INDEX idx_txn_stock_item ON transactions(stock_item_name);
CREATE INDEX idx_txn_party ON transactions(party_name);
CREATE INDEX idx_txn_channel ON transactions(channel);
CREATE INDEX idx_txn_item_date ON transactions(stock_item_name, txn_date);


-- =============================================================
-- COMPUTED DATA (rebuilt after each sync)
-- =============================================================

-- Daily stock position for every SKU
-- This is the reconstructed "what was the stock level on each day?"
CREATE TABLE daily_stock_positions (
    id              SERIAL PRIMARY KEY,
    stock_item_name TEXT NOT NULL,
    position_date   DATE NOT NULL,
    
    opening_qty     NUMERIC NOT NULL,           -- Stock at start of day
    inward_qty      NUMERIC DEFAULT 0,          -- Total inward on this day
    outward_qty     NUMERIC DEFAULT 0,          -- Total outward on this day
    closing_qty     NUMERIC NOT NULL,           -- Stock at end of day
    
    -- Channel breakdown of outward
    wholesale_out   NUMERIC DEFAULT 0,
    online_out      NUMERIC DEFAULT 0,
    store_out       NUMERIC DEFAULT 0,
    
    -- Status
    is_in_stock     BOOLEAN NOT NULL,           -- closing_qty > 0
    
    UNIQUE(stock_item_name, position_date)
);

CREATE INDEX idx_daily_pos_item ON daily_stock_positions(stock_item_name);
CREATE INDEX idx_daily_pos_date ON daily_stock_positions(position_date);
CREATE INDEX idx_daily_pos_in_stock ON daily_stock_positions(stock_item_name, is_in_stock);


-- Per-SKU computed metrics (the core output)
CREATE TABLE sku_metrics (
    id                      SERIAL PRIMARY KEY,
    stock_item_name         TEXT UNIQUE NOT NULL,
    category_name           TEXT NOT NULL,              -- Brand
    
    -- Current state
    current_stock           NUMERIC NOT NULL,
    
    -- Velocity (units per day, calculated over in-stock days only)
    wholesale_velocity      NUMERIC DEFAULT 0,          -- Wholesale units/day
    online_velocity         NUMERIC DEFAULT 0,          -- Online units/day
    total_velocity          NUMERIC DEFAULT 0,          -- All channels units/day
    
    -- Velocity period info
    total_in_stock_days     INTEGER DEFAULT 0,          -- Days used for velocity calc
    velocity_start_date     DATE,                        -- Earliest in-stock date used
    velocity_end_date       DATE,                        -- Latest in-stock date used
    
    -- Stock-out tracking
    days_to_stockout        NUMERIC,                    -- Current stock / total velocity
    estimated_stockout_date DATE,                        -- Today + days_to_stockout
    
    -- Import history
    last_import_date        DATE,                        -- Most recent Purchase from supplier
    last_import_qty         NUMERIC,                     -- Quantity of last import
    last_import_supplier    TEXT,                         -- Supplier name
    
    -- Reorder status
    reorder_status          TEXT DEFAULT 'ok',           -- 'critical', 'warning', 'ok', 'out_of_stock', 'no_data'
    reorder_qty_suggested   NUMERIC,                     -- Suggested order quantity
    
    -- Metadata
    computed_at             TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_reorder_status CHECK (reorder_status IN (
        'critical', 'warning', 'ok', 'out_of_stock', 'no_data'
    ))
);

CREATE INDEX idx_sku_metrics_category ON sku_metrics(category_name);
CREATE INDEX idx_sku_metrics_status ON sku_metrics(reorder_status);
CREATE INDEX idx_sku_metrics_stockout ON sku_metrics(days_to_stockout);


-- Per-brand rollup
CREATE TABLE brand_metrics (
    id                      SERIAL PRIMARY KEY,
    category_name           TEXT UNIQUE NOT NULL,        -- Brand name
    
    total_skus              INTEGER DEFAULT 0,
    in_stock_skus           INTEGER DEFAULT 0,           -- current_stock > 0
    out_of_stock_skus       INTEGER DEFAULT 0,           -- current_stock <= 0
    critical_skus           INTEGER DEFAULT 0,           -- days_to_stockout < 30
    warning_skus            INTEGER DEFAULT 0,           -- days_to_stockout 30-90
    ok_skus                 INTEGER DEFAULT 0,           -- days_to_stockout > 90
    no_data_skus            INTEGER DEFAULT 0,           -- No transactions to compute velocity
    
    -- Weighted average days to stockout (weighted by velocity — fast movers matter more)
    avg_days_to_stockout    NUMERIC,
    
    -- Supplier info
    primary_supplier        TEXT,
    supplier_lead_time      INTEGER,                     -- Default lead time in days
    
    computed_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_brand_metrics_name ON brand_metrics(category_name);


-- =============================================================
-- SYNC TRACKING
-- =============================================================

CREATE TABLE sync_log (
    id              SERIAL PRIMARY KEY,
    sync_started    TIMESTAMPTZ NOT NULL,
    sync_completed  TIMESTAMPTZ,
    status          TEXT DEFAULT 'running',     -- 'running', 'completed', 'failed'
    
    -- Counts
    categories_synced   INTEGER DEFAULT 0,
    items_synced        INTEGER DEFAULT 0,
    transactions_synced INTEGER DEFAULT 0,
    new_parties_found   INTEGER DEFAULT 0,      -- Unclassified parties discovered
    
    -- Dates covered
    txn_from_date   DATE,
    txn_to_date     DATE,
    
    error_message   TEXT,
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

## Key Design Decisions

### Why denormalize channel into transactions?

The `transactions.channel` column duplicates data from `parties.channel`. This is intentional — the velocity computation queries need to filter by channel, and joining to the parties table on every row of a 100K+ transaction table is unnecessarily expensive. We copy the channel at sync time. If a party's classification changes, we re-sync the channel column.

### Why reconstruct daily positions instead of using Tally's closing balance?

Tally gives us the CURRENT closing balance, but we need the HISTORICAL position — what was the stock level on June 8? On July 15? The daily_stock_positions table reconstructs this from the opening balance + cumulative transactions. This is essential for the velocity calculation, which needs to know which days were "in stock" vs "out of stock."

### Why store transactions with a unique constraint instead of using Tally IDs?

Tally's MasterId and AlterId are useful for delta detection but may not be reliably exposed through all XML request types. The unique constraint on (date, voucher_number, stock_item, quantity, is_inward) prevents duplicate imports even if we re-pull the same date range. This is a pragmatic dedup strategy.

## Estimated Data Volumes

| Table | Estimated Rows | Growth Rate |
|-------|---------------|-------------|
| stock_categories | 20-50 | Static (new brands rare) |
| stock_items | 5,000-15,000 | Slow (new products added occasionally) |
| parties | 100-300 | Slow (new customers occasionally) |
| suppliers | 10-30 | Static |
| transactions | 50,000-200,000/year | ~200-800/day |
| daily_stock_positions | 5,000 items × 365 days = 1.8M/year | ~5,000/day |
| sku_metrics | 5,000-15,000 | Recomputed nightly |
| brand_metrics | 20-50 | Recomputed nightly |

Total database size estimate: 500MB - 2GB after first year. Well within a small Postgres instance.
