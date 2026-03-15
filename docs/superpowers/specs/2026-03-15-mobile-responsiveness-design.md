# Mobile Responsiveness — Design Spec

**Goal:** Make the entire Art Lounge Stock Intelligence dashboard fully functional on mobile phones (Android + iPhone, all screen sizes) with a native-feeling experience — not just a shrunken desktop.

**Scope:** All 11 pages, full workflow capability, touch-optimized interactions.

---

## 1. Responsive Architecture

### Breakpoints (3 tiers)

| Tier | Width | Behavior |
|------|-------|----------|
| Mobile | `< 768px` | Single column, bottom tabs, list rows, bottom sheets |
| Tablet | `768px–1024px` | Hybrid — 2-col grids where helpful, keeps top header nav |
| Desktop | `> 1024px` | Current layout unchanged |

### Core Principle

Mobile-specific components where CSS alone won't cut it. A `useIsMobile()` hook (based on `window.matchMedia('(max-width: 767px)')`) conditionally renders mobile vs desktop variants for views that need fundamentally different markup (list rows vs table rows, bottom sheets vs dialogs).

### What stays the same across all breakpoints
- Same API calls, same React Query cache, same routing
- Same color system, status badges, ABC/XYZ badges
- Same data — no "lite" mobile version

### What changes on mobile
- Layout shell: bottom tab bar + hamburger drawer replaces header nav
- Tables → compact list rows with tap-to-expand/navigate
- Summary grids → stacked cards or horizontal scroll strips
- Dialogs → bottom sheets (more thumb-friendly)
- Chart interactions: date preset buttons replace drag-to-select
- Filter controls → bottom sheet drawer with active filter chips
- Forms → full-width stacked inputs

---

## 2. Layout Shell

### Mobile Header (replaces desktop header nav)
- Compact: hamburger (☰) + page title + sync status dot + help icon
- Fixed at top, does not scroll with content

### Bottom Tab Bar
- 4 tabs for daily workflow: **Home**, **Brands**, **Critical**, **Build PO**
- Active tab highlighted with primary color
- Safe area padding at bottom for iPhone home indicator
- Only visible on mobile (`< 768px`)

### Hamburger Drawer
- Slides from left with backdrop overlay
- Contains admin/setup pages grouped by section:
  - **Data Management:** Parties, Suppliers, Overrides, Dead Stock
  - **System:** Settings, Help Guide
- Sync info (last sync time, next sync) shown at bottom of drawer
- Tap outside or swipe left to close

### Desktop layout
- Completely unchanged above 768px — no modifications to current header nav

---

## 3. Shared Mobile Patterns

### Compact List Rows (replaces tables)
Used for: SKU lists, priority brands, critical SKUs, PO items, dead stock, parties, suppliers, overrides.

Structure per row:
- Left border colored by reorder status (red=critical, amber=warning, green=ok, gray=no_data/OOS)
- Line 1: Item name (bold, truncated) + status badge (right-aligned)
- Line 2: Key metrics inline (Stock, Velocity, Days to Stockout) + ABC badge
- Tap action: navigate to detail view or expand inline (depends on page)

### Sticky Search + Filter Chip Drawer
Used on: SKU Detail, Brand Overview, Critical SKUs, Dead Stock.

- Search bar sticky at top of scrollable content
- "Filters" button beside search with active count badge
- Tapping "Filters" opens a bottom sheet with all filter options
- Active filters shown as dismissible chips below search bar
- Quick status pill tabs (horizontal scroll) for the most common filter dimension

### Bottom Sheets (replaces dialogs)
Used for: Calculation breakdown, override forms, sort options, filter panels, SKU input dialog, classification picker.

- Slide up from bottom, draggable handle at top
- Backdrop overlay, tap outside to close
- Max height: 85vh (user can always see the page behind)
- Replaces `Dialog` component on mobile, keeps `Dialog` on desktop

### Cards (for summary views only)
Used on: Home summary stats, Brand Overview.

- Rounded corners, subtle background
- Status color accent (left border or background tint)
- Tap navigates to detail

---

## 4. Page-by-Page Mobile Design

### 4.1 Home (Dashboard)

**Summary cards:** Horizontal scroll strip (Critical / Warning / Healthy counts). Cards have colored backgrounds, large numbers, horizontal scroll prevents vertical space waste.

**Search:** Sticky below summary strip.

**Priority brands:** Compact list rows sorted by urgency. Each row shows brand name, critical/warning count badge, SKU count, stock value. Tap navigates to Brand → SKU Detail.

### 4.2 Brand Overview

**View toggle:** List/Cards toggle in header (compact for power users, cards for visual scan).

**Cards view:** Each brand is a card with:
- Brand name + SKU count
- Health percentage (right-aligned, color-coded)
- 4-cell status grid: Critical / Warning / OK / Dead counts
- Left border by worst status
- Tap navigates to SKU Detail for that brand

**List view:** Compact list rows with brand name + health % + worst-status badge.

**Search + Filters:** Sticky search + filter button. Filter bottom sheet contains: status filter, sort order. Active filters as chips.

### 4.3 SKU Detail

**SKU List (collapsed state):**
- Back arrow + brand name in header with SKU count
- Sticky search + horizontal scrolling status pill tabs (All / Critical / Warning / OK / OOS)
- Sort button in header → opens sort bottom sheet (Status, Stock, Velocity, Stockout, ABC)
- Compact list rows

**SKU Detail (expanded state — full-screen navigate):**
On mobile, tapping a SKU row navigates to a dedicated full-screen detail view (not inline expand). This provides room for all detail content:
- Header: back arrow + SKU name + Part No + status badge
- 2×2 metric cards: Current Stock, Days to Stockout, Total Velocity, Suggested Qty
- Channel velocity breakdown: Wholesale / Online / Store rows
- Stock timeline chart: full-width area chart with date preset buttons (7d / 30d / 90d / All). No drag-to-select on touch.
- Classification badges: ABC, XYZ, Buffer multiplier
- Action buttons: "View Calculations" (opens CalculationBreakdown bottom sheet), "Override" (opens override form bottom sheet)
- Back arrow returns to SKU list with scroll position preserved

### 4.4 Critical SKUs

**Tier layout:** 3 collapsible sections (Immediate / Urgent / Watch) with count badges in headers. Tap header to expand/collapse.

**SKU rows:** Same compact list rows. Tap navigates to full-screen SKU detail view.

### 4.5 PO Builder

**Config section:** Lead time, buffer override, velocity type controls in a collapsible card at top. Collapsed by default after first edit to maximize list space.

**SKU list:** Compact list rows with inline editable quantity field. Tap the quantity number to edit (opens numeric keyboard).

**Export:** Sticky floating action button (FAB) at bottom-right, above tab bar. Tapping exports Excel.

**Add Custom SKUs:** "Add" button in header. Dialog renders as full-screen bottom sheet with search input.

### 4.6 Dead Stock

**Tabs:** Dead / Slow Mover tabs stay as horizontal tabs at top.

**SKU rows:** Same compact list pattern.

**Threshold config:** Moves into the "Filters" bottom sheet.

**Reorder intent selector:** Renders inline (already compact enough).

### 4.7 Party Classification

**List rows:** Party name + current classification badge.

**Edit:** Tap row to change classification via a bottom sheet picker with options: Supplier / Wholesale / Online / Store / Internal / Ignore.

### 4.8 Supplier Management

**List:** Compact rows showing supplier name, default lead time, buffer override value.

**Edit:** Tap row to open full-screen form with stacked full-width inputs (name, lead times, currency, buffer override, notes).

**Add:** Button in header. Opens same full-screen form.

**Delete:** Requires confirmation dialog (bottom sheet on mobile).

### 4.9 Override Review

**List rows:** Override type + SKU name + value + age.

**Actions:** Keep / Remove buttons revealed on tap (not swipe — more accessible). Stale filter toggle at top.

### 4.10 Settings

**Layout:** Current sidebar-with-sections becomes single-column stacked accordion. Each section (Safety Buffers, Lead Times, Analysis Defaults, Dead Stock Thresholds, Classification Rules) is a collapsible panel.

**Inputs:** Full-width. Number inputs get `inputmode="decimal"` for numeric keyboard.

**Save:** Sticky button at bottom of viewport.

### 4.11 Help

**Layout:** Single-column scroll (already mostly works at mobile width).

**Table of contents:** Sidebar scroll-spy becomes a sticky dropdown selector at top of page.

**Content:** Visual formula boxes, cards, and grids reflow to full-width single-column.

---

## 5. Touch & Accessibility

- **Minimum touch targets:** 44×44px for all interactive elements (Apple HIG guideline)
- **Input modes:** `inputmode="numeric"` on quantity/stock fields, `inputmode="decimal"` on buffer/lead-time fields
- **Safe areas:** `env(safe-area-inset-bottom)` padding on bottom tab bar for iPhone notch/home indicator
- **No hover-dependent UI:** All hover tooltips become tap-to-show. HelpTip popovers already work on tap. `onMouseEnter` prefetch on Brand Overview won't fire on mobile — acceptable, data loads on tap instead.
- **Scroll position preservation:** When navigating back from detail views, restore scroll position in the list using React Router's `useScrollRestoration` or manual `sessionStorage` of scroll offset.
- **Pull-to-refresh:** Not needed (data refreshes via sync, not user pull)

---

## 6. Performance on Mobile

### List virtualization
Pages that render large lists without pagination need virtual scrolling on mobile to prevent jank:
- **Dead Stock** (loads all items for a brand — can be 1000+): use `@tanstack/react-virtual` for the list rows
- **Critical SKUs** (loads up to 500): virtualize if scroll performance degrades
- **SKU Detail** already paginates (200 per page) — acceptable without virtualization but consider reducing default page size to 100 on mobile

### Loading & skeleton states
- `MobileListRow` needs a skeleton variant (two gray bars mimicking the 2-line row layout)
- `MobileLayout` shows a centered spinner for route-level lazy loading
- Existing page-level loading skeletons adapt to mobile column layouts

### Error states
- Existing inline error messages and empty state text work at mobile widths — no separate mobile treatment needed
- Network errors show a full-width banner below the mobile header

---

## 7. Guided Tour on Mobile

The existing react-joyride tour targets desktop DOM elements (`data-tour` attributes on table headers, header nav buttons, etc.) that don't exist on mobile. On mobile:

- **Disable the existing tour** — the desktop tour steps reference UI that doesn't exist on mobile
- **Create mobile-specific tour steps** — a separate `mobile-tour-steps.ts` with steps targeting mobile elements (`data-tour-mobile` attributes on bottom tab bar, list rows, filter button, etc.)
- **Tour step count:** Shorter than desktop (10-12 steps vs 18) — mobile users expect faster onboarding
- **Tooltip positioning:** Joyride tooltips use `placement: "top"` or `"bottom"` (never `"left"`/`"right"` which can overflow on narrow screens)
- **Tour launch:** Same HelpMenu trigger, `useIsMobile()` selects which step set to use

---

## 8. Warning Banners on Mobile

Desktop shows alert banners between header and content for unclassified parties and stale overrides. On mobile:

- Collapse into a **single-line notification bar** below the mobile header
- Shows the most urgent warning with a count: "3 unclassified parties · 5 stale overrides"
- Tap the bar to navigate to the relevant page (Parties or Overrides)
- Dismissible per-session (tap × to hide, reappears next session)

---

## 9. SKU Detail Routing

On mobile, tapping a SKU row in the list needs to show a full-screen detail view. Implementation approach:

- **State-driven overlay, not a new route.** The SKU detail view is rendered as a full-screen overlay within the existing `/brands/:categoryName/skus` route, driven by component state (`selectedSku`).
- **History API integration:** Push a history entry when opening detail view so the browser back button closes it and returns to the list. Use `window.history.pushState` / `popstate` listener.
- **Scroll position:** Store the list scroll offset before opening detail, restore it on close.
- This avoids adding new routes and keeps the URL structure clean. Desktop behavior (inline expand) is unchanged.

---

## 10. Implementation Strategy

### New shared components to create
- `MobileLayout.tsx` — mobile shell (header + bottom tabs + drawer)
- `BottomSheet.tsx` — wraps the existing shadcn `Sheet` component with `side="bottom"` and adds mobile defaults: drag handle, 85vh max-height, safe-area padding, backdrop. Not a new primitive — a convenience wrapper.
- `MobileListRow.tsx` — reusable compact list row component with skeleton variant
- `FilterDrawer.tsx` — bottom sheet with filter controls + chip display
- `useIsMobile.ts` — reactive media query hook (`max-width: 767px`) using `window.matchMedia` with change event listener. Re-renders component when crossing the breakpoint. Follow the standard shadcn/ui `useIsMobile` pattern.

### Modification approach
Each page gets responsive treatment:
1. Add `useIsMobile()` check
2. Render mobile-specific markup when true (list rows, different grid layouts)
3. Desktop markup unchanged when false
4. Replace `Dialog` usage with `BottomSheet` on mobile
5. PO Builder: tap SKU row opens bottom sheet for qty + notes editing (rather than inline editing which is too cramped)

### Tablet tier (768px–1024px)
Not a separate implementation pass. Tablet gets desktop layout with natural Tailwind responsive adjustments:
- Brand Overview cards: `md:grid-cols-2` (already exists)
- Home summary cards: `md:grid-cols-3` (already fits)
- Tables: keep full desktop tables (tablets have enough width)
- Navigation: keep desktop header nav

### Dead Stock drawer access
The hamburger drawer's "Dead Stock" link navigates to `/brands` with a "dead stock" filter pre-applied, since Dead Stock is brand-scoped. User picks a brand first, then sees its dead stock.

### No backend changes
All changes are frontend-only. Same API, same data shape, same queries.

---

## 11. What's NOT in scope
- Native app (PWA or React Native) — browser-only
- Offline support — requires network connection
- Push notifications — future enhancement
- Tablet-specific layouts beyond responsive Tailwind breakpoints
- Landscape mode optimization — portrait-first
- Dark/light mode toggle — stays dark theme only
