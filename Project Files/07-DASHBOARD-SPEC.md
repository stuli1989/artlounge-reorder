# 07 — Dashboard Specification

## Overview

A browser-based dashboard with three views. Built with React + Tailwind CSS frontend, FastAPI backend serving data from PostgreSQL. No login required initially (secured at network level — only accessible from your IP or VPN).

## Global Elements

### Header Bar
- Logo / App name: "Art Lounge — Stock Intelligence"
- Last sync timestamp: "Data as of: Mar 11, 2026 2:00 AM"
- Freshness indicator: Green dot if < 24h, Amber if 24-48h, Red if > 48h
- Warning banner (if applicable): "⚠ 3 new parties need classification" — links to classification page

### Navigation
- Three tabs: **Brands** | **SKU Detail** | **PO Builder**
- SKU Detail and PO Builder require a brand selection (either from clicking a brand row, or from a dropdown)

## View 1: Brand Overview

### Purpose
At a glance, see which brands need attention. Sorted by urgency.

### Data Source
`brand_metrics` table

### Layout
Full-width table, one row per brand (stock category).

### Columns

| Column | Data | Format |
|--------|------|--------|
| Brand | category_name | Text, clickable → opens SKU Detail |
| Total SKUs | total_skus | Integer |
| In Stock | in_stock_skus | Integer, green text |
| Out of Stock | out_of_stock_skus | Integer, red text if > 0 |
| Critical | critical_skus | Integer, red background if > 0 |
| Warning | warning_skus | Integer, amber background if > 0 |
| OK | ok_skus | Integer |
| Avg Days to Stockout | avg_days_to_stockout | "42 days" or "N/A". Color-coded: Red < 30, Amber 30-90, Green > 90 |
| Lead Time | supplier_lead_time | "180 days" |
| Action | — | Button: "View SKUs" → navigates to View 2, "Build PO" → navigates to View 3 |

### Sorting
Default sort: by `critical_skus` descending, then `warning_skus` descending. User can click any column header to re-sort.

### Filters
- Search box: filter brands by name
- Status filter: "Show only brands with critical/warning items" toggle

### Summary Bar (above table)
Four stat cards:
- Total Brands: 23
- Brands with Critical Items: 5 (red)
- Brands with Warning Items: 8 (amber)
- Total SKUs Out of Stock: 312 (red)

## View 2: SKU Detail

### Purpose
For a selected brand, see every SKU sorted by urgency. This is where you decide what to order.

### Data Source
`sku_metrics` table filtered by `category_name`

### Layout

**Brand header:** "Speedball — 847 SKUs" with supplier info: "Supplier: Speedball Art Products LLC | Default Lead Time: 180 days (sea) / 30 days (air)"

**Summary cards:**
- Critical: 12 SKUs (red)
- Warning: 45 SKUs (amber)
- OK: 650 SKUs (green)
- Out of Stock: 40 SKUs
- No Data: 100 SKUs (grey)

**Table:** One row per SKU

### Columns

| Column | Data | Format |
|--------|------|--------|
| Status | reorder_status | Colored dot/badge: 🔴 Critical, 🟡 Warning, 🟢 OK, ⚫ Out of Stock, ⚪ No Data |
| SKU Name | stock_item_name | Text, truncated with tooltip for long names |
| Current Stock | current_stock | Integer with unit. "18 pcs". Red if 0 or negative. |
| Wholesale Velocity | wholesale_velocity × 30 | "48.0 /month" |
| Online Velocity | online_velocity × 30 | "6.1 /month" |
| Total Velocity | total_velocity × 30 | "54.1 /month" |
| Days to Stockout | days_to_stockout | "7 days" — color-coded. "OUT" if 0. |
| Last Import | last_import_date | "Nov 26, 2025" |
| Last Import Qty | last_import_qty | "250" |
| Suggested Order | reorder_qty_suggested | "426" — only shown for critical/warning items |

### Sorting
Default: by `days_to_stockout` ascending (most urgent first). NULL values (no_data) at bottom.

### Filters
- Status filter: Show All / Critical Only / Warning & Critical / Out of Stock
- Search: filter by SKU name
- Min velocity filter: "Only show items with velocity > X" (to hide dead stock with no movement)

### Row Click
Clicking a row expands to show:
- Mini timeline chart of stock level over time (from daily_stock_positions)
- Transaction history (last 20 transactions)
- Import history (all imports with dates and quantities)

## View 3: PO Builder

### Purpose
Generate a purchase order for a selected brand/supplier. Pre-filled with all items that need reordering.

### Data Source
`sku_metrics` filtered by category + reorder_status IN ('critical', 'warning', 'out_of_stock')

### Layout

**Header:** "Purchase Order — Speedball Art Products LLC"

**Settings bar:**
- Lead time assumption: dropdown [Sea Freight (180 days) / Air Freight (30 days) / Custom: ___ days]
- Safety buffer: slider [1.0x / 1.2x / 1.3x / 1.5x / 2.0x] — default 1.3x
- Include "warning" items: toggle (default: yes)
- Include "OK" items below threshold: toggle (default: no)

Changing these settings recalculates suggested quantities in real-time.

**Table:** One row per SKU that needs ordering

### Columns

| Column | Data | Editable? |
|--------|------|-----------|
| Include | Checkbox | Yes — uncheck to exclude from PO |
| SKU Name | stock_item_name | No |
| Current Stock | current_stock | No |
| Velocity (/month) | total_velocity × 30 | No |
| Days to Stockout | days_to_stockout | No |
| Suggested Qty | computed from velocity × lead time × buffer | No (changes with settings) |
| Order Qty | Defaults to suggested_qty | **Yes — user edits this** |
| Notes | Empty | Yes — free text |

### Footer
- Total Items: 47
- Total Order Quantity: 2,340 units
- **Export as Excel** button → downloads .xlsx file
- **Export as PDF** button → downloads formatted PO as PDF

### Excel Export Format

The exported Excel should be formatted as a purchase order ready to email:

```
Row 1:  Art Lounge India — Purchase Order
Row 2:  To: Speedball Art Products LLC
Row 3:  Date: March 11, 2026
Row 4:  (blank)
Row 5:  Headers: Item Name | SKU/Code | Quantity | Unit | Notes
Row 6+: Data rows
Last:   Total Quantity: 2,340
```

## API Endpoints

### FastAPI Backend Routes

```
GET  /api/brands
     Returns: List of brand_metrics, sorted by urgency
     Query params: ?search=speedball

GET  /api/brands/{category_name}/skus
     Returns: List of sku_metrics for this brand
     Query params: ?status=critical,warning &min_velocity=0.1 &sort=days_to_stockout

GET  /api/brands/{category_name}/skus/{stock_item_name}
     Returns: Full detail for one SKU including daily positions and transaction history

GET  /api/brands/{category_name}/skus/{stock_item_name}/positions
     Returns: Daily stock position data for charting
     Query params: ?from=2025-04-01 &to=2026-03-11

GET  /api/brands/{category_name}/skus/{stock_item_name}/transactions
     Returns: Transaction history
     Query params: ?limit=50

GET  /api/brands/{category_name}/po-data
     Returns: PO builder data — all SKUs needing reorder with suggested quantities
     Query params: ?lead_time=180 &buffer=1.3 &include_warning=true

POST /api/export/po
     Body: { category_name, lead_time, buffer, items: [{stock_item_name, order_qty, notes}] }
     Returns: Excel file download

GET  /api/parties/unclassified
     Returns: List of unclassified parties needing review

POST /api/parties/classify
     Body: { tally_name, channel }
     Classifies a party

GET  /api/sync/status
     Returns: Last sync info, freshness status, any warnings
```

## Tech Notes

- Use React Query (TanStack Query) for data fetching with caching
- Use Recharts for the stock level timeline charts
- Use react-table or TanStack Table for sortable/filterable tables
- Excel generation happens server-side (Python openpyxl)
- Dashboard should be responsive but optimized for desktop (this is a work tool, not mobile)
