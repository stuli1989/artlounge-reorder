# Universal Search — Design Spec

**Date:** 2026-03-16
**Status:** Approved

## Overview

Replace all existing distributed search inputs across the dashboard with a single `<UniversalSearch />` component. One search bar, same behavior everywhere — type a brand name, SKU name, or part number and jump directly to it.

## Backend

### New endpoint: `GET /api/search?q=...`

Single unified search endpoint returning grouped results. Requires authentication (`Depends(get_current_user)`), consistent with all other API routes.

**Parameters:**
- `q` (required, min 2 chars, max 100 chars, whitespace-trimmed) — search query string. Returns 400 if missing, too short after trim, or too long.
- `scope` (optional) — brand name to scope SKU results (used when searching from a brand's SKU page). If the scope doesn't match any brand, `scoped_skus` is simply empty (no error).

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

- `brand_count`, `sku_count`, `scoped_sku_count` = total matches before LIMIT (requires `COUNT(*) OVER()` window function). Useful for showing "47 more results..." hints.
- `scoped_skus` and `scoped_sku_count` are only present when `scope` is provided.

**Result limits:**
- Top 5 brands
- Top 10 scoped SKUs (only when `scope` param provided)
- Top 10 global SKUs (reduced to 5 when scoped results are present)

**Ranking:** exact match > starts-with > contains

**Search fields:**
- Brands: `category_name`
- SKUs: `stock_item_name`, `part_no`

**SQL approach:**
- ILIKE with escaped special characters (existing `_escape_ilike` pattern from `skus.py`)
- `ORDER BY` clause implements ranking: `CASE WHEN LOWER(field) = LOWER(q) THEN 0 WHEN LOWER(field) LIKE LOWER(q) || '%' THEN 1 ELSE 2 END`
- Three queries in same DB connection:
  1. Brands query (against `brand_metrics`)
  2. Scoped SKUs query (against `sku_metrics WHERE category_name = scope`) — only when scope provided
  3. Global SKUs query (against `sku_metrics`, excludes scoped brand to avoid duplicates)
- All SKU queries filter `WHERE COALESCE(is_active, TRUE) = TRUE` to exclude inactive items (consistent with existing `list_skus` pattern)
- No special indexes needed — sequential scan on 22K rows with ILIKE + LIMIT completes in <50ms. The existing trigram index on `stock_items.tally_name` is available if performance ever becomes a concern.

### New frontend API function

Add `fetchSearch(q: string, scope?: string)` to `src/dashboard/src/lib/api.ts`, plus `SearchResults` type to `types.ts`.

## Frontend

### `<UniversalSearch />` component

A single reusable React component replacing every existing search input.

**Props:**
- `scope?: string` — optional brand name for scoped searching (passed on SKU pages)
- `placeholder?: string` — customizable placeholder text

**Behavior:**
- Debounced input (300ms, existing pattern)
- Minimum 2 characters to trigger API call
- React Query for caching search results (stale responses handled automatically)
- Click outside closes dropdown (existing pattern)

**Dropdown sections (grouped with headers):**

1. **"Brands"** — up to 5 results
   - Each row: brand name + total SKU count + critical SKU count badge
2. **"SKUs in {Brand}"** — up to 10 results (only when `scope` is set)
   - Each row: SKU name, part number (if exists), status badge
3. **"All SKUs"** — up to 10 results (5 when scoped results shown)
   - Each row: SKU name, part number (if exists), brand name, status badge

**States:**
- **Loading:** Small spinner inside dropdown while API request is in flight
- **No results:** "No brands or SKUs match '{query}'" message
- **Error:** "Search failed — try again" message (no retry loop)
- **Empty input:** Dropdown hidden

**Keyboard navigation:**
- Arrow up/down to navigate results (input retains focus, dropdown is a listbox)
- Enter to select highlighted result
- Escape to close dropdown and clear

**Navigation on select:**
- Brand result → `/brands/{categoryName}/skus`
- SKU result → `/brands/{categoryName}/skus?highlight={exact_sku_name}` — navigates to the brand's SKU page and highlights/scrolls to that specific SKU row. The `highlight` param triggers an exact-match lookup + scroll, separate from the search filter.

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

### SKU highlight behavior

When navigating to a SKU page via `?highlight={sku_name}`:
- The SKU detail page reads the `highlight` param from the URL
- Fetches the first page of SKUs with `search={sku_name}` (exact name search narrows to 1 result)
- Scrolls to and briefly highlights the matching row (e.g., a subtle background flash)
- Clears the highlight param from the URL after scrolling (clean URL)

## Performance

- Single DB round trip per keystroke (after debounce)
- PostgreSQL ILIKE with LIMIT on 22K rows completes in <50ms (sequential scan is fine at this scale)
- React Query caching means repeated/similar searches are instant
- 300ms debounce prevents excessive API calls

## Out of scope

- Ctrl+K command palette overlay (could be added later)
- Searching parties or suppliers from universal search
- Fuzzy/typo-tolerant search (ILIKE substring matching is sufficient for V1)
