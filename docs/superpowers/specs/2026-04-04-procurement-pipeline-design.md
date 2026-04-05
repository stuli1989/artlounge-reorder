# Procurement Pipeline: Price Lists, Budget-Aware PO Builder, Landed Cost & Document Verification

**Date:** 2026-04-04
**Status:** Approved for implementation
**Phases:** 3 (each delivers standalone value)

---

## Problem

The team builds purchase orders without cost visibility. They don't know the running total of a PO, can't set budget targets, and manually compare supplier documents (ORN, invoices) line-by-line against what was ordered. Supplier price lists come as messy PDFs and Excels with varying formats, and there's no system to store or track pricing over time. MRP calculation happens in Excel after goods arrive.

## Solution

A phased procurement pipeline that covers the full lifecycle: price list import, budget-aware PO building, landed cost calculation, MRP derivation, and automated document verification.

## End-to-End Process Flow

This is the real-world procurement process the system supports, from onboarding a new supplier through to final invoice verification:

```
1. PRICE NEGOTIATION (offline)
   Meet supplier, receive first price list
   Negotiate discounts (brand-wide or SKU-level)
   May differ by origin (China factory = USD, Europe factory = EUR)
   Arrive at agreed pricing

2. PRICE LIST UPLOAD [Phase 1]
   Upload agreed price list (PDF/Excel) into system
   AI parses document (LlamaIndex) -> structured line items
   Match to SKUs -> user reviews and confirms
   Prices saved with full discount structure (list price, discount %, net price)

3. BUILD PO [Phase 1]
   Select brand -> see suggested quantities WITH prices
   Running total in supplier currency + INR (with exchange rate buffer %)
   Set budget target (floor/ceiling/guide)
   "Fill to target" assist for reaching minimums
   MOQ and case size enforcement
   Save PO -> status: [Draft]

4. SEND PO [Phase 1]
   Export to Excel / mark as sent
   Prices and quantities locked -> status: [Sent]

5. ORN VERIFICATION [Phase 3]
   Supplier sends Order Receipt Note confirming the order
   Upload ORN -> compare against PO
   Compare ALL fields: qty, list_price, discount_pct, net_price, line_total
   If exact match -> skip upload, confirm directly
   If mismatch -> find outliers:
     - Sense check: do we need to change our costing?
     - If no: write to supplier, they fix and resend
     - If yes: accept change, update PO costing
   -> status: [ORN Confirmed]

6. IMPORT COSTING [Phase 2]
   Import costs sealed: freight, duty, clearance, etc.
   Enter costs into system
   System calculates per-item landed cost in INR
   -> status: [Costed]

7. MRP CALCULATION [Phase 2]
   Landed cost + margin strategy -> suggested MRP per item
   Adjust per item: mass market (lower margin), retail-only (higher margin), etc.
   These strategies are set once per SKU/category, rarely changed
   Save final MRPs

8. INVOICE VERIFICATION [Phase 3]
   Supplier ships (possibly partial: 80 of 100 items)
   Upload invoice -> compare against PO/ORN
   Qty differences expected (partial shipment) -> informational
   Price/discount differences NOT expected -> flag as outliers
   Resolve discrepancies (accept updates costing, reject disputes with supplier)
   -> status: [Complete]
```

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

The full lifecycle of a PO from creation through to completion. ORN verification, import costing, MRP calculation, and invoice verification are all stages within the PO journey — not separate workflows.

```
[Draft] -- user builds PO, saves multiple times
   |
[Sent] -- user marks sent (records sent_at, locks prices/quantities)
   |
[ORN Received] -- supplier sends Order Receipt Note confirming the order
   |              upload ORN -> compare against PO (qty, price, discount)
   |              if exact match: skip upload, advance directly
   |              if mismatch: find outliers -> sense check costing
   |                -> either accept (update costing) or reject (supplier fixes)
   |
[ORN Confirmed] -- ORN matches PO (or discrepancies resolved)
   |                import costs now get sealed (freight, duty, clearance)
   |
[Costed] -- import costs entered -> per-item landed cost calculated
   |         MRP derived from landed cost + margin strategy
   |         MRP adjusted per item (mass market, retail-only, etc.)
   |
[Invoiced] -- supplier ships (possibly partial: 80 of 100 items)
   |           upload invoice -> compare against PO (qty, price, discount)
   |           qty differences expected (partial shipment)
   |           price/discount differences are NOT expected -> flag as outliers
   |           if match: advance
   |           if mismatch: resolve per item (accept or reject)
   |
[Complete] -- invoice verified, all costs finalized
   |
[Cancelled] -- PO cancelled (escape from any stage)
```

**Stage rules:**
- **Draft** — fully editable (lines, quantities, budget, notes)
- **Sent** — locked. Prices, quantities, and discount structure frozen as a record of what was ordered. This is the baseline for all subsequent comparisons.
- **ORN Received through Complete** — PO itself is locked; only costing data, MRP, and comparison resolutions are editable
- Excel export works from any stage, pulling from saved PO data

**Comparison fields (ORN and Invoice):**
All three of these are compared because any can cause downstream costing issues:
- **qty** — ordered vs confirmed/shipped quantity
- **discount_pct** — agreed discount vs supplier's stated discount
- **net_price** — agreed net price vs actual (catches rounding, discount, or list price changes)
- **list_price** — catalog price may have changed since PO was created
- **line_total** — cross-check: net_price * qty should equal stated total

---

## Phase 2: Landed Cost + MRP Calculation

These steps happen within the PO lifecycle, after ORN is confirmed and import costs are sealed. The PO advances from [ORN Confirmed] to [Costed].

### 2.1 Import Cost Input

After ORN is confirmed and import costs are sealed (freight, duty, clearance), user enters them per PO:

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

ORN and Invoice verification are stages within the PO lifecycle (see lifecycle diagram above). This phase builds the upload, parsing, comparison, and resolution UI for those stages.

### 3.1 ORN (Order Receipt Note) Verification

PO advances from [Sent] to [ORN Received] when the supplier sends their confirmation.

**Flow:**
1. User navigates to the PO detail page and clicks "Upload ORN"
2. Upload ORN (PDF/Excel) -> LlamaIndex parses -> extract line items
3. Match ORN line items to the PO's `po_lines` (by item_code, falling back to EAN/name)
4. Compare **all five fields** per item against the locked PO values:
   - **qty** — ordered 120, ORN says 100? Flag.
   - **list_price** — agreed EUR 4.19, ORN says EUR 4.50? Flag.
   - **discount_pct** — agreed 79%, ORN says 75%? Flag. This matters because even if net_price looks close, the wrong discount structure will cause issues on future orders.
   - **net_price** — agreed EUR 0.90, ORN says EUR 0.95? Flag.
   - **line_total** — cross-check: net_price * qty should match stated total
5. Also flag:
   - **Missing items** — in PO but not in ORN
   - **Extra items** — in ORN but not in PO
6. Generate comparison report with per-item status

**If ORN matches PO exactly:** user can skip upload entirely and advance the PO directly to [ORN Confirmed]. The system should offer this as a one-click option ("ORN matches, confirm?").

**Discrepancy resolution for ORN:**
- All outliers shown on one screen
- Per-item decision:
  - **Accept** — update our costing to match supplier's values (e.g., discount was negotiated down from 79% to 75%)
  - **Reject** — write back to supplier to correct. PO stays in [ORN Received] until resolved.
- Accepting a price/discount change on the ORN updates the `po_lines` snapshot values and recalculates line totals
- Once all discrepancies are resolved -> PO advances to [ORN Confirmed]

### 3.2 Invoice Verification

PO advances from [Costed] to [Invoiced] when the supplier ships goods and sends an invoice.

**Key difference from ORN:** Invoices often cover partial shipments. The supplier confirmed 100 items in the ORN but may ship only 80. So:
- **Qty differences are expected** — 80 shipped vs 100 ordered is normal, not an error
- **Price/discount differences are NOT expected** — these should match the ORN-confirmed values
- Flags if invoice total != sum of line items (arithmetic error in supplier's invoice)

**Flow:**
1. User clicks "Upload Invoice" on the PO detail page
2. Upload invoice (PDF/Excel) -> LlamaIndex parses -> extract line items
3. Match invoice line items to PO's `po_lines`
4. Compare against PO (using the ORN-confirmed values if ORN was uploaded):
   - **qty** — informational only (partial shipment). Record actual shipped qty.
   - **list_price** — should match. Flag if different.
   - **discount_pct** — should match. Flag if different.
   - **net_price** — should match. Flag if different.
   - **line_total** — cross-check against invoice's stated total
5. Also flag missing/extra items

**Discrepancy resolution for Invoice:**
- Same UI as ORN resolution
- Per-item: Accept (update costing, cascade to landed cost recalculation and MRP update) or Reject (dispute with supplier)
- Once resolved -> PO advances to [Complete]

### 3.3 Cascading Updates on Acceptance

When a price or discount discrepancy is accepted (at either ORN or Invoice stage):
1. `po_lines` values updated (list_price, discount_pct, net_price, line_total)
2. `purchase_orders.total_value` and `total_value_inr` recalculated
3. If PO is already in [Costed] stage: `landed_cost_inr` recalculated per affected item
4. If MRP was already derived: `suggested_mrp` recalculated, user prompted to review `final_mrp`

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
| status | TEXT | NOT NULL DEFAULT 'draft' | 'draft','sent','orn_received','orn_confirmed','costed','invoiced','complete','cancelled' |
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
| field_name | TEXT | NOT NULL | 'qty', 'list_price', 'discount_pct', 'net_price', 'line_total' |
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

### Phase 1: Price Lists + PO Builder

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
- `GET /api/purchase-orders/{id}` — get PO with lines + current lifecycle stage
- `PUT /api/purchase-orders/{id}` — update draft PO (lines, budget, notes)
- `PATCH /api/purchase-orders/{id}/status` — advance lifecycle (draft->sent, orn_confirmed->costed, etc.)
- `POST /api/purchase-orders/{id}/fill-to-target` — get fill suggestions
- `POST /api/purchase-orders/{id}/export` — generate Excel

**Budget Calculation:**
- `GET /api/brands/{category_name}/po-data` — existing endpoint, enhanced with price data from supplier_prices
- Price fields added to PoDataItem response: net_price, list_price, discount_pct, moq, case_size, has_price

### Phase 2: Landed Cost + MRP

- `POST /api/purchase-orders/{id}/import-costs` — enter import costs (PO must be in orn_confirmed stage)
- `GET /api/purchase-orders/{id}/landed-costs` — calculate and return per-item landed costs
- `GET /api/purchase-orders/{id}/mrp-suggestions` — calculate MRPs from landed cost + strategy
- `PUT /api/purchase-orders/{id}/mrp` — save final MRPs, advance PO to costed
- `GET /api/pricing-strategies` — list strategies
- `PUT /api/pricing-strategies` — create/update strategies

### Phase 3: Document Verification (ORN + Invoice)

**ORN (advances PO from sent -> orn_received -> orn_confirmed):**
- `POST /api/purchase-orders/{id}/orn/upload` — upload ORN, parse, compare against PO (qty, list_price, discount_pct, net_price, line_total)
- `POST /api/purchase-orders/{id}/orn/skip` — skip ORN upload if exact match ("ORN matches, confirm directly")
- `GET /api/purchase-orders/{id}/orn/comparison` — get ORN vs PO comparison results
- `PATCH /api/purchase-orders/{id}/orn/resolve` — accept or reject discrepancies per item

**Invoice (advances PO from costed -> invoiced -> complete):**
- `POST /api/purchase-orders/{id}/invoice/upload` — upload invoice, parse, compare against PO/ORN (qty informational, price/discount must match)
- `GET /api/purchase-orders/{id}/invoice/comparison` — get invoice vs PO comparison results
- `PATCH /api/purchase-orders/{id}/invoice/resolve` — accept or reject discrepancies per item

**Shared:**
- `GET /api/document-comparisons/{comparison_id}` — get detailed field-by-field comparison
- Accepting price/discount changes cascades: updates po_lines -> recalculates total_value -> recalculates landed_cost if applicable -> flags MRP for review if applicable

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
**Delivers:** Team can import price lists, build POs with cost visibility, set budget targets, and persist POs through the Draft -> Sent stages.

1. Database migration: new tables (supplier_price_lists, supplier_import_configs, supplier_prices, purchase_orders, po_lines)
2. LlamaIndex integration: upload, parse, extract
3. SKU matching engine
4. Import preview + confirmation UI
5. Price list management page (list imports, view details)
6. Enhanced PO builder: price columns, running total, budget bar
7. Budget target with floor/ceiling/guide modes
8. "Fill to target" assist
9. PO persistence with lifecycle (save/load drafts, mark as sent, status tracking)
10. PO detail page showing current lifecycle stage + available actions
11. Exchange rate + buffer % input
12. MOQ/case size enforcement (warnings)
13. Supplier import config UI (column mapping)

### Phase 2: Landed Cost + MRP
**Delivers:** Per-item landed cost in INR, suggested MRP, pricing strategy management. Covers the [ORN Confirmed] -> [Costed] lifecycle transition.

1. Database migration: import_costs, pricing_strategies, po_lines additions
2. Import cost input UI on PO detail page (available after ORN confirmed)
3. Landed cost calculation engine
4. Pricing strategy CRUD
5. MRP derivation engine
6. MRP adjustment UI
7. Update stock_items.mrp from calculated values
8. PO advances to [Costed] when MRP is finalized

### Phase 3: Document Verification (ORN + Invoice)
**Delivers:** Automated ORN and invoice comparison against POs, discrepancy tracking. Covers the [Sent] -> [ORN Received] -> [ORN Confirmed] and [Costed] -> [Invoiced] -> [Complete] lifecycle transitions.

1. Database migration: order_receipt_notes, orn_lines, invoices, invoice_lines, document_comparisons
2. ORN upload + parse on PO detail page (reuses LlamaIndex pipeline)
3. Comparison engine: field-by-field diff on all five fields (qty, list_price, discount_pct, net_price, line_total) plus missing/extra items
4. ORN comparison results UI with per-item accept/reject
5. "ORN matches — confirm directly" skip option
6. Invoice upload + parse on PO detail page
7. Invoice comparison: qty differences informational (partial shipment), price/discount differences flagged as outliers
8. Invoice comparison results UI with per-item accept/reject
9. Cascading updates on acceptance: po_lines -> total_value -> landed_cost_inr -> suggested_mrp recalculation
10. PO lifecycle advances: sent -> orn_received -> orn_confirmed (after Phase 3 ORN steps), costed -> invoiced -> complete (after Phase 3 invoice steps)

**Note on phase ordering:** Phase 3 covers two separate lifecycle stages (ORN after sending, Invoice after costing). In practice, ORN verification may be needed before Phase 2 (landed cost) can proceed, since import costs are entered after ORN confirmation. Teams can deploy Phase 3's ORN portion alongside Phase 2, or use the "skip ORN" flow to advance POs directly to [ORN Confirmed] until Phase 3 is built.

---

## Out of Scope

- **Automated exchange rate fetching** — user enters rate manually (could add API integration later)
- **Supplier portal / e-procurement** — POs exported as Excel/PDF, not sent electronically
- **GRN (Goods Received Notes) tracking** — partial receipt tracking deferred beyond Phase 3
- **Multi-currency single PO** — each PO is single-currency. If a supplier has both USD and EUR items, split into two POs.
- **Approval workflows** — no multi-user approval chain for POs
- **Price list negotiation tools** — the negotiation happens offline; system captures the agreed result
