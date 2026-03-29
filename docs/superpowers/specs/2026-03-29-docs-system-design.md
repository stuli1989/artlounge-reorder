# Documentation System — Design Spec

## Problem

The current docs are split across three places — `how-it-works.html` (Tally-era, outdated), `/help` (in-app React page), and tribal knowledge. After the Unicommerce migration and status rename, none of them accurately describe the system. We need one unified, encyclopedic reference that onboards everyone from zero and serves as the definitive reference for how the system works.

## Design Principles

- **Crisp writing** — friendly tone, fewest words needed. No walls of text. Let tables, diagrams, and formulas carry the weight.
- **Show, don't tell** — real transaction tables, monospace formula blocks, flow diagrams. If you can verify it with a calculator, you understand it.
- **Archetype-driven** — teach through 6 real SKU profiles that cover the diversity of the catalog.
- **Full transparency** — document the INVOICES bug, the KG Shipping Package workaround, the drift monitoring, known limitations. This is the source of truth.

## Architecture

### Implementation

- **React pages within the dashboard app** — first-class citizens, not a bolt-on.
- **Routing:** `/docs` redirects to `/docs/overview`. Each chapter has its own route. Uses nested `<Route>` with `<Outlet />` for the DocsLayout shell.
- **No auth required** — `/docs/*` routes are placed OUTSIDE `<ProtectedRoute />` in App.tsx, at the same level as `/login`. Publicly accessible for onboarding.
- **In-app navigation** — nav bar "Docs" link (was "Help") points to `/docs`. Icon: BookOpen.
- **Sidebar nav** — persistent left sidebar with chapter-level + section-level links. Scroll spy highlights current section. On mobile: slides in as a drawer via hamburger button.
- **Light/dark mode** — docs-only toggle stored in `localStorage` key `docs-theme`. Independent of dashboard theme. Defaults to light.
- **Content as React components** — not markdown. Enables embedded diagrams, interactive elements, styled tables.
- **Each chapter is its own file** — clean separation, manageable file sizes. Lazy-loaded via `React.lazy()` following existing dashboard pattern.
- **Cross-linking** — chapters link to each other using `<Link to="/docs/data-sources#invoices-bug">` with hash anchors. CalloutBox component takes a `linkTo` prop.
- **Old URL redirect** — `how-it-works.html` is deleted. No redirect needed (internal tool, not indexed).
- **Invalid routes** — `/docs/*` catch-all redirects to `/docs/overview`.
- **No SSR** — SPA-only is fine. Internal tool, not indexed by search engines.

### Visual Design

- **Design reference:** clean editorial like Linear's changelog or Stripe's docs — generous whitespace, clear hierarchy, polished but not flashy.
- **Typography:** use Inter (already available via Tailwind defaults) for body, monospace for formulas/code blocks. No custom font loading.
- **Light mode default** with dark mode toggle. Docs pages use their own CSS variables scoped under a `.docs-light` / `.docs-dark` class on the layout wrapper.
- **Interactivity: targeted, not flashy** — two interactive elements total:
  1. **Formula calculator** (Chapter 3): 5 number inputs (stock, velocity, lead time, coverage, buffer) → displays computed suggested qty and resulting status badge. Pure React state, no API calls.
  2. **Status decision tree** (Chapter 4): static SVG flowchart. On hover/click of a status node, highlights the path from root to that status. CSS transitions only, no animation library.
- **Animated data flow** (Chapter 2): CSS-animated dots moving along connecting lines between flow diagram nodes. Plays on scroll-into-view via IntersectionObserver. Falls back to static diagram if prefers-reduced-motion is set.

## Chapters

### 1. Overview
**Route:** `/docs/overview`

What Art Lounge's reordering challenge is, what the system does, key numbers (23K+ SKUs, 172 brands, 3 facilities, nightly sync). One-paragraph problem statement, one-paragraph solution, a "system at a glance" summary.

### 2. Data Sources
**Route:** `/docs/data-sources`

Sections:
- **Unicommerce overview** — what UC is, what role it plays (ERP/warehouse management)
- **The order lifecycle** — Sale Order → Picklist → Shipping Package → Invoice → Dispatch. What each entity means. Animated flow diagram.
- **Three facilities** — ppetpl (Bhiwandi main warehouse), PPETPLKALAGHODA (Kala Ghoda retail store), ALIBHIWANDI (stock counting only). What each does, why it matters.
- **The hybrid formula** — why we pull from 4 different API sources: Transaction Ledger (supply + BHW demand via PICKLIST), Shipping Package API (KG demand), Inventory Snapshot (current stock), Catalog (SKU master).
- **Why INVOICES are excluded** — the billing document bug (1x–144x inflated quantities). Show a concrete example: "UC says 1,728 units. Actual invoice shows 12. That's 144x."
- **Why KG uses Shipping Packages** — counter sales bypass PICKLIST. Only appear in Shipping Packages or (broken) INVOICES.
- **Nightly sync** — what happens every night: catalog pull → ledger per facility → KG shipping packages → inventory snapshots → pipeline computation → drift check → email.
- **Drift monitoring** — forward-walked stock vs snapshot comparison. 98.4% exact match rate. What causes drift (inventoryBlocked). What we do about it.

### 3. How We Calculate
**Route:** `/docs/calculations`

Sections:
- **Stock positions** — forward walk from Day 0. Each GRN adds stock, each PICKLIST removes. Current sellable stock from UC Inventory Snapshot (not forward walk). Brief example showing 5 transactions building a position.
- **Velocity** — units sold ÷ in-stock days × 30 = monthly velocity. Why we exclude out-of-stock days (prevents dilution). Monospace calculation block with real numbers.
- **Channel breakdown** — wholesale, online, store. How channels are classified (sale order prefix, facility rules). Total = sum of channels.
- **ABC classification** — top 80% revenue = A, next 15% = B, bottom 5% = C. Revenue = quantity × MRP from catalog.
- **XYZ classification** — demand variability. X = stable (CV < 0.5), Y = variable (0.5–1.0), Z = erratic (> 1.0).
- **Stockout projection** — stock ÷ daily velocity = days left. Edge cases: velocity=0 with stock → "no demand"; velocity=0 without stock → "out of stock".
- **Lead time & coverage** — lead time = days until shipment arrives (90d sea freight default). Coverage period = how long the order should last after arrival. Auto-calculated from turns-per-year.
- **Safety buffer** — multiplier on coverage demand (not lead time demand). ABC-based defaults. Why buffer is only on coverage: prevents double-buffering.
- **The reorder formula** — `demand_during_lead = velocity × lead_time` (no buffer) + `order_for_coverage = velocity × coverage_period × buffer` − `current_stock` = suggested qty. Monospace block showing the math with real numbers.

Interactive element: formula calculator. Enter stock, velocity, lead time, coverage, buffer → see suggested qty and status.

### 4. Understanding Statuses
**Route:** `/docs/statuses`

Sections:
- **The 7 statuses** — table with: status name, condition, color, what it means, what to do. One row per status.
- **Capital priority stack** — Lost Sales > Urgent > Reorder > Healthy > Dead Stock > Out of Stock > No Data. Why this ordering matters for working capital.
- **Status decision tree** — visual flowchart: "Is stock > 0?" → "Is velocity > 0?" → "Is days left < lead time?" → status. Lightly interactive: enter stock + velocity → highlights the path.
- **What to do for each** — brief action guidance per status. "Lost Sales: order immediately, you're bleeding revenue." "Healthy: keep ordering on your normal cycle."
- **Intent overrides** — must_stock, do_not_reorder. How they interact with calculated status.

### 5. Real SKU Walkthroughs
**Route:** `/docs/walkthroughs`

Each walkthrough structure:
1. **Profile card** — SKU name, part number, archetype label, 4 key stats (stock, velocity, days left, status)
2. **Flow diagram** — bird's-eye showing this SKU's journey through the system (which APIs, which facility, which channel)
3. **Transaction table** — actual UC transactions: date, type, order #, channel, qty in/out, running stock. Real data.
4. **Calculation blocks** — monospace step-by-step: velocity calc, stockout calc, reorder formula. Every number traceable.
5. **Verdict** — status badge, suggested qty, one-sentence plain English explanation.
6. **Callout boxes** — "Notice" linking to relevant concepts elsewhere in docs.

The 6 archetypes:
- **The Workhorse** — Koh-i-noor Eraser Pencil (6312). Wholesale-dominated, massive velocity, Urgent status. Teaches: high-volume wholesale flow, velocity calculation, why the suggested qty is large.
- **The Flash Seller** — W&N Varnish. Stocks out immediately after GRN, perpetual Lost Sales. Teaches: Lost Sales status, what happens when demand exceeds supply frequency.
- **The Store Bestseller** — KG retail-dominated SKU. Teaches: why KG uses Shipping Package API instead of PICKLIST, the store channel path.
- **The Online Mover** — Magento/marketplace-heavy SKU. Teaches: online channel classification (MAGENTO2, AMAZON_IN_API), spiky demand.
- **The Dead Stock Sitter** — stock on hand, zero velocity. Teaches: Dead Stock vs Out of Stock distinction, why having stock doesn't mean it's selling.
- **The Sporadic Item** — occasional bursts, low confidence velocity. Teaches: in-stock-days-only velocity, why low confidence matters, XYZ classification.

**Data sourcing:** All walkthrough data is hardcoded in the component files at build time. During implementation, query the live database to find representative SKUs for each archetype and extract their actual transaction history, velocity, and status. The data is then written into the TSX files as const arrays — no runtime API calls. This keeps the docs fast and independent of the API.

**Archetype identification:** SKU 6312 (Workhorse) and a W&N Varnish SKU (Flash Seller) are pre-identified. For the remaining 4, query during implementation:
- Store Bestseller: `SELECT * FROM sku_metrics WHERE store_velocity > wholesale_velocity AND current_stock > 0 ORDER BY store_velocity DESC LIMIT 5`
- Online Mover: `SELECT * FROM sku_metrics WHERE online_velocity > wholesale_velocity ORDER BY online_velocity DESC LIMIT 5`
- Dead Stock Sitter: `SELECT * FROM sku_metrics WHERE current_stock > 10 AND total_velocity = 0 LIMIT 5`
- Sporadic Item: `SELECT * FROM sku_metrics WHERE total_velocity > 0 AND total_velocity < 1 AND demand_cv > 1.0 LIMIT 5`

Pick the most illustrative from each query.

### 6. Using the Dashboard
**Route:** `/docs/dashboard-guide`

Page-by-page guide. For each page:
- What it shows
- Key actions you can take
- Tips / what to look for

Pages covered: Home, Brands, SKU Detail (expanded row + Calculation tab), Priority SKUs, Build PO, Dead Stock, Overrides, Suppliers, Parties, Settings.

### 7. Daily Workflows
**Route:** `/docs/workflows`

Procedural guides:
- **Morning check (5 min)** — open Home → check urgent count → scan Priority page → done.
- **Building a PO today** — go to brand → Build PO → review suggestions → adjust quantities → export Excel → send to supplier.
- **Monthly review** — check Dead Stock page → review overrides → check brand-level trends → tune supplier lead times if needed.
- **Tuning buffers & coverage** — when to increase buffer (critical items, long lead times), when to decrease (stable demand, fast resupply). How coverage period auto-calculates from turns-per-year.
- **Investigating anomalies** — stock doesn't match? Check drift log. Velocity seems wrong? Check in-stock days. Status doesn't make sense? Open Calculation tab.

### 8. System Architecture
**Route:** `/docs/architecture`

- **Data flow diagram** — static diagram showing: UC APIs → Nightly Sync → PostgreSQL → Pipeline → Dashboard.
- **4 API sources** — Transaction Ledger (Export Job API), Shipping Package (search API), Inventory Snapshot, Catalog. What each provides.
- **Sync schedule** — runs nightly at 10:30 PM IST via Railway cron.
- **Drift monitoring** — how forward-walked closing stock is compared to snapshot. What the numbers mean.
- **Known limitations** — INVOICES excluded (billing doc bug), KG PICKLIST incomplete (counter sales), Ali Bhiwandi is stock-counting only (no demand), inventoryBlocked causes drift.

### 9. Glossary
**Route:** `/docs/glossary`

Searchable A–Z. Key terms: ABC class, buffer, channel, coverage period, dead stock, drift, facility, forward walk, GRN, healthy, in-stock days, lead time, lost sales, out of stock, PICKLIST, reorder, shipping package, snapshot, stockout, transaction ledger, urgent, velocity, XYZ class.

## Shared Components

Create in `src/dashboard/src/pages/docs/components/`:

- **DocsLayout** — sidebar + content shell, light/dark toggle, mobile responsive
- **FormulaBlock** — monospace code-style block for showing calculations
- **TransactionTable** — styled table for UC transaction rows (date, type, order#, channel, qty, running stock)
- **FlowDiagram** — horizontal flow boxes with arrows (reusable for UC lifecycle, SKU journey, data pipeline)
- **CalloutBox** — colored info/warning/notice boxes with links
- **StatusTable** — the 7-status reference table with badges and colors
- **ProfileCard** — SKU archetype header with key stats
- **DocSection** — section wrapper with anchor ID for sidebar navigation
- **SearchableList** — for glossary filtering

## File Changes

| Action | File |
|--------|------|
| Create | `src/dashboard/src/pages/docs/Overview.tsx` |
| Create | `src/dashboard/src/pages/docs/DataSources.tsx` |
| Create | `src/dashboard/src/pages/docs/Calculations.tsx` |
| Create | `src/dashboard/src/pages/docs/Statuses.tsx` |
| Create | `src/dashboard/src/pages/docs/Walkthroughs.tsx` |
| Create | `src/dashboard/src/pages/docs/DashboardGuide.tsx` |
| Create | `src/dashboard/src/pages/docs/Workflows.tsx` |
| Create | `src/dashboard/src/pages/docs/Architecture.tsx` |
| Create | `src/dashboard/src/pages/docs/Glossary.tsx` |
| Create | `src/dashboard/src/pages/docs/components/DocsLayout.tsx` |
| Create | `src/dashboard/src/pages/docs/components/FormulaBlock.tsx` |
| Create | `src/dashboard/src/pages/docs/components/TransactionTable.tsx` |
| Create | `src/dashboard/src/pages/docs/components/FlowDiagram.tsx` |
| Create | `src/dashboard/src/pages/docs/components/CalloutBox.tsx` |
| Create | `src/dashboard/src/pages/docs/components/StatusTable.tsx` |
| Create | `src/dashboard/src/pages/docs/components/ProfileCard.tsx` |
| Create | `src/dashboard/src/pages/docs/components/DocSection.tsx` |
| Create | `src/dashboard/src/pages/docs/components/SearchableList.tsx` |
| Modify | `src/dashboard/src/App.tsx` — add `/docs/*` routes, no auth required |
| Modify | `src/dashboard/src/components/Layout.tsx` — Help nav → `/docs` |
| Modify | `src/dashboard/src/components/mobile/MobileLayout.tsx` — Help nav → `/docs` |
| Delete | `src/dashboard/src/pages/Help.tsx` |
| Delete | `src/dashboard/public/how-it-works.html` |
| Delete | `src/dashboard/public/reorder-logic-playground.html` |

## Writing Style

- Friendly, direct, conversational. Not corporate, not academic.
- Short paragraphs (2-3 sentences max).
- Tables and formula blocks over prose wherever possible.
- Every number should be traceable — if you say "138.4/mo", show the math that produces it.
- Callout boxes for digressions ("Why do we exclude INVOICES?") — keeps the main flow clean.
- No filler words, no "In this section we will discuss..."
- Use "you" and "we" naturally.
