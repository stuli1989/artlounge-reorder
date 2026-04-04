# Procurement Pipeline: Price Lists, Budget-Aware PO Builder, Landed Cost & Document Verification

**Date:** 2026-04-04
**Status:** Approved for implementation
**Phases:** 3 (each delivers standalone value)

---

## Problem

The team builds purchase orders without cost visibility. They don't know the running total of a PO, can't set budget targets, and manually compare supplier documents (ORN, invoices) line-by-line against what was ordered. Supplier price lists come as messy PDFs and Excels with varying formats, and there's no system to store or track pricing over time. MRP calculation happens in Excel after goods arrive.

## Solution

A phased procurement pipeline that covers the full lifecycle: price list import, budget-aware PO building, landed cost calculation, MRP derivation, and automated document verification.

---

## Phase 1: Price Lists + Budget-Aware PO Builder

### 1.1 Supplier Price List Import

#### Upload Flow

```
User uploads PDF/Excel via dashboard
        |
Backend stores file, sends to LlamaIndex API (agentic tier)
        |
LlamaIndex returns structured markdown with HTML tables
        |
Python extraction layer: parse HTML tables -> raw line items
    {supplier_product_code, supplier_product_name, ean,
     list_price, discount_pct, net_price, qty, origin}
        |
SKU matching engine: match each line to stock_items
        |
Return preview to frontend (matched, unmatched, ambiguous)
        |
User reviews, confirms/corrects matches
        |
Save to supplier_prices (mark previous as is_current=FALSE)
```

#### LlamaIndex Integration

- **SDK:** `llama-cloud` Python package
- **Method:** `client.parsing.parse(tier="agentic", version="latest", upload_file=..., output_options={"markdown": {"tables": {"output_tables_as_markdown": False}}}, expand=["markdown_full"])`
- **API key:** Stored as environment variable `LLAMAINDEX_API_KEY`
- **Output:** HTML tables in markdown. Tested with a 13-page Winsor & Newton order confirmation (257 line items) — extracted all items with correct prices, discounts, and product codes.
- **Extraction:** BeautifulSoup parses `<table>` -> `<tr>` -> `<td>`. Column mapping is supplier-specific.

#### Supplier Column Mapping

Each supplier's documents have different column layouts. A stored mapping per supplier handles this:

- When first importing from a new supplier, user maps their columns to standard fields
- Mapping stored in `supplier_import_configs` table
- Subsequent imports from same supplier reuse the mapping
- If supplier changes format, user re-maps

**Standard fields to map to:** supplier_product_code, supplier_product_name, ean, list_price, discount_pct, net_price, qty, origin, moq, case_size

#### SKU Matching Strategy (3-tier)

Tested with real Winsor & Newton data: 87% match rate on tier 1 alone.

1. **Exact match on item_code** — supplier_product_code = stock_items.item_code
2. **EAN match** — supplier's barcode = stock_items.ean
3. **Fuzzy name match** — trigram similarity on display_name (reuses existing `/po-data/match` logic)

Each line item gets a match status:
- `matched` — confident single match (tier 1 or 2)
- `ambiguous` — multiple possible matches (user picks)
- `unmatched` — no match found (user manually assigns or skips)

#### Import Preview UI

After parsing + matching, user sees a review screen:

- Table showing: match status, supplier code, supplier name, matched SKU, our name, net price, action buttons
- Summary bar: "204 matched, 5 ambiguous, 26 unmatched"
- User confirms -> prices saved with `is_current=TRUE`, previous prices for same supplier set to `is_current=FALSE`

#### Discount Structure

Price lists capture the full discount structure, not just net price:
- `list_price` — catalog/gross price
- `discount_pct` — agreed discount percentage
- `net_price` — list_price * (1 - discount_pct/100)

This varies by:
- **Brand-wide discount** — all SKUs in a brand get same discount (simpler case)
- **SKU-level discount** — individual items have different discounts (complex case)
- **Origin-based pricing** — same SKU from China factory vs Europe factory has different prices/currencies

Multiple `supplier_prices` rows per item_code support origin-based pricing.

### 1.2 Budget-Aware PO Builder

#### Budget Bar (sticky, always visible)

Displays:
- **Running total** in supplier currency + INR equivalent
- **Budget target** with mode: floor ("need to reach"), ceiling ("can't exceed"), guide ("aiming for")
- **Progress bar** — visual percentage of target
- **Exchange rate** with buffer %: `effective_rate = base_rate * (1 + buffer_pct / 100)`
- **MOV indicator** — whether supplier's minimum order value is met
- **Item count** and count of items without price data
- **Save PO** and **Fill to Target** buttons

Example: EUR base rate = 90.00, buffer = 3%, effective rate = 92.70

#### Enhanced PO Table

New columns added to existing PO table:
- **Net Price** — from `supplier_prices WHERE is_current=TRUE`. Shows "—" with warning if no price.
- **Line Total** — net_price * order_qty, updates live on qty change
- **MOQ** — minimum order quantity. Amber highlight if qty < MOQ (warning, not blocking).
- **Case Size** — if set, nudge to round to nearest multiple ("Round to 6 or 12?")

Items without prices still appear and work — they just don't contribute to running total. A count shows how many items lack price data.

#### "Fill to Target" Assist

When current total < floor target, user clicks "Fill to Target":

1. Calculate gap: target - current_total
2. Find candidates, prioritized by:
   - Items in PO with order_qty < suggested_qty (bump to suggested)
   - Excluded items sorted by reorder urgency (lost_sales > urgent > reorder)
   - Items at MOQ that could go to next case_size multiple
3. Present suggestions in modal with checkboxes
4. User selects items -> Apply -> quantities updated

For ceiling mode: if total exceeds target, highlight items to reduce (lowest urgency first).

#### PO Lifecycle

```
[Draft] -- user builds, saves multiple times
   |
[Sent] -- user marks sent (records sent_at, locks prices/quantities)
   |
[Partial Received] -- some items received (future: GRN linking)
   |
[Received] -- all items received
   |
[Cancelled] -- PO cancelled
```

- Draft POs can be edited freely
- Sent POs are locked — prices and quantities frozen as a record
- Excel export still works, now pulling from saved PO data

---

## Phase 2: Landed Cost + MRP Calculation

### 2.1 Import Cost Input

After a PO is sent and import costs are sealed (freight, duty, clearance), user enters them per PO:

- **Freight cost** — total freight amount
- **Customs duty** — percentage or absolute amount
- **Clearance/handling** — customs clearance charges
- **Other costs** — miscellaneous
- **Distribution method** — how to allocate across line items: by_value (proportional to line total), by_weight, by_volume, or equal split

### 2.2 Landed Cost Engine

Per PO line item:

```
allocated_import_cost = distribute(total_import_costs, method, line_items)
landed_cost_per_unit_fcy = net_price  (in supplier currency)
landed_cost_per_unit_inr = (net_price * effective_exchange_rate) + allocated_import_cost_per_unit
```

Where `effective_exchange_rate = base_rate * (1 + buffer_pct / 100)`

Result: per-item `landed_cost_inr` stored on `po_lines`.

### 2.3 MRP Derivation

From landed cost, apply margin rules:

```
suggested_mrp = landed_cost_inr / (1 - target_margin_pct / 100)
```

Example: landed cost = INR 200, target margin = 40% -> MRP = 200 / 0.60 = INR 333

#### Pricing Strategies

Per-SKU or per-category (SKU-level overrides category-level):

- **distribution** — standard margin, wholesale + retail + online
- **retail_only** — higher margin, no wholesale distribution
- **mass_market** — competitive/lower margin for volume items

Each strategy has a `target_margin_pct`. Set once, rarely changed.

#### MRP Adjustment UI

- Table showing: item_code, name, landed_cost_inr, strategy, target_margin, suggested_mrp, final_mrp (editable)
- Bulk adjust by category
- Save updates `stock_items.mrp` and `po_lines.final_mrp`

---

## Phase 3: Document Verification (ORN + Invoice)

### 3.1 ORN (Order Receipt Note) Verification

After sending a PO, the supplier sends an ORN confirming the order.

**Flow:**
1. Upload ORN (PDF/Excel) -> LlamaIndex parses -> extract line items
2. Match line items to the related PO's `po_lines`
3. Compare field by field: qty, net_price, discount_pct, line_total
4. Generate comparison report:
   - **Exact match** — green, no action needed
   - **Price mismatch** — flag with diff (agreed EUR 0.90, ORN says EUR 0.95)
   - **Qty mismatch** — flag (ordered 120, ORN shows 100)
   - **Missing items** — in PO but not in ORN
   - **Extra items** — in ORN but not in PO

If ORN matches PO exactly, no upload needed — user can skip this step.

### 3.2 Invoice Verification

Supplier ships partial order (80 of 100 items). Invoice differs from ORN.

**Same flow as ORN**, but:
- Compares against PO (and optionally against ORN)
- Handles partial shipments — qty differences are expected, but price differences are not
- Flags if invoice total != sum of line items

### 3.3 Discrepancy Resolution

All outliers shown on one screen per document comparison:

- Per-item decision: **Accept** (update costing) or **Reject** (write back to supplier)
- If price discrepancy accepted: cascades to landed cost recalculation and MRP update
- Resolution tracked in `document_comparisons` table for audit

---

## Database Schema

### New Tables

#### `supplier_price_lists`
Tracks each imported price list document.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| supplier_id | INTEGER | FK -> suppliers, NOT NULL | |
| currency | TEXT | NOT NULL | EUR, USD, GBP, INR |
| source_filename | TEXT | NOT NULL | Original filename |
| source_type | TEXT | NOT NULL | 'pdf', 'excel', 'manual' |
| imported_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| valid_from | DATE | | User-entered, nullable |
| valid_until | DATE | | User-entered, nullable |
| notes | TEXT | | |
| raw_markdown | TEXT | | LlamaIndex parsed output |
| status | TEXT | NOT NULL DEFAULT 'active' | 'active', 'superseded', 'archived' |

#### `supplier_import_configs`
Column mapping per supplier for parsing imported documents.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| supplier_id | INTEGER | FK -> suppliers, UNIQUE | One config per supplier |
| column_mapping | JSONB | NOT NULL | {"product_code": 2, "list_price": 5, ...} |
| notes | TEXT | | Format description |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

#### `supplier_prices`
Per-SKU pricing from a price list.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| price_list_id | INTEGER | FK -> supplier_price_lists, NOT NULL | |
| item_code | TEXT | FK -> stock_items, NOT NULL | Matched SKU |
| supplier_product_code | TEXT | | Supplier's own code |
| supplier_product_name | TEXT | | Name from their document |
| ean | TEXT | | EAN/barcode if present |
| list_price | NUMERIC | | Before discount |
| discount_pct | NUMERIC | | e.g., 79.0 |
| net_price | NUMERIC | NOT NULL | After discount |
| currency | TEXT | NOT NULL | |
| moq | INTEGER | | Min order qty per SKU |
| case_size | INTEGER | | Order in multiples |
| origin | TEXT | | FRA, CHN, USA, etc. |
| is_current | BOOLEAN | NOT NULL DEFAULT TRUE | Latest price for this SKU+supplier |

UNIQUE constraint on (item_code, price_list_id) — one price per SKU per import.
When new price list imported: UPDATE supplier_prices SET is_current=FALSE WHERE supplier_id=X AND is_current=TRUE, then insert new rows.

#### `purchase_orders`
Persisted POs replacing ephemeral generation.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| po_number | TEXT | UNIQUE | Auto-generated or user-entered |
| supplier_id | INTEGER | FK -> suppliers, NOT NULL | |
| currency | TEXT | NOT NULL | |
| exchange_rate | NUMERIC | | Base rate to INR |
| exchange_rate_buffer_pct | NUMERIC | DEFAULT 0 | Buffer % for fluctuation |
| effective_exchange_rate | NUMERIC | | base * (1 + buffer/100) |
| budget_target | NUMERIC | | Target amount (nullable) |
| budget_mode | TEXT | | 'floor', 'ceiling', 'guide' |
| status | TEXT | NOT NULL DEFAULT 'draft' | 'draft','sent','partial_received','received','cancelled' |
| total_value | NUMERIC | | Sum of line totals (supplier currency) |
| total_value_inr | NUMERIC | | total_value * effective_exchange_rate |
| notes | TEXT | | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| sent_at | TIMESTAMPTZ | | When marked as sent |

#### `po_lines`
Individual items in a PO.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| po_id | INTEGER | FK -> purchase_orders, NOT NULL | |
| item_code | TEXT | FK -> stock_items, NOT NULL | |
| order_qty | INTEGER | NOT NULL | |
| list_price | NUMERIC | | Snapshot from supplier_prices |
| discount_pct | NUMERIC | | Snapshot |
| net_price | NUMERIC | | Snapshot |
| line_total | NUMERIC | | net_price * order_qty |
| suggested_qty | INTEGER | | System recommendation |
| moq | INTEGER | | Snapshot |
| case_size | INTEGER | | Snapshot |
| notes | TEXT | | |
| landed_cost_inr | NUMERIC | | Phase 2: per-unit landed cost |
| suggested_mrp | NUMERIC | | Phase 2: margin-derived MRP |
| final_mrp | NUMERIC | | Phase 2: after user adjustment |

UNIQUE constraint on (po_id, item_code).

#### `import_costs` (Phase 2)
Import costs per PO for landed cost calculation.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| po_id | INTEGER | FK -> purchase_orders, UNIQUE | One record per PO |
| freight_cost | NUMERIC | DEFAULT 0 | |
| duty_pct | NUMERIC | | Customs duty percentage |
| duty_amount | NUMERIC | | Or absolute duty amount |
| clearance_cost | NUMERIC | DEFAULT 0 | |
| other_costs | NUMERIC | DEFAULT 0 | |
| cost_distribution_method | TEXT | DEFAULT 'by_value' | 'by_value','by_weight','by_volume','equal' |
| notes | TEXT | | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

#### `pricing_strategies` (Phase 2)
Margin rules per SKU or category.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| item_code | TEXT | FK -> stock_items | Per-SKU override (nullable) |
| category_name | TEXT | | Per-brand default (nullable) |
| strategy_type | TEXT | NOT NULL | 'distribution','retail_only','mass_market' |
| target_margin_pct | NUMERIC | NOT NULL | e.g., 40.0 |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | |

CHECK: item_code IS NOT NULL OR category_name IS NOT NULL.
SKU-level overrides category-level.

#### `order_receipt_notes` (Phase 3)
Parsed ORN documents.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| po_id | INTEGER | FK -> purchase_orders | Linked PO |
| supplier_id | INTEGER | FK -> suppliers, NOT NULL | |
| orn_number | TEXT | | From document |
| orn_date | DATE | | |
| currency | TEXT | | |
| total_value | NUMERIC | | |
| source_filename | TEXT | | |
| raw_markdown | TEXT | | LlamaIndex output |
| status | TEXT | NOT NULL DEFAULT 'parsed' | 'parsed','matched','verified','disputed' |
| imported_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

#### `orn_lines` (Phase 3)

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| orn_id | INTEGER | FK -> order_receipt_notes, NOT NULL | |
| item_code | TEXT | FK -> stock_items | Matched SKU |
| supplier_product_code | TEXT | | |
| supplier_product_name | TEXT | | |
| qty | INTEGER | | |
| list_price | NUMERIC | | |
| discount_pct | NUMERIC | | |
| net_price | NUMERIC | | |
| line_total | NUMERIC | | |

#### `invoices` (Phase 3)

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| po_id | INTEGER | FK -> purchase_orders | Linked PO (nullable) |
| supplier_id | INTEGER | FK -> suppliers, NOT NULL | |
| invoice_number | TEXT | | |
| invoice_date | DATE | | |
| currency | TEXT | | |
| total_value | NUMERIC | | |
| source_filename | TEXT | | |
| raw_markdown | TEXT | | LlamaIndex output |
| status | TEXT | NOT NULL DEFAULT 'parsed' | 'parsed','matched','verified','disputed' |
| imported_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

#### `invoice_lines` (Phase 3)

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| invoice_id | INTEGER | FK -> invoices, NOT NULL | |
| item_code | TEXT | FK -> stock_items | Matched SKU |
| supplier_product_code | TEXT | | |
| supplier_product_name | TEXT | | |
| qty | INTEGER | | |
| list_price | NUMERIC | | |
| discount_pct | NUMERIC | | |
| net_price | NUMERIC | | |
| line_total | NUMERIC | | |

#### `document_comparisons` (Phase 3)
Tracks field-by-field comparison results.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | |
| comparison_type | TEXT | NOT NULL | 'orn_vs_po', 'invoice_vs_po', 'invoice_vs_orn' |
| source_id | INTEGER | NOT NULL | ORN or invoice ID |
| target_id | INTEGER | NOT NULL | PO or ORN ID |
| item_code | TEXT | | |
| field_name | TEXT | NOT NULL | 'net_price', 'qty', 'discount_pct', 'line_total' |
| expected_value | NUMERIC | | From PO/ORN |
| actual_value | NUMERIC | | From ORN/invoice |
| diff | NUMERIC | | actual - expected |
| status | TEXT | NOT NULL DEFAULT 'pending' | 'pending', 'accepted', 'rejected' |
| resolved_at | TIMESTAMPTZ | | |
| notes | TEXT | | |

### Modified Tables

#### `suppliers` — add columns:
- `default_moq_type` TEXT — 'per_sku', 'case_size', 'order_value', 'mixed'
- `default_exchange_rate` NUMERIC — last used rate for convenience

---

## API Endpoints

### Phase 1

**Price List Management:**
- `POST /api/price-lists/upload` — upload PDF/Excel, parse via LlamaIndex, return preview
- `POST /api/price-lists/{id}/confirm` — confirm matches, save to supplier_prices
- `GET /api/price-lists` — list all imports (filterable by supplier)
- `GET /api/price-lists/{id}` — get import details + line items
- `GET /api/suppliers/{id}/current-prices` — get all is_current=TRUE prices for a supplier
- `PUT /api/supplier-import-configs/{supplier_id}` — save/update column mapping

**PO Management:**
- `POST /api/purchase-orders` — create draft PO
- `GET /api/purchase-orders` — list POs (filterable by supplier, status)
- `GET /api/purchase-orders/{id}` — get PO with lines
- `PUT /api/purchase-orders/{id}` — update draft PO (lines, budget, notes)
- `PATCH /api/purchase-orders/{id}/status` — change status (draft->sent, etc.)
- `POST /api/purchase-orders/{id}/fill-to-target` — get fill suggestions
- `POST /api/purchase-orders/{id}/export` — generate Excel

**Budget Calculation:**
- `GET /api/brands/{category_name}/po-data` — existing endpoint, enhanced with price data from supplier_prices
- Price fields added to PoDataItem response: net_price, list_price, discount_pct, moq, case_size, has_price

### Phase 2

- `POST /api/purchase-orders/{id}/import-costs` — enter import costs
- `GET /api/purchase-orders/{id}/landed-costs` — calculate and return per-item landed costs
- `GET /api/purchase-orders/{id}/mrp-suggestions` — calculate MRPs from landed cost + strategy
- `PUT /api/purchase-orders/{id}/mrp` — save final MRPs
- `GET /api/pricing-strategies` — list strategies
- `PUT /api/pricing-strategies` — create/update strategies

### Phase 3

- `POST /api/purchase-orders/{id}/orn/upload` — upload ORN, parse, compare against PO
- `POST /api/purchase-orders/{id}/invoice/upload` — upload invoice, parse, compare
- `GET /api/document-comparisons/{id}` — get comparison results
- `PATCH /api/document-comparisons/{id}/resolve` — accept or reject discrepancies

---

## Technical Details

### LlamaIndex Configuration

- **Package:** `llama-cloud` (Python SDK)
- **Tier:** `agentic` (best accuracy for complex documents)
- **Environment variable:** `LLAMAINDEX_API_KEY`
- **Output format:** HTML tables in markdown (`output_tables_as_markdown: False`)
- **Expand:** `["markdown_full"]`
- **Raw output stored** in `raw_markdown` columns for audit and re-processing

### Document Parsing Architecture

```
upload_and_parse(file, supplier_id)
    |
    +-- llamaindex_parse(file) -> raw_markdown
    |
    +-- extract_line_items(raw_markdown, column_mapping) -> [{supplier_product_code, ...}]
    |
    +-- match_to_skus(line_items) -> [{item_code, match_status, ...}]
    |
    +-- return preview for user confirmation
```

The extraction layer uses BeautifulSoup to parse HTML tables from the LlamaIndex output. The column mapping (from `supplier_import_configs`) tells it which `<td>` index corresponds to which field.

### Exchange Rate Buffer

```
effective_rate = base_exchange_rate * (1 + buffer_pct / 100)
total_inr = total_fcy * effective_rate
```

Both `exchange_rate` (base) and `exchange_rate_buffer_pct` stored on the PO for transparency.

### Price Superseding Logic

On new price list import for supplier X:
1. `UPDATE supplier_prices SET is_current = FALSE WHERE price_list_id IN (SELECT id FROM supplier_price_lists WHERE supplier_id = X AND status = 'active')`
2. `UPDATE supplier_price_lists SET status = 'superseded' WHERE supplier_id = X AND status = 'active'`
3. Insert new `supplier_price_lists` row with `status = 'active'`
4. Insert new `supplier_prices` rows with `is_current = TRUE`

### PO Number Generation

Auto-generated format: `PO-{SUPPLIER_CODE}-{YYYYMM}-{SEQ}`
Example: `PO-WN-202604-001` (first Winsor & Newton PO in April 2026)
User can override with custom PO number.

---

## Implementation Phases

### Phase 1: Price Lists + Budget PO Builder
**Delivers:** Team can import price lists, build POs with cost visibility, set budget targets.

1. Database migration: new tables (supplier_price_lists, supplier_import_configs, supplier_prices, purchase_orders, po_lines)
2. LlamaIndex integration: upload, parse, extract
3. SKU matching engine
4. Import preview + confirmation UI
5. Price list management page (list imports, view details)
6. Enhanced PO builder: price columns, running total, budget bar
7. Budget target with floor/ceiling/guide modes
8. "Fill to target" assist
9. PO persistence (save/load drafts, mark as sent)
10. Exchange rate + buffer % input
11. MOQ/case size enforcement (warnings)
12. Supplier import config UI (column mapping)

### Phase 2: Landed Cost + MRP
**Delivers:** Per-item landed cost in INR, suggested MRP, pricing strategy management.

1. Database migration: import_costs, pricing_strategies, po_lines additions
2. Import cost input UI (per PO)
3. Landed cost calculation engine
4. Pricing strategy CRUD
5. MRP derivation engine
6. MRP adjustment UI
7. Update stock_items.mrp from calculated values

### Phase 3: Document Verification
**Delivers:** Automated ORN and invoice comparison against POs, discrepancy tracking.

1. Database migration: order_receipt_notes, orn_lines, invoices, invoice_lines, document_comparisons
2. ORN upload + parse (reuses LlamaIndex pipeline)
3. PO comparison engine (field-by-field diff)
4. Comparison results UI
5. Invoice upload + parse
6. Invoice vs PO/ORN comparison
7. Discrepancy resolution workflow (accept/reject per item)
8. Cascading updates on acceptance (re-calculate landed cost if price changed)

---

## Out of Scope

- **Automated exchange rate fetching** — user enters rate manually (could add API integration later)
- **Supplier portal / e-procurement** — POs exported as Excel/PDF, not sent electronically
- **GRN (Goods Received Notes) tracking** — partial receipt tracking deferred beyond Phase 3
- **Multi-currency single PO** — each PO is single-currency. If a supplier has both USD and EUR items, split into two POs.
- **Approval workflows** — no multi-user approval chain for POs
- **Price list negotiation tools** — the negotiation happens offline; system captures the agreed result
