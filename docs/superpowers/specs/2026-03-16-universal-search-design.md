# Universal Search — Design Spec

**Date:** 2026-03-16
**Status:** Approved

## Overview

Replace all existing distributed search inputs across the dashboard with a single `<UniversalSearch />` component. One search bar, same behavior everywhere — type a brand name, SKU name, or part number and jump directly to it.

## Backend

### New endpoint: `GET /api/search?q=...`

Single unified search endpoint returning grouped results.

**Parameters:**
- `q` (required, min 2 chars) — search query string
- `scope` (optional) — brand name to scope SKU results (used when searching from a brand's SKU page)

**Response:**
```json
{
  "brands": [
    { "category_name": "WINSOR & NEWTON", "total_skus": 1243, "critical_skus": 42 }
  ],
  "skus": [
    { "stock_item_name": "Winsor Blue 37ml", "part_no": "WN-0114", "category_name": "WINSOR & NEWTON", "reorder_status": "critical", "current_stock": 5 }
  ],
  "scoped_skus": [
    { "stock_item_name": "Cotman Brush Round 4", "part_no": "WN-5301", "category_name": "WINSOR & NEWTON", "reorder_status": "ok", "current_stock": 30 }
  ],
  "brand_count": 3,
  "sku_count": 47,
  "scoped_sku_count": 12
}
```

**Result limits:**
- Top 5 brands
- Top 10 scoped SKUs (only when `scope` param provided)
- Top 10 global SKUs (reduced to 5 when scoped results are present)

**Ranking:** exact match > starts-with > contains

**Search fields:**
- Brands: `category_name`
- SKUs: `stock_item_name`, `part_no`

**SQL approach:**
- ILIKE with escaped special characters (existing `_escape_ilike` pattern)
- `ORDER BY` clause implements ranking: `CASE WHEN LOWER(field) = LOWER(q) THEN 0 WHEN LOWER(field) LIKE LOWER(q) || '%' THEN 1 ELSE 2 END`
- Two queries (brands + SKUs) run in same DB connection, merged in Python

## Frontend

### `<UniversalSearch />` component

A single reusable React component replacing every existing search input.

**Props:**
- `scope?: string` — optional brand name for scoped searching (passed on SKU pages)
- `placeholder?: string` — customizable placeholder text

**Behavior:**
- Debounced input (300ms, existing pattern)
- Minimum 2 characters to trigger API call
- React Query for caching search results
- Click outside closes dropdown (existing pattern)

**Dropdown sections (grouped with headers):**

1. **"Brands"** — up to 5 results
   - Each row: brand name + total SKU count + critical SKU count badge
2. **"SKUs in {Brand}"** — up to 10 results (only when `scope` is set)
   - Each row: SKU name, part number (if exists), status badge
3. **"All SKUs"** — up to 10 results (5 when scoped results shown)
   - Each row: SKU name, part number (if exists), brand name, status badge

**Keyboard navigation:**
- Arrow up/down to navigate results
- Enter to select highlighted result
- Escape to close dropdown and clear

**Navigation on select:**
- Brand result → `/brands/{categoryName}/skus`
- SKU result → `/brands/{categoryName}/skus?search={exact_sku_name}` (pre-fills search to show that SKU)

### Pages affected

| Page | Route | Current | Change |
|------|-------|---------|--------|
| Home | `/` | Brand-only search dropdown | Replace with `<UniversalSearch />` |
| Brand Overview | `/brands` | Brand filter input | Replace with `<UniversalSearch />` |
| SKU Detail | `/brands/:name/skus` | Item name/part# filter | Replace with `<UniversalSearch scope={brand} />` |
| Critical SKUs | `/critical` | Search input | Replace with `<UniversalSearch />` |
| Dead Stock | `/brands/:name/dead-stock` | Search input | Replace with `<UniversalSearch scope={brand} />` |

**Not affected:**
- Parties page — searches parties, different domain
- Suppliers page — searches suppliers, different domain

## Performance

- Single DB round trip per keystroke (after debounce)
- PostgreSQL ILIKE with LIMIT keeps query fast at 22K SKUs
- Existing indexes on `category_name`, `stock_item_name`, `part_no` leveraged
- React Query caching means repeated/similar searches are instant
- 300ms debounce prevents excessive API calls

## Out of scope

- Ctrl+K command palette overlay (could be added later)
- Searching parties or suppliers from universal search
- Fuzzy/typo-tolerant search (ILIKE substring matching is sufficient for V1)
