# 08 — API & Frontend Adjustments

## Overview

~95% of the API and frontend carries over unchanged. Changes are limited to column renames, new fields, and label updates.

## API Route Changes

### Unchanged (no modifications needed)
- `routes/brands.py` — reads from `brand_metrics` (generic)
- `routes/skus.py` — reads from `sku_metrics` (generic)
- `routes/suppliers.py` — CRUD on `suppliers` table
- `routes/overrides.py` — CRUD on `overrides` table
- `routes/po.py` — Excel export from `sku_metrics`
- `routes/search.py` — full-text search on `stock_items`
- `routes/users.py` — user management
- `routes/auth_routes.py` — JWT auth

### Minor Changes

**`routes/parties.py`:**
- SQL references `tally_name` → `name`, `tally_parent` → `party_group`
- Response field `tally_name` → `name`
- Note: party classification becomes simpler (UC channels are pre-mapped), but keep the UI for manual overrides

**`routes/settings.py`:**
- Remove `backdate_physical_stock` and `physical_stock_grace_days` setting keys
- Add display for `open_purchase` visibility toggle

**`routes/sync_status.py`:**
- Update status labels: source = "unicommerce" instead of "tally"
- Add UC-specific stats (dispatches, returns, GRNs pulled)

### New Fields in Existing Responses

**SKU detail endpoint** — add to response:
- `open_purchase` — pending PO quantity (reference display)
- `bad_inventory` — damaged stock count
- `zero_activity_ratio` — ratio of idle days
- `min_sample_met` — whether velocity has sufficient data (14+ in-stock days)
- `return_type_breakdown` — {CIR: count, RTO: count} if returns exist
- `uc_channel` — raw UC channel code

**Brand metrics endpoint** — add:
- `min_days_to_stockout` — earliest stockout in brand

### New Status Values

The `reorder_status` field now has these values:
- `stocked_out` (NEW — actively selling, already out)
- `out_of_stock` (was `out_of_stock`)
- `no_demand` (was `no_data`)
- `critical`
- `warning`
- `ok`

Update the `valid_reorder_status` CHECK constraint in the schema.

## Frontend Changes

### Label/Copy Changes

| Location | Old | New |
|---|---|---|
| Party Classification page | "Tally Name" column | "Name" |
| Party Classification page | "Tally Parent" column | "Group" |
| Sync Status | "Tally sync" | "Unicommerce sync" |
| Sync Stats | "categories_synced, items_synced, transactions_synced" | "skus_updated, dispatches, returns, grns" |
| Reorder Status badge | "No Data" | "No Demand" |
| Reorder Status badge | (new) | "Stocked Out" (red, distinct from "Out of Stock") |

### New UI Elements

**SKU Detail page:**
- Show `open_purchase` as an info badge: "12 units on PO" (not factored into reorder)
- Show `bad_inventory` if > 0: "3 units damaged"
- Show "Insufficient velocity data" warning if `min_sample_met = false`
- Show `do_not_reorder` with calculated status: "OK (reorder suppressed)"

**Brand Overview page:**
- Add `min_days_to_stockout` column (or tooltip)

### No Changes Needed

- Brand Overview grid layout
- SKU detail stock timeline chart
- PO Builder export
- Supplier Management CRUD
- Settings page (minus removed Tally settings)
- ABC/XYZ badges
- Trend indicator arrows
- All filtering, sorting, pagination
