# Help System & Onboarding Design

## Overview

Build a three-layer help system for the Art Lounge Stock Intelligence dashboard. The team has never seen this tool — they need full onboarding from "what is this" to "how do I use it daily."

### Three Layers

1. **Guided Tour** — Step-by-step first-time walkthrough (auto-starts, replayable)
2. **Contextual Tooltips** — 12 well-placed info icons with 1-2 sentence explanations + "Learn more" links
3. **Help/Guide Page** — Full reference manual at `/help` with concepts, page guides, workflows, and glossary

All three layers share the same content: the tour introduces concepts, tooltips remind you, the Help page explains fully.

---

## Layer 1: Guided Tour

### Library

react-joyride — lightweight, React-compatible, supports spotlight highlighting, step-by-step progression, and navigation callbacks between pages.

### Tour State

- `localStorage` flag `tourCompleted`
- If not set, tour auto-starts when Home page mounts
- "Replay tour" available from the Help menu in the header
- Tour can be dismissed at any step (marks as completed)

### Tour Flow — 18 Steps

The tour follows a realistic workflow: "Check what needs reordering for a brand."

**Home Page (Steps 1-5):**

| Step | Target | Content |
|------|--------|---------|
| 1 | Center (welcome) | "Welcome to Stock Intelligence. This dashboard tracks 22,000+ SKUs across 167 brands and tells you what to reorder and when. All data syncs nightly from Tally." |
| 2 | Sync indicator | "This shows when data last synced from Tally. A green dot means data is fresh." |
| 3 | Summary cards | "Your daily snapshot. Critical SKUs need ordering now. Brands Needing POs shows how many brands have items to reorder." |
| 4 | Brand search | "Type a brand name to jump straight to it. Try it after the tour." |
| 5 | Priority table | "Brands sorted by urgency — most critical items at the top. Click any row to drill in." |

**Brand Overview (Steps 6-8):**

| Step | Target | Content |
|------|--------|---------|
| 6 | Brand summary cards | "Each card summarizes a brand's health — critical SKUs, warnings, and dead stock at a glance." |
| 7 | Filters/sort | "Filter to only critical brands, or sort by any column to focus your review." |
| 8 | Brand row | "Click a brand to see all its individual SKUs. Let's drill into one." |

**SKU Detail (Steps 9-14):**

| Step | Target | Content |
|------|--------|---------|
| 9 | SKU table | "Every SKU for this brand. Status badges tell you at a glance what needs attention — red means act now." |
| 10 | Column headers | "Stock levels on the left, velocity (how fast it sells) in the middle, reorder suggestion on the right. Velocity is split by channel: wholesale, online, and store — because each is an independent demand track drawing from the same inventory." |
| 11 | Expandable row area | "Click any SKU to see its full story — stock history, sales breakdown, and exactly how the reorder suggestion was calculated." |
| 12 | Stock Timeline tab | "This chart shows daily stock levels over time. Drag across the chart to zoom into a date range. Transactions are listed below." |
| 13 | Calculation tab | "This breaks down exactly how the reorder number was calculated — velocity, lead time, safety buffer. Every number is explained." |
| 14 | Override button | "If the system's estimate doesn't match reality — maybe you know a big order is coming — click Adjust to set your own value. You'll need to provide a reason, and the system will flag it if the data drifts." |

**PO Builder (Steps 15-17):**

| Step | Target | Content |
|------|--------|---------|
| 15 | PO nav/button | "When you're ready to place an order, Build PO creates a purchase order for this brand." |
| 16 | PO table | "Review suggested quantities. Toggle items in or out, adjust quantities, and add notes for your supplier." |
| 17 | Export button | "Export to Excel — ready to send to your supplier." |

**Wrap-up (Step 18):**

| Step | Target | Content |
|------|--------|---------|
| 18 | Help menu icon | "That's the core workflow! You can replay this tour anytime from here. The Help Guide has detailed explanations of every concept and page." |

### Multi-Page Navigation

Steps 1-5 run on `/`. Steps 6-8 navigate to `/brands`. Steps 9-14 navigate to `/brands/WINSOR%20%26%20NEWTON/skus` (or first available brand). Steps 15-17 navigate to the PO builder. Step 18 returns to `/`.

The GuidedTour component manages step-to-route mapping and triggers navigation via React Router when advancing between page groups.

---

## Layer 2: Contextual Tooltips

### Component: `<HelpTip>`

A reusable component wrapping shadcn's Popover:

```tsx
<HelpTip
  tip="Units sold per day, calculated from in-stock days only."
  helpAnchor="velocity"
/>
```

- Renders as a small ⓘ icon (muted color, doesn't compete with data)
- Click/hover opens popover with tip text
- Optional "Learn more →" link navigates to `/help#${helpAnchor}`
- Consistent sizing and positioning across all placements

### Design Principles for Tables

- Info icons on **column headers only**, never per-row
- **First-encounter principle** — explain a concept where it first appears, don't repeat
- **Group explanations** — one icon for a column group (e.g., "Velocity" covers wholesale/online/store/total)
- Self-documenting elements (colored status badges) get a single grouped explanation rather than individual icons

### 12 Placements

| # | Page | Target | Tip | Help Anchor |
|---|------|--------|-----|-------------|
| 1 | Header | Sync indicator | "Last successful data sync from Tally. Runs nightly." | sync |
| 2 | Home | Critical SKUs card | "SKUs with less than lead time + buffer days of stock at current sell-through rate." | stockout-projection |
| 3 | Brand Overview | "Critical" column | "Count of SKUs that need reordering now based on velocity and lead time." | stockout-projection |
| 4 | Brand Overview | "Dead Stock" column | "Items with zero sales for more than the configured threshold days." | dead-stock |
| 5 | SKU Detail | "Status" column | "Reorder urgency based on days of stock remaining: Critical (order now), Warning (order soon), OK (sufficient stock), Out of Stock (zero inventory)." | status-thresholds |
| 6 | SKU Detail | "Velocity" column group | "Units sold per day, calculated from in-stock days only. Split by channel because wholesale, online, and store are parallel demand tracks drawing from the same inventory." | velocity |
| 7 | SKU Detail | ABC badge area | "Revenue classification: A = top 80% revenue (highest priority), B = next 15%, C = bottom 5%. Drives buffer size and reorder priority." | abc-classification |
| 8 | SKU Detail | "Days Left" column | "Projected days until stockout at current total velocity." | stockout-projection |
| 9 | Calculation | Buffer mode selector | "Safety stock multiplier. Global uses ABC-class defaults. Per-SKU lets you set a custom buffer for this item." | lead-time-buffer |
| 10 | Calculation | Methodology header | "Expand to see exactly how each number was calculated, with formulas and source data." | methodology |
| 11 | PO Builder | "Suggested Qty" column | "Recommended order: enough to cover lead time + buffer at current velocity, minus current stock." | reorder-quantity |
| 12 | Settings | XYZ toggle | "Demand variability scoring. Currently 99.6% of SKUs are Z-class (sporadic), so this adds little discrimination for art supplies." | abc-classification |

---

## Layer 3: Help/Guide Page

### Route & Layout

- Route: `/help` (and `/help#anchor` for deep links)
- Layout: Left sidebar navigation (same pattern as Settings page) + scrollable content on right
- Scroll-spy highlights active section in sidebar as user scrolls
- Header "?" icon links here

### Content Structure

#### 1. Getting Started

What this tool does: Stock Intelligence tracks every SKU Art Lounge carries, monitors how fast each one is selling across wholesale, online, and store channels, and tells you when to reorder and how much.

Where the data comes from: All data syncs nightly from Tally Prime. The sync pulls stock levels, transactions, and party information. The system then calculates velocities, projects stockout dates, and generates reorder suggestions.

Who it's for: The purchasing and inventory team. Use it daily to check what needs ordering, weekly to review dead stock and overrides, and whenever you're building a purchase order.

#### 2. Key Concepts

**2.1 Three Parallel Demand Tracks — One Shared Inventory**

Art Lounge serves three markets simultaneously, each with its own demand pattern:

- **Wholesale:** B2B retailers and institutions. Large, irregular orders (50-500 units). Low predictability — one order can equal months of retail sales.
- **Online (Magento, Amazon, Flipkart):** Individual consumers. Steady trickle (1-3 units/day). Most predictable channel — good for baseline velocity.
- **Store (Physical retail):** Walk-in customers. Moderate volume, somewhat seasonal.

All three draw from the same physical stock. A wholesale order of 200 units and 200 individual online orders both empty the same shelf — but they represent completely different demand signals.

The system tracks them as parallel pipelines:
- Each channel gets its own velocity (units/day)
- Total velocity = wholesale + online + store (the combined drain rate)
- Stockout projection uses the combined total
- Per-channel breakdown shows *why* stock is moving

The practical difference: If total velocity is 5 units/day, it matters whether that's 4 wholesale + 0.5 online + 0.5 store (one client could stop ordering) versus 1 wholesale + 3 online + 1 store (stable consumer demand). The breakdown helps you judge forecast reliability.

**2.2 Velocity — Your Sell-Through Rate**

Velocity = units sold per day, counting only days when the item was in stock.

Why exclude out-of-stock days: If a product was out of stock for 3 months waiting for a shipment, those zero-sale days would drag down the average and make the system underestimate demand. By only counting in-stock days, velocity reflects actual demand, not supply gaps.

Flat vs WMA: Flat velocity treats all days equally. Weighted Moving Average (WMA) gives more weight to recent sales — useful for detecting trends. Toggle between them in SKU detail.

Trend indicator: Compares recent 90-day WMA to the yearly average. Trending up (ratio > 1.2), flat, or trending down (ratio < 0.8).

**2.3 ABC Classification — Not All SKUs Are Equal**

Based on revenue contribution:
- **A-class** (top 80% of revenue): Your money-makers. Highest priority, largest safety buffers. Running out of an A-class item costs you the most.
- **B-class** (next 15%): Important but not critical. Moderate buffers.
- **C-class** (bottom 5% + zero revenue): Long tail. Minimal buffers — not worth tying up capital in excess stock for slow items.

ABC drives reorder priority: when you open the dashboard, A-class critical items are flagged first.

**2.4 Lead Time & Safety Buffer**

Lead time = days from placing an order to receiving it. Configured per supplier — Art Lounge's imports typically take 60-120 days by sea.

Safety buffer = extra stock to cover demand variability during lead time. Expressed as a multiplier:
- A-class default: 1.5x (50% extra safety stock)
- B-class default: 1.0x (equal to lead time demand)
- C-class default: 0.5x (minimal safety stock)

The balancing act for an importer: You order infrequently in large batches. Too little buffer = stockouts between shipments. Too much = capital locked in unsold inventory for months.

**2.5 Stockout Projection**

Current stock / total daily velocity = days of stock remaining.

Status thresholds:
- **Critical:** Days remaining < lead time + buffer. Order now or you'll run out before the next shipment arrives.
- **Warning:** Approaching the threshold. Plan your order.
- **OK:** Comfortable stock levels.
- **Out of Stock:** Zero inventory right now.
- **No Data:** Insufficient sales history to calculate.

**2.6 Reorder Quantity**

Formula: (velocity x (lead time + buffer days)) - current stock.

This gives you "how much to order so you don't run out before the next shipment arrives." The PO Builder shows this as the suggested quantity, which you can adjust before exporting.

**2.7 Overrides — When You Know Better**

The system calculates from Tally data, but sometimes you know things it doesn't: a big wholesale order is coming, a product is being discontinued, seasonal demand is shifting.

You can override: velocity, stock levels, or add notes to any SKU. Every override requires a reason and is timestamped.

Staleness: The system monitors whether the underlying data has drifted significantly from when the override was set. Stale overrides are flagged for review on the Overrides page.

**2.8 Channel Classification**

Every transaction in Tally has a party (customer/supplier) name. The system classifies each party into a channel: wholesale, online, store, supplier, internal, or ignore.

This classification drives the entire channel separation. The Parties page shows unclassified parties — velocity calculations may be incomplete until all parties are classified. A banner appears across the app when parties need attention.

#### 3. Page-by-Page Guides

One subsection per page:

- **Home** — Daily starting point. Summary cards, brand search, priority table. Click anything to drill down.
- **Brands** — All 167 brands with health summary. Filter, sort, click to see SKUs.
- **SKU Detail** — The main workspace. Expandable rows with stock timeline, calculation breakdown, and override controls. Filters for date range and velocity type.
- **Critical SKUs** — All critical items in one view, tiered by urgency: Immediate (A-class, <7 days), Urgent (A-class, 7-30 days), Watch (B/C critical + warnings).
- **Build PO** — Purchase order builder. Review suggestions, toggle items, adjust quantities, export to Excel.
- **Dead Stock** — Items not selling. Two tabs: Dead Stock (zero sales beyond threshold) and Slow Movers (very low velocity). Set reorder intent (Normal / Must Stock / Do Not Reorder).
- **Parties** — Classify Tally parties into channels. Essential for accurate velocity calculations.
- **Suppliers** — Manage supplier details and lead times (sea/air/default). Lead times feed into stockout projections.
- **Overrides** — Review all active overrides. Filter for stale overrides where data has drifted. Keep or remove.
- **Settings** — Configure safety buffers, lead times, analysis defaults, dead stock thresholds, and view classification stats.

#### 4. Daily Workflows

**Morning check: "What needs ordering today?"**
1. Open Home — scan the Critical SKUs count
2. Click Critical or a priority brand
3. Review critical items — check velocity and days remaining
4. Click Build PO for brands that need orders
5. Adjust quantities, export to Excel, send to supplier

**Deep dive: "Investigating a specific SKU"**
1. Use brand search on Home or browse Brands page
2. Find the SKU, click to expand
3. Check Stock Timeline — see the stock level history and recent transactions
4. Check Calculation tab — understand why the system recommends what it does
5. Override velocity or stock if you have better information

**Monthly review: "Housekeeping"**
1. Check Overrides page — review and remove stale overrides
2. Check Dead Stock — mark items as "Do Not Reorder" or "Must Stock"
3. Check Parties page — classify any new parties from recent Tally syncs

**Setup: "After a Tally sync brings new parties"**
1. Notice the yellow banner "N new parties need classification"
2. Go to Parties page
3. Classify each party (wholesale/online/store/etc.)
4. Velocity calculations update automatically

#### 5. Glossary

Alphabetical quick-reference. Each entry links to the full explanation in Key Concepts.

- **ABC Classification** — Revenue-based SKU prioritization (A/B/C). [→ Key Concepts](#abc-classification)
- **Buffer** — Safety stock multiplier applied on top of lead time demand. [→ Key Concepts](#lead-time-buffer)
- **Channel** — Sales track: wholesale, online, or store. [→ Key Concepts](#three-channels)
- **Critical** — SKU with less stock than needed to cover lead time + buffer. [→ Key Concepts](#stockout-projection)
- **Days Left** — Projected days until stockout at current velocity. [→ Key Concepts](#stockout-projection)
- **Dead Stock** — Items with zero sales beyond a configured threshold. [→ Page Guide](#dead-stock)
- **Lead Time** — Days from placing an order to receiving it. [→ Key Concepts](#lead-time-buffer)
- **Override** — Manual adjustment to velocity or stock when you have better information. [→ Key Concepts](#overrides)
- **Party** — A customer or supplier in Tally. Must be classified into a channel. [→ Key Concepts](#channel-classification)
- **Reorder Quantity** — Suggested units to order: (velocity x coverage days) - current stock. [→ Key Concepts](#reorder-quantity)
- **Staleness** — When an override's underlying data has drifted significantly from when it was set. [→ Key Concepts](#overrides)
- **Velocity** — Units sold per day, counting only in-stock days. [→ Key Concepts](#velocity)
- **WMA** — Weighted Moving Average. Gives more weight to recent sales than older ones. [→ Key Concepts](#velocity)
- **XYZ Classification** — Demand variability scoring. Most Art Lounge SKUs are Z-class (sporadic). [→ Settings](#xyz)

---

## Implementation

### Prerequisites

1. Install shadcn Popover component: `npx shadcn@latest add popover` (does not exist yet in `components/ui/`)
2. Install react-joyride: `npm install react-joyride` (verify React 19 compatibility — pin version if needed)

### New Files

| File | Purpose |
|------|---------|
| `components/GuidedTour.tsx` | Tour wrapper with 18 steps, page navigation, localStorage state |
| `components/HelpTip.tsx` | Reusable ⓘ tooltip with popover + "Learn more" link |
| `components/HelpMenu.tsx` | Header "?" dropdown (Help Guide + Replay Tour) |
| `pages/Help.tsx` | Full help/guide page with sidebar nav + scroll-spy (reuse Settings page `IntersectionObserver` pattern) |

### HelpTip Component Interface

```tsx
interface HelpTipProps {
  tip: string           // 1-2 sentence explanation
  helpAnchor?: string   // if provided, shows "Learn more →" linking to /help#anchor
}
```

### Modified Files

| File | Change |
|------|--------|
| `App.tsx` | Add `/help` route |
| `components/Layout.tsx` | Add HelpMenu to header, mount GuidedTour, add HelpTip to sync indicator (inline in Layout) |
| `pages/Home.tsx` | Add 1 HelpTip (critical card), add `data-tour` attributes to summary cards, brand search, priority table |
| `pages/BrandOverview.tsx` | Add 2 HelpTips ("Health" column header, "Dead / Slow" column header), add `data-tour` attributes |
| `pages/SkuDetail.tsx` | Add 4 HelpTips (status, velocity group, ABC, days left), add `data-tour` attributes to table and expand trigger |
| `components/CalculationBreakdown.tsx` | Add 2 HelpTips (buffer mode, methodology), add `data-tour` attributes to override buttons |
| `pages/PoBuilder.tsx` | Add 1 HelpTip (suggested qty), add `data-tour` attributes to PO table and export button |
| `pages/Settings.tsx` | Add 1 HelpTip (XYZ toggle) |

### Tour DOM Targeting Convention

All tour targets use `data-tour` attributes on the target elements. Convention: `data-tour="step-name"` in kebab-case.

Examples:
- `data-tour="sync-indicator"` on the sync status div in Layout.tsx
- `data-tour="summary-cards"` on the cards container in Home.tsx
- `data-tour="brand-search"` on the search input in Home.tsx
- `data-tour="sku-table"` on the table wrapper in SkuDetail.tsx
- `data-tour="export-button"` on the export button in PoBuilder.tsx

react-joyride targets these via CSS selector: `[data-tour="step-name"]`.

### Tour Multi-Page Strategy

The `GuidedTour` component lives in `Layout.tsx` (always mounted). It:
1. Reads current step index from state
2. Maps step ranges to routes (steps 1-5 → `/`, steps 6-8 → `/brands`, etc.)
3. On "Next" click, if the next step requires a different route, navigates first then advances
4. Uses react-joyride's `callback` prop to handle step transitions
5. For SKU Detail steps, navigates to `/brands/WINSOR%20%26%20NEWTON/skus` (known brand with good data)
6. For PO Builder steps, navigates to `/brands/WINSOR%20%26%20NEWTON/po`

### Tour Resilience

**Wait-for-target strategy:** After navigating to a new route, the tour pauses and polls for the target element using `requestAnimationFrame` loop with a 5-second timeout. This handles:
- Lazy-loaded page chunks downloading
- API data loading before elements render
- React Suspense boundaries resolving

If the target doesn't appear within 5 seconds, the tour skips to the next step on the same page (or shows a "Let's continue" fallback).

**Programmatic row expansion (Steps 11-14):** The tour triggers a click on the first SKU row's expand button before advancing to steps that target expanded content. The GuidedTour component:
1. After navigating to SKU Detail, waits for the table to render
2. Programmatically clicks the first row's expand toggle via `document.querySelector('[data-tour="first-sku-row"]').click()`
3. Waits for expanded content to appear
4. Then switches to the "Calculation" tab via click before steps targeting calculation content

**Empty state:** If the brands API returns zero results (unlikely in production but possible in dev), the tour gracefully skips steps 6-17 and jumps to step 18 with a message: "No brand data available right now. Complete the tour later when data has synced."

**Mid-tour navigation:** If the user navigates away using browser back/forward, the tour pauses. On return to the expected route, it resumes. If they navigate to a completely different page, the tour ends gracefully and can be replayed from the Help menu.

### Tooltip Placement Corrections

Per code review, actual column header names differ from initial spec:

| # | Page | Actual Target | Tip | Help Anchor |
|---|------|---------------|-----|-------------|
| 3 | Brand Overview | "Health" column header | "Combined health indicator: count of critical, warning, and ok SKUs for this brand." | stockout-projection |
| 4 | Brand Overview | "Dead / Slow" column header | "Dead stock (zero sales beyond threshold) and slow movers (very low velocity)." | dead-stock |

### Tour Step 10 Correction

Step 10 targets the SKU Detail table column headers. Actual columns are: Status, Part No, SKU Name, Stock, Velocity /mo, ABC. The content should read:

"Each column tells part of the story. Status shows urgency, Stock shows what you have, Velocity shows how fast it sells (split by channel when expanded), and ABC shows revenue importance."

### Lead Time Note

Help content should say "typically 90-180 days by sea" to match the PO Builder's default of 180 days for sea freight.

---

## Success Criteria

- First-time user can complete the tour in under 3 minutes
- Every non-obvious term in the UI has a tooltip within one click
- Help page covers every concept needed to make reorder decisions
- Tooltips don't clutter table views (column headers only, 12 total)
- Tour is replayable and Help page is always accessible
- No new API endpoints needed — all content is static/client-side
- Tour handles lazy loading, async data, and edge cases gracefully
