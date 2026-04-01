# Prefix Search & PO Builder Enhancement

**Date:** 2026-04-01
**Status:** Approved

## Problem

The operations team needs to view and order entire product ranges together. Product ranges share a common part_no prefix (e.g., all Winsor & Newton PWC items start with "0102"). Currently, the only way to find these is to scroll through a brand's SKU list or search for individual items one at a time.

## Solution

Enhance search and the PO builder to support part_no prefix lookup, allowing the team to find, view, and build purchase orders for entire product ranges in one action.

## Design

### 1. Backend: Prefix Search API

**New endpoint:** `GET /api/search/prefix?q={prefix}`

- Minimum 2 characters required
- Returns all SKUs whose `part_no` starts with the given prefix (case-insensitive)
- Response shape:

```json
{
  "prefix": "0102",
  "total": 42,
  "brands": ["Winsor & Newton"],
  "skus": [
    {
      "stock_item_name": "WN PWC Cadmium Yellow 0102010",
      "part_no": "0102010",
      "category_name": "Winsor & Newton",
      "current_stock": 150,
      "reorder_status": "ok"
    }
  ]
}
```

**Enhanced `/api/search`:** When the query matches 2+ SKUs by part_no prefix, include a `prefix_group` section in the response:

```json
{
  "prefix_group": {
    "prefix": "0102",
    "total": 42,
    "brands": ["Winsor & Newton"]
  },
  "brands": [...],
  "skus": [...],
  "scoped_skus": [...]
}
```

`prefix_group` is `null` when fewer than 2 SKUs match by prefix.

**New endpoint:** `POST /api/po-data/prefix`

- Request: `{ "prefix": "0102", "coverage_days": 180, "buffer": 1.3, "from_date": "...", "to_date": "..." }`
- Finds all SKUs matching the prefix
- Uses each SKU's own brand supplier `lead_time_default` (no single lead_time param)
- Returns the same PO data shape as the existing endpoints, plus a `brands` summary array

**New endpoint:** `GET /api/skus?prefix={prefix}`

- Returns paginated SKU list (same shape as `/api/brands/{name}/skus`) filtered by part_no prefix
- Supports all existing query params: status, sort, sort_dir, min_velocity, abc_class, etc.
- Cross-brand: no category_name filter applied

### 2. Universal Search: Prefix Group Result

When the search query matches 2+ SKUs by part_no prefix, a "Prefix Match" group appears at the top of the search dropdown:

```
┌─────────────────────────────────────────────┐
│ Prefix Match                                 │
│   "0102" -> 42 SKUs across 1 brand           │
│   [View SKUs]  [Build PO]                   │
├─────────────────────────────────────────────┤
│ Brands                                       │
│   Winsor & Newton (42 urgent)               │
├─────────────────────────────────────────────┤
│ SKUs                                         │
│   0102010 - WN PWC Cadmium Yellow           │
│   0102045 - WN PWC Alizarin Crimson         │
│   ... +40 more                              │
└─────────────────────────────────────────────┘
```

- **"View SKUs"** navigates to `/skus?prefix=0102`
- **"Build PO"** navigates to `/po?prefix=0102`
- Only shown when 2+ SKUs match by prefix; single matches appear as normal SKU results
- Prefix detection runs alongside normal brand/SKU search (same API call)

### 3. PO Builder: Code Prefix Tab + Cross-Brand Support

**SkuInputDialog — new third tab: "Code Prefix"**

- Input field for part_no prefix + Search button (or Enter to search)
- Shows preview: count, brand breakdown, scrollable SKU list
- "Load into PO Builder" button feeds matched SKUs into the PO flow

**URL entry:** `/po?prefix=0102` auto-opens with the prefix tab pre-filled and auto-searched.

**Cross-brand PO table enhancements:**

- **Brand badge** next to each SKU name (subtle chip, like existing status badges)
- **Summary bar** above the table: "3 brands: Winsor & Newton (30), Daler Rowney (8), Caran d'Ache (4)"
- Brand column visible when PO contains multiple brands

**Lead time handling:** Each SKU uses its own brand's `supplier.lead_time_default`. The global lead time override in PO config still works and applies uniformly when set by the user.

### 4. SKU List: Prefix Filter Page

**Route:** `/skus?prefix=0102`

- Standalone SKU list page (not scoped to a single brand)
- Reuses existing SKU table component with all filters/sorting
- Page header: "SKUs matching prefix '0102'" with brand breakdown
- All existing filters (status, velocity, ABC class, etc.) work on top of the prefix filter
- Backed by `GET /api/skus?prefix=0102` endpoint

## Files to Modify

### Backend
- `src/api/routes/search.py` — add prefix_group to search response, add `/api/search/prefix` endpoint
- `src/api/routes/po.py` — add `POST /api/po-data/prefix` endpoint
- `src/api/routes/skus.py` — add `GET /api/skus` cross-brand endpoint with prefix param

### Frontend
- `src/dashboard/src/components/UniversalSearch.tsx` — render prefix group result with View/Build PO actions
- `src/dashboard/src/components/SkuInputDialog.tsx` — add Code Prefix tab
- `src/dashboard/src/pages/PoBuilder.tsx` — handle `?prefix=` URL param, cross-brand badges/summary bar, per-SKU brand lead times
- `src/dashboard/src/lib/api.ts` — add `fetchPrefixSearch`, `fetchPoDataByPrefix`, `fetchSkusByPrefix` functions
- `src/dashboard/src/lib/types.ts` — add PrefixSearchResult type
- `src/dashboard/src/App.tsx` (or router config) — add `/skus` route
- New page: `src/dashboard/src/pages/SkuListByPrefix.tsx` — cross-brand SKU list page

## Non-Goals

- No brand-level prefix aggregation (e.g., "all brands whose part_nos start with X")
- No saved prefix searches or favorites
- No auto-suggest for known prefixes
- Group-by-brand sorting in PO table deferred (nice-to-have, not V1)
