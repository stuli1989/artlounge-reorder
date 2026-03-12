# T19: SKU Detail Page

## Prerequisites
- T17 (React scaffolding)
- T15 (SKU API endpoints exist)

## Objective
Build the SKU Detail page — shows every SKU for a selected brand, sorted by urgency, with expandable rows for charts and transaction history.

## Design System
Use shadcn/ui: `Card`, `Table`, `Badge`, `Input`, `Select`, `Collapsible`, `Separator`.
Use `recharts` for stock timeline charts.
Use `@tanstack/react-query` for data fetching.

## Files to Create/Modify

### 1. `dashboard/src/pages/SkuDetail.tsx`

Route: `/brands/:categoryName/skus`
Get `categoryName` from URL params.

#### Layout Structure

**Brand Header:**
```
Speedball — 847 SKUs
Supplier: Speedball Art Products LLC | Default Lead Time: 180 days (sea)
```

**Summary Cards (4 cards):**
- Critical: 12 SKUs (red)
- Warning: 45 SKUs (amber)
- OK: 650 SKUs (green)
- Out of Stock: 40 SKUs (dark red)

Derived from the SKU list client-side (count by status).

**Filters:**
- Status filter: Select dropdown — "All" / "Critical" / "Warning & Critical" / "Out of Stock"
- Search: Input — filter by SKU name
- Min velocity: Input — "Only show items with velocity > X /month"

**Main Table:**

| Column | Format |
|--------|--------|
| Status | StatusBadge component (from T18) |
| SKU Name | Text, truncated with tooltip for long names |
| Current Stock | "18 pcs" — red if 0 or negative |
| Wholesale Vel. | "48.0 /mo" (wholesale_velocity × 30) |
| Online Vel. | "6.1 /mo" (online_velocity × 30) |
| Total Vel. | "54.1 /mo" (total_velocity × 30) |
| Days Left | "7 days" — color-coded. "OUT" if 0. |
| Last Import | "Nov 26, 2025" |
| Import Qty | "250" |
| Suggested Order | "421" — only for critical/warning |

**Default sort:** days_to_stockout ASC, NULLs at bottom.

**Row expansion:** Clicking a row expands to show:
1. Stock timeline chart
2. Transaction history

Data from `GET /api/brands/{categoryName}/skus?status=...&search=...`

### 2. `dashboard/src/components/StockTimelineChart.tsx`

Recharts area/line chart showing stock levels over time.

```tsx
// Data from GET /api/brands/{cat}/skus/{item}/positions
// X-axis: position_date
// Y-axis: closing_qty (area fill)
// Color: green when in_stock, red when out of stock
// Optional: overlay markers for import dates
```

Chart specs:
- Area chart with closing_qty
- Reference line at y=0
- Tooltip showing date, stock level, inward/outward for that day
- Responsive width, fixed ~200px height (fits in expanded row)

### 3. `dashboard/src/components/TransactionHistory.tsx`

Simple table showing recent transactions for the expanded SKU.

```tsx
// Data from GET /api/brands/{cat}/skus/{item}/transactions?limit=20
// Columns: Date | Party | Type | Voucher # | Qty In | Qty Out | Channel
```

Use shadcn `Table` with compact styling. Color-code channel badges.

## Interactions
- Click row → expand/collapse detail panel
- Only one row expanded at a time (accordion behavior)
- "Build PO" button in header → navigates to /brands/{categoryName}/po
- Back button → navigates to /

## Acceptance Criteria
- [ ] Brand name from URL params used to fetch correct SKUs
- [ ] Summary cards count by reorder_status
- [ ] Status/search/velocity filters work
- [ ] Table sortable by clicking column headers
- [ ] Row click expands to show chart + transaction history
- [ ] Stock timeline chart renders from daily positions data
- [ ] Transaction history shows last 20 transactions
- [ ] Velocity displayed as /month (× 30)
- [ ] Loading states for initial load and row expansion
- [ ] "Build PO" button navigates to PO builder
