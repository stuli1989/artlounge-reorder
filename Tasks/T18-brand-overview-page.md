# T18: Brand Overview Page

## Prerequisites
- T17 (React scaffolding with shadcn/ui)
- T15 (Brand API endpoints exist)

## Objective
Build the Brand Overview page — the main landing page showing all brands sorted by urgency.

## Design System
Use shadcn/ui components: `Card`, `Table`, `Badge`, `Input`, `Button`, `Select`.
Use `@tanstack/react-query` for data fetching.

## File to Create/Modify

### `dashboard/src/pages/BrandOverview.tsx`

#### Layout Structure

**Summary Cards (top row — 4 cards using shadcn `Card`):**
- Total Brands: 23
- Brands with Critical Items: 5 (red accent)
- Brands with Warning Items: 8 (amber accent)
- Total SKUs Out of Stock: 312 (red accent)

Data from `GET /api/brands/summary`

**Filters (below cards):**
- Search input (shadcn `Input`) — filter brands by name
- Toggle: "Show only brands with critical/warning items" (shadcn `Checkbox` or `Switch`)

**Main Table (shadcn `Table` or @tanstack/react-table):**

| Column | Format | Notes |
|--------|--------|-------|
| Brand | Text, clickable → /brands/{name}/skus | Bold text |
| Total SKUs | Integer | |
| In Stock | Integer, green text | |
| Out of Stock | Integer, red text if > 0 | |
| Critical | shadcn `Badge` variant="destructive" if > 0 | Red background |
| Warning | `Badge` with amber/yellow styling if > 0 | |
| OK | Integer | |
| Avg Days to Stockout | "42 days" or "N/A" | Color: Red < 30, Amber 30-90, Green > 90 |
| Lead Time | "180 days" | |
| Actions | Two buttons: "View SKUs" and "Build PO" | shadcn `Button` variant="outline" |

**Default sort:** critical_skus DESC, then warning_skus DESC. Column headers clickable to re-sort.

Data from `GET /api/brands?search=...`

#### Interactions
- Click brand name or "View SKUs" → navigate to `/brands/{category_name}/skus`
- Click "Build PO" → navigate to `/brands/{category_name}/po`
- Search input filters in real-time (debounced API call or client-side filter)

### `dashboard/src/components/StatusBadge.tsx`

Reusable status badge component:
```tsx
// Uses shadcn Badge with appropriate variant/color based on status
type Status = 'critical' | 'warning' | 'ok' | 'out_of_stock' | 'no_data'

// critical → destructive (red)
// warning → amber/yellow (custom or outline with amber text)
// ok → green (custom or default)
// out_of_stock → dark (secondary)
// no_data → grey (outline)
```

## Color Scheme
- Critical / Out of Stock: `text-red-600 bg-red-50` or shadcn destructive
- Warning: `text-amber-600 bg-amber-50`
- OK: `text-green-600 bg-green-50`
- No Data: `text-gray-500 bg-gray-50`

## Acceptance Criteria
- [ ] Summary cards show aggregate counts from API
- [ ] Table renders all brands with correct columns
- [ ] Brand name clickable → navigates to SKU detail
- [ ] Status badges color-coded correctly
- [ ] Days-to-stockout color-coded (red < 30, amber 30-90, green > 90)
- [ ] Search filters brands by name
- [ ] "Show critical/warning only" toggle works
- [ ] Sorting by column headers
- [ ] Loading state while fetching (shadcn skeleton or spinner)
- [ ] Empty state if no brands match filter
