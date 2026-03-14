# UI/UX Audit — Design Specification

**Date:** 2026-03-14
**Status:** Approved
**Goal:** Reduce noise, surface what operations needs, and build confidence in the system's recommendations through 6 targeted changes.

## Context

The dashboard has accumulated features that obscure the primary workflow. An operations user typically:
1. Knows which brand/supplier they need to order for
2. Jumps straight to that brand's SKUs
3. Needs Part No + Name + Stock + Velocity + ABC class visible without expanding
4. Wants channel velocity (wholesale/online/store) and reorder suggestion on expand — not buried in tabs
5. Needs to trust the math — conclusion first, then drill into details
6. Needs a central place for global configuration

The current UI fails these workflows: Part No is hidden in a secondary row, channel velocity was removed from easy access, the Calculation Breakdown is confusing rather than confidence-building, and there's no Settings page.

---

## Change 1: SKU Table — Reordered Columns

**Files:** `src/dashboard/src/pages/SkuDetail.tsx`

### Current columns (8)
| Expand | Status | SKU Name + badges | Stock | Velocity /mo | Days Left | Suggested | Intent |
Secondary row below each SKU: ABC badge, XYZ badge, Part No, Hazardous indicator

### New columns (7)
| Expand | Status | Part No | SKU Name | Stock | Velocity /mo | ABC |

**Changes:**
- **Part No promoted** to a primary column — bold monospace, immediately visible without expanding. This is the supplier's code and the single most important identifier for operations.
- **ABC class promoted** from secondary row to primary column — small colored badge (A=red, B=amber, C=gray).
- **Days Left, Suggested Qty removed** from main row — moved to expanded summary strip (Change 2). These are detail-level data points, not scan-level.
- **Intent column removed** from main row — intent badges (Must Stock, DNR) shown inline with SKU Name for display. The editable `ReorderIntentSelector` dropdown moves into the expanded row's summary strip, in the Reorder section next to the suggested qty.
- **Secondary metadata row removed entirely** — Hazardous shown as a small amber square icon inline with SKU Name. XYZ shown only in expanded strip (informational, not actionable at scan level).
- **SKU Name column** shows just the name + hazardous icon (amber ■) + intent badges (Must Stock, DNR) if set. No other badges.

**Grid template:** `28px 80px 110px 1fr 80px 100px 60px` (approximate, tune during implementation).

**Data availability:** `part_no` already exists in SkuMetrics type and is returned by the SKU list API. `abc_class` is also already in the response.

---

## Change 2: Expanded Row — Summary Strip Before Tabs

**Files:** `src/dashboard/src/pages/SkuDetail.tsx`

### Current expanded row
Three tabs: Stock Timeline | Transactions | Calculation. No summary — must click into tabs to see any detail.

### New expanded row
**Summary strip** (always visible on expand) → **Tabs** below.

**Summary strip layout** — 3-column grid:

| Velocity by Channel | Stock & Stockout | Reorder |
|---|---|---|
| W: **4.2** O: **1.8** S: **0.3** │ Total: **6.3** ↗ | In Stock: **42** · Days Left: **200d** | Suggested: **85 units** · Buffer 1.5x · Lead 180d |

**Design details:**
- Each section has a small uppercase label (10px, muted) and large metric values (18px, bold).
- Channel velocity uses color coding: Wholesale=blue (#2563eb), Online=purple (#7c3aed), Store=green (#059669).
- Total velocity separated by a thin vertical border, includes trend icon.
- Days Left colored by severity (red if critical, amber if warning, green if ok).
- Reorder section shows buffer multiplier and lead time as small muted text below the suggested qty.
- ABC and XYZ badges shown as small pills in the reorder section footer.
- Horizontal border-bottom (2px) separates strip from tabs.

**Tabs below** — same 3 tabs (Stock Timeline, Transactions, Calculation), unchanged.

**Data availability:**
- `wholesale_velocity` and `online_velocity` exist in `SkuMetrics` and are returned by the SKU list API.
- `store_velocity` does NOT exist as a stored field — it is derived at runtime as `max(0, total - wholesale - online)`. Must be added to the SKU list API response and the `SkuMetrics` TypeScript type as a computed field.
- `current_stock`, `days_to_stockout`, `reorder_qty_suggested`, `safety_buffer`, `abc_class`, `xyz_class`, `trend_direction` — all already in `SkuMetrics`.
- `supplier_lead_time` is NOT on `SkuMetrics` — it lives on `BrandMetrics`. The summary strip should receive lead time from the page-level brand query (SkuDetail already fetches brand data for the header). Pass it as a prop to the expanded row.

**ReorderIntentSelector placement:** The editable intent dropdown (removed from main row in Change 1) is placed in the summary strip's Reorder section, below the suggested qty and buffer info.

---

## Change 3: Calculation Breakdown — 3-Layer Confidence Builder

**Files:** `src/dashboard/src/components/CalculationBreakdown.tsx`

### Current state
5 sequential cards: Data Source → Position Reconstruction → Transaction Breakdown → Velocity Calculation → Stockout & Reorder. All visible at once, ~600px of dense technical content. User must scroll through methodology to find the conclusion.

### New state — 3 collapsible layers

**Layer 1: Verdict (always visible, not collapsible)**
A green-bordered card with a human-readable recommendation:
> "Order 85 units. Wholesale demand is driving this at 4.2/mo. At current velocity you have ~200 days of stock, but with 180-day sea freight lead time and 1.5x A-class safety buffer, you should order now to avoid stockout."

This is generated from existing data fields: `reorder.suggested_qty`, channel velocities, `stockout.days_to_stockout`, `reorder.supplier_lead_time`, `reorder.buffer_multiplier`, `reorder.status`.

Verdict templates by status (`{dominant_channel}` is derived in frontend by comparing wholesale/online/store velocities — not an API field):
- **Critical:** "Order {qty} units. {dominant_channel} demand is driving this at {velocity}/mo. At current velocity you have ~{days} days of stock, but with {lead_time}-day lead time and {buffer}x {abc}-class buffer, you should order now."
- **Warning:** "Consider ordering {qty} units. You have ~{days} days of stock — within the {lead_time}-day lead time window."
- **OK:** "No immediate action needed. You have ~{days} days of stock, well above the {lead_time}-day lead time."
- **Out of Stock:** "Out of stock — order {qty} units immediately. Last had stock {days_ago} days ago."
- **No Data:** "Insufficient data to make a recommendation. No velocity data available."

**Layer 2: Key Assumptions (collapsible, expanded by default)**
A table of input values the system used, each with an "Edit" link to override:

| Input | Value | Action |
|-------|-------|--------|
| Lead Time | 180 days (Sea Freight) | Edit |
| Safety Buffer | 1.5x (A-class, ABC only) | Edit |
| Total Velocity | 6.3 /mo (W: 4.2 + O: 1.8 + S: 0.3) | Edit |
| Current Stock | 42 units | Edit |
| In-Stock Days | 285 of 365 days (78%) | *(gut check — not editable)* |

"Edit" behavior varies by row:
- **Lead Time:** "Edit" links to the Suppliers page (`/suppliers`) where lead times are managed — this is a supplier-level setting, not a per-SKU override.
- **Safety Buffer:** "Edit" opens the existing `BufferModeSelector` inline (already built) — allows switching between ABC-only, XYZ, or follow-global.
- **Total Velocity / Current Stock:** "Edit" opens the existing `OverrideForm` inline (already built) — creates a per-SKU override.
- **In-Stock Days:** Not editable — shown as a gut check, labeled as such.

The BufferModeSelector (already built) is shown below this table.

**Layer 3: Methodology & Formulas (collapsible, collapsed by default)**
5 numbered sections, each in a light gray bordered card:

1. **Velocity — How we measure demand:** Formula + channel-by-channel table (units sold ÷ in-stock days × 30) + confidence note + out-of-stock exclusion note.
2. **In-Stock Days — How we count active periods:** Visual bar (green=in-stock, red=out-of-stock periods over FY) + day counts. Reuses existing `InStockBar` component.
3. **Stockout Projection:** Step-by-step arithmetic (`current_stock / daily_burn_rate = days_left`) + estimated stockout date.
4. **Reorder Quantity:** Full formula chain (`lead_time_demand → safety_stock → reorder_point → suggested_qty`) with actual numbers plugged in.
5. **Status Determination:** Threshold table (Critical ≤ lead_time × 1.0, Warning ≤ lead_time × 1.5, OK > lead_time × 1.5, Out of Stock ≤ 0) + "This SKU: {status}" callout.

**Data availability:** All data comes from the existing `BreakdownResponse`. No new API fields needed — just restructuring the presentation.

**What's removed:**
- **Data Source card** — merged into Layer 2 (current stock row shows source, data-as-of shown as small footer text).
- **Position Reconstruction card** — removed entirely (user confirmed this becomes meaningless as Tally data improves; the in-stock bar in Layer 3 covers the useful part).
- **Transaction Breakdown card** — already available in the Transactions tab; no need to duplicate in Calculation.

---

## Change 4: Home Page — Simplified to Actionable Items

**Files:** `src/dashboard/src/pages/Home.tsx`

### Current state
3 sections, 8 cards: "Needs Action" (3 cards), "Portfolio Health" (4 chart cards: Stock Status bar, Revenue Distribution bar, Demand Trends indicators, Inventory Quality counts), "Top Priority Brands" table.

### New state
3 sections, simplified:

**Section 1: Brand Search**
A prominent search input: "Jump to brand... (type to search)". On selection, navigates directly to `/brands/{categoryName}/skus`. Uses existing brand search from BrandOverview.

**Section 2: Action Cards (3 cards, grid)**
| Critical SKUs | Brands Needing POs | Total Brands |
|---|---|---|
| **47** across 12 brands (red) | **8** brands (amber) | **167** tracked (neutral) |

First two cards are clickable — Critical navigates to `/critical`, Brands links to `/brands` with critical filter.

**Section 3: Priority Brands Table**
Same as current "Top Priority Brands" table but simplified columns:
| Brand | Critical | Warning | Out of Stock | → |
Clickable rows navigate to brand SKU page. Shows top 10, "View all brands →" link at bottom.

**What's removed:**
- Portfolio Health section entirely (Stock Status bar, Revenue Distribution, Demand Trends, Inventory Quality). Can return later when there's a real use case.
- The 3 "Needs Action" cards replaced by 3 simpler action cards.

**Data:** Still uses `fetchDashboardSummary()` — same API, just fewer fields displayed.

---

## Change 5: Settings Page (New)

**Files (new):**
- `src/dashboard/src/pages/Settings.tsx`
- Route added in `src/dashboard/src/App.tsx`

### Layout
Sidebar navigation (left, 200px) + content area (right).

**Sidebar sections:**
1. Safety Buffers
2. Lead Times
3. Analysis Defaults
4. Dead Stock Thresholds
5. Classification

Each section is a scroll target within the same page (not separate routes). Active section highlighted with left border + background.

### Section content

**Safety Buffers:**
- Buffer mode display: "ABC Only (recommended)" or "ABC×XYZ" — reflects current `use_xyz_buffer` setting.
- ABC-only buffer table: A → 1.5x, B → 1.3x, C → 1.1x (editable).
- Toggle: "Use XYZ-adjusted buffers" switch — same as in ClassificationExplainer but now in a proper location.
- If XYZ enabled: show the full 3×3 matrix (A×X, A×Y, A×Z, etc.)
- Note: "Changes take effect after next nightly sync. Per-item overrides are unaffected."

**Lead Times:**
- Table of suppliers with lead times (read from suppliers table).
- "Manage suppliers →" link to `/suppliers` page (don't duplicate CRUD here).

**Analysis Defaults:**
- Velocity type: Flat vs WMA (currently only a frontend toggle with no persistence — this makes it a persisted default).
- Default date range: Full FY, Last 6 months, Last 3 months.
- These are new `app_settings` keys: `default_velocity_type`, `default_date_range`.
- **Consumers:** `SkuDetail.tsx`, `CriticalSkus.tsx`, and `DeadStock.tsx` should read these settings via `fetchSettings()` on mount and use them as initial state values for their velocity type and date range selectors. This replaces the current hardcoded defaults (`'flat'` and `'full_fy'`).

**Dead Stock Thresholds:**
- Dead stock threshold: days input (currently in DeadStock page header — move canonical control here).
- Slow mover threshold: velocity input (same — move here).
- These already exist as `app_settings` keys: `dead_stock_threshold_days`, `slow_mover_velocity_threshold`.

**Classification:**
- Link to ClassificationExplainer modal (or embed the explainer content directly).
- ABC thresholds display (currently hardcoded: A=80%, B=95%, C=100%).
- XYZ thresholds display (CV < 0.5 = X, < 1.0 = Y, else Z).
- Note: these thresholds are not editable in V1 (engine constants). Show as informational.

### API
Uses existing `GET /api/settings` and `PUT /api/settings/{key}` endpoints. New settings keys (`default_velocity_type`, `default_date_range`) need to be seeded in `app_settings` table.

---

## Change 6: Navigation — Grouped with Settings

**Files:** `src/dashboard/src/components/Layout.tsx`

### Current nav (7 items, flat)
Home | Brands | Critical | Build PO | Parties | Suppliers | Overrides

### New nav (8 items, grouped with separators)
Home | Brands | Critical | Build PO | **·** | Parties | Suppliers | Overrides | **·** | ⚙ Settings

**Groups:**
1. **Primary actions:** Home, Brands, Critical, Build PO — the daily workflow
2. **Data management:** Parties, Suppliers, Overrides — setup and maintenance
3. **Settings:** Global configuration

Separator is a subtle vertical bar (color: `#94a3b8`, thin). Settings uses a gear icon (⚙) prefix.

---

## Deferred Items (Not in This Spec)

These were discussed during brainstorming and explicitly deferred:
- **Timeline + Transactions tabs merged** into one view — future improvement
- **Position Reconstruction phased out** as Tally data improves — removed from Calculation Breakdown but not from API
- **Home page complexity added back** (charts, distributions) — when needs emerge
- **Mobile responsiveness** — not in scope

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `src/dashboard/src/pages/SkuDetail.tsx` | Column reorder, summary strip, read analysis defaults from settings |
| `src/dashboard/src/components/CalculationBreakdown.tsx` | Complete restructure to 3-layer design |
| `src/dashboard/src/pages/Home.tsx` | Strip to search + action cards + priority table |
| `src/dashboard/src/pages/Settings.tsx` **(new)** | Settings page with sidebar sections |
| `src/dashboard/src/App.tsx` | Add `/settings` route |
| `src/dashboard/src/components/Layout.tsx` | Grouped nav, Settings link |
| `src/dashboard/src/lib/types.ts` | Add channel velocities to SkuMetrics (if not present) |
| `src/api/routes/skus.py` | Add wholesale/online/store velocity to SKU list response |
| `src/db/migration_v4_settings_defaults.sql` **(new)** | Seed new settings keys |

## Files NOT Modified

- `src/engine/*` — no engine changes
- `src/api/routes/po.py` — PO builder unchanged
- `src/dashboard/src/pages/PoBuilder.tsx` — unchanged
- `src/dashboard/src/pages/BrandOverview.tsx` — unchanged
- `src/dashboard/src/pages/CriticalSkus.tsx` — unchanged
- `src/dashboard/src/pages/DeadStock.tsx` — threshold controls remain in-page as secondary access (primary moves to Settings)
