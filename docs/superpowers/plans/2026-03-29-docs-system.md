# Documentation System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the outdated how-it-works.html and in-app Help page with a unified 9-chapter documentation system built as first-class React pages.

**Architecture:** React pages within the existing Vite/React/TypeScript dashboard app. Docs live at `/docs/*` routes outside `<ProtectedRoute />` (publicly accessible). Each chapter is a lazy-loaded page component. Shared doc components (FormulaBlock, TransactionTable, FlowDiagram, etc.) provide consistent styling. Editorial design with its own light/dark mode toggle.

**Tech Stack:** React 18, TypeScript, React Router 6 (nested routes + Outlet), Tailwind CSS, Lucide icons

**Spec:** `docs/superpowers/specs/2026-03-29-docs-system-design.md`

---

## File Map

### Shared Components (Task 1)
| File | Purpose |
|------|---------|
| `src/dashboard/src/pages/docs/components/DocsLayout.tsx` | Sidebar + content shell, light/dark toggle, mobile drawer |
| `src/dashboard/src/pages/docs/components/DocSection.tsx` | Section wrapper with anchor ID |
| `src/dashboard/src/pages/docs/components/FormulaBlock.tsx` | Monospace code-style calculation blocks |
| `src/dashboard/src/pages/docs/components/TransactionTable.tsx` | Styled UC transaction table |
| `src/dashboard/src/pages/docs/components/FlowDiagram.tsx` | Horizontal flow boxes with arrows |
| `src/dashboard/src/pages/docs/components/CalloutBox.tsx` | Info/warning/notice boxes with optional link |
| `src/dashboard/src/pages/docs/components/StatusTable.tsx` | 7-status reference table with badges |
| `src/dashboard/src/pages/docs/components/ProfileCard.tsx` | SKU archetype header card |
| `src/dashboard/src/pages/docs/components/SearchableList.tsx` | Filterable list for glossary |
| `src/dashboard/src/pages/docs/components/theme.css` | Docs-specific CSS variables for light/dark |

### Chapter Pages (Tasks 3–11)
| File | Chapter |
|------|---------|
| `src/dashboard/src/pages/docs/Overview.tsx` | 1. Overview |
| `src/dashboard/src/pages/docs/DataSources.tsx` | 2. Data Sources |
| `src/dashboard/src/pages/docs/Calculations.tsx` | 3. How We Calculate |
| `src/dashboard/src/pages/docs/Statuses.tsx` | 4. Understanding Statuses |
| `src/dashboard/src/pages/docs/Walkthroughs.tsx` | 5. Real SKU Walkthroughs |
| `src/dashboard/src/pages/docs/DashboardGuide.tsx` | 6. Using the Dashboard |
| `src/dashboard/src/pages/docs/Workflows.tsx` | 7. Daily Workflows |
| `src/dashboard/src/pages/docs/Architecture.tsx` | 8. System Architecture |
| `src/dashboard/src/pages/docs/Glossary.tsx` | 9. Glossary |

### Modified Files (Task 2)
| File | Change |
|------|--------|
| `src/dashboard/src/App.tsx` | Add `/docs/*` routes outside ProtectedRoute |
| `src/dashboard/src/components/Layout.tsx` | Change Help nav link to Docs → `/docs` |
| `src/dashboard/src/components/mobile/MobileLayout.tsx` | Change Help nav link to Docs → `/docs` |
| `src/dashboard/src/components/HelpMenu.tsx` | Update "How it works" link to `/docs` |

### Deleted Files (Task 12)
| File | Reason |
|------|--------|
| `src/dashboard/src/pages/Help.tsx` | Replaced by docs system |
| `src/dashboard/public/how-it-works.html` | Replaced by docs system |
| `src/dashboard/public/reorder-logic-playground.html` | Superseded by docs |

---

## Important Context for Implementers

### Writing Style
- **Crisp and friendly.** No walls of text. Short paragraphs (2-3 sentences max).
- **Tables and formula blocks over prose** wherever possible.
- **Every number traceable** — show the math that produces it.
- **Use "you" and "we"** naturally. No corporate or academic tone.
- **No filler** — no "In this section we will discuss..."

### Existing Patterns
- Dashboard uses `React.lazy()` for all page imports in App.tsx
- All pages are wrapped in `<SuspenseWrapper>` with a LoadingSkeleton fallback
- Navigation links are defined in `Layout.tsx` navGroups array and `MobileLayout.tsx`
- The app uses shadcn/ui components (Badge, Card, Table, etc.) and Tailwind CSS
- Use `py` for Python commands, PostgreSQL at `"/c/Program Files/PostgreSQL/17/bin/psql"`
- Run frontend dev: `cd src/dashboard && npm run dev`
- Build frontend: `cd src/dashboard && npm run build`

### Data for Walkthroughs
Walkthrough data is **hardcoded** in the component files. During Task 9, query the database to find representative SKUs and extract real transaction data, then embed as const arrays.

---

### Task 1: Shared Doc Components

**Files:**
- Create: `src/dashboard/src/pages/docs/components/theme.css`
- Create: `src/dashboard/src/pages/docs/components/DocsLayout.tsx`
- Create: `src/dashboard/src/pages/docs/components/DocSection.tsx`
- Create: `src/dashboard/src/pages/docs/components/FormulaBlock.tsx`
- Create: `src/dashboard/src/pages/docs/components/TransactionTable.tsx`
- Create: `src/dashboard/src/pages/docs/components/FlowDiagram.tsx`
- Create: `src/dashboard/src/pages/docs/components/CalloutBox.tsx`
- Create: `src/dashboard/src/pages/docs/components/StatusTable.tsx`
- Create: `src/dashboard/src/pages/docs/components/ProfileCard.tsx`
- Create: `src/dashboard/src/pages/docs/components/SearchableList.tsx`

This is the foundation. Every other task depends on these components.

- [ ] **Step 1: Create `theme.css`**

Docs-specific CSS variables for light/dark mode. Scoped under `.docs-light` and `.docs-dark` classes.

```css
/* Light/dark theme variables for docs pages */
.docs-light {
  --docs-bg: #fafaf9;
  --docs-bg-card: #ffffff;
  --docs-bg-code: #f5f5f4;
  --docs-text: #1c1917;
  --docs-text-secondary: #57534e;
  --docs-text-muted: #a8a29e;
  --docs-border: #e7e5e4;
  --docs-accent: #d97706;
  --docs-accent-dim: #92400e;
  --docs-link: #2563eb;
  --docs-sidebar-bg: #ffffff;
  --docs-sidebar-active: #fef3c7;
}

.docs-dark {
  --docs-bg: #0c1015;
  --docs-bg-card: #19222d;
  --docs-bg-code: #111820;
  --docs-text: #e8e2d6;
  --docs-text-secondary: #9aa8b8;
  --docs-text-muted: #5e7080;
  --docs-border: #253344;
  --docs-accent: #f0a500;
  --docs-accent-dim: #c48800;
  --docs-link: #60a5fa;
  --docs-sidebar-bg: #111820;
  --docs-sidebar-active: rgba(240, 165, 0, 0.1);
}
```

- [ ] **Step 2: Create `DocsLayout.tsx`**

Import `theme.css` at the top of this file: `import './theme.css'`

The shell component. Renders sidebar + content area via `<Outlet />`. Features:
- Light/dark mode toggle stored in `localStorage` key `docs-theme`, defaults to `light`
- Sidebar with chapter list and section links within each chapter
- Scroll spy: highlights current section in sidebar based on scroll position (IntersectionObserver on DocSection elements)
- Mobile: sidebar hidden by default, toggled via hamburger button, slides in as a left drawer
- "Back to Dashboard" link at top of sidebar
- `/docs` base route redirects to `/docs/overview` via `<Navigate />`

The sidebar data structure should be a const array defining chapters with their routes and sub-sections:

```typescript
const DOCS_NAV = [
  { title: 'Overview', path: '/docs/overview', sections: [] },
  { title: 'Data Sources', path: '/docs/data-sources', sections: [
    { id: 'unicommerce', label: 'Unicommerce' },
    { id: 'order-lifecycle', label: 'Order Lifecycle' },
    { id: 'facilities', label: 'Three Facilities' },
    { id: 'hybrid-formula', label: 'Hybrid Formula' },
    { id: 'invoices-bug', label: 'Why INVOICES Excluded' },
    { id: 'kg-shipping', label: 'KG Shipping Packages' },
    { id: 'nightly-sync', label: 'Nightly Sync' },
    { id: 'drift', label: 'Drift Monitoring' },
  ]},
  // ... etc for all 9 chapters
]
```

Chapter links use `<NavLink>` for active state. Section links use `<a href="#section-id">` for scroll-to behavior.

Prev/Next navigation at bottom of content area: links to previous and next chapter.

- [ ] **Step 3: Create `DocSection.tsx`**

Simple wrapper that adds an `id` for anchor linking and registers with IntersectionObserver for scroll spy.

```typescript
interface DocSectionProps {
  id: string
  title?: string
  children: React.ReactNode
}
```

Renders a `<section id={id}>` with optional `<h2>` title. The IntersectionObserver callback calls a context function to update the active section in the sidebar.

- [ ] **Step 4: Create `FormulaBlock.tsx`**

Monospace block for showing calculations. Dark background in light mode, slightly lighter in dark mode.

```typescript
interface FormulaBlockProps {
  children: React.ReactNode
  caption?: string
}
```

Renders a `<pre>` styled block with monospace font, slight padding, rounded corners, and optional caption below.

- [ ] **Step 5: Create `TransactionTable.tsx`**

Reusable table for showing UC transaction rows in walkthroughs.

```typescript
interface Transaction {
  date: string
  type: string
  orderNumber: string
  channel: string
  qty: number  // positive = in, negative = out
  runningStock: number
}

interface TransactionTableProps {
  transactions: Transaction[]
  caption?: string
}
```

Renders a styled table with columns: Date, Type, Order #, Channel, Qty (green for positive, red for negative), Running Stock. Type column uses friendly labels (GRN → "Purchase Received", PICKLIST → "Picked for Order").

- [ ] **Step 6: Create `FlowDiagram.tsx`**

Horizontal flow of boxes connected by arrows. Used for UC lifecycle, SKU journey, data pipeline.

```typescript
interface FlowNode {
  icon?: string  // emoji or lucide icon name
  title: string
  subtitle?: string
  color: string  // tailwind color like 'teal' | 'amber' | 'red' | 'purple'
}

interface FlowDiagramProps {
  nodes: FlowNode[]
  animated?: boolean  // CSS-animated dots along connecting lines
}
```

Renders horizontally on desktop, wraps/stacks on mobile. If `animated`, uses CSS keyframes to animate dots along the connecting lines. Respects `prefers-reduced-motion`.

- [ ] **Step 7: Create `CalloutBox.tsx`**

Info/warning/notice boxes.

```typescript
interface CalloutBoxProps {
  type: 'info' | 'warning' | 'notice'
  title?: string
  linkTo?: string
  linkText?: string
  children: React.ReactNode
}
```

Colors: info = blue, warning = amber, notice = gold/accent. Optional `<Link>` at the end.

- [ ] **Step 8: Create `StatusTable.tsx`, `ProfileCard.tsx`, `SearchableList.tsx`**

**StatusTable:** Renders the 7-status reference table with badge colors, conditions, meanings, and actions. Hardcoded data — no props needed beyond an optional `compact` boolean.

**ProfileCard:** SKU archetype header.
```typescript
interface ProfileCardProps {
  name: string
  partNo: string
  archetype: string
  archetypeDescription: string
  stats: { label: string; value: string; color?: string }[]
}
```

**SearchableList:** Input + filtered list for glossary.
```typescript
interface GlossaryEntry { term: string; definition: string }
interface SearchableListProps { entries: GlossaryEntry[] }
```

- [ ] **Step 9: Build and verify components render**

Create a minimal `Overview.tsx` placeholder that imports and renders a few components to verify everything works:

```bash
cd src/dashboard && npm run build 2>&1 | tail -5
```

Expected: Clean build.

- [ ] **Step 10: Commit**

```bash
git add src/dashboard/src/pages/docs/
git commit -m "feat: add shared docs components (DocsLayout, FormulaBlock, TransactionTable, etc.)"
```

---

### Task 2: Routing & Navigation Integration

**Files:**
- Modify: `src/dashboard/src/App.tsx`
- Modify: `src/dashboard/src/components/Layout.tsx`
- Modify: `src/dashboard/src/components/mobile/MobileLayout.tsx`
- Modify: `src/dashboard/src/components/HelpMenu.tsx`

- [ ] **Step 1: Add docs routes to App.tsx**

Add `/docs/*` routes OUTSIDE the `<ProtectedRoute />` wrapper, at the same level as `/login`:

```typescript
const DocsLayout = lazy(() => import('./pages/docs/components/DocsLayout'))
const DocsOverview = lazy(() => import('./pages/docs/Overview'))
// ... lazy imports for all 9 chapter pages

<Routes>
  <Route path="/login" element={...} />

  {/* Docs — public, no auth */}
  <Route path="/docs" element={<SuspenseWrapper><DocsLayout /></SuspenseWrapper>}>
    <Route index element={<Navigate to="/docs/overview" replace />} />
    <Route path="overview" element={<SuspenseWrapper><DocsOverview /></SuspenseWrapper>} />
    <Route path="data-sources" element={<SuspenseWrapper><DocsDataSources /></SuspenseWrapper>} />
    <Route path="calculations" element={<SuspenseWrapper><DocsCalculations /></SuspenseWrapper>} />
    <Route path="statuses" element={<SuspenseWrapper><DocsStatuses /></SuspenseWrapper>} />
    <Route path="walkthroughs" element={<SuspenseWrapper><DocsWalkthroughs /></SuspenseWrapper>} />
    <Route path="dashboard-guide" element={<SuspenseWrapper><DocsDashboardGuide /></SuspenseWrapper>} />
    <Route path="workflows" element={<SuspenseWrapper><DocsWorkflows /></SuspenseWrapper>} />
    <Route path="architecture" element={<SuspenseWrapper><DocsArchitecture /></SuspenseWrapper>} />
    <Route path="glossary" element={<SuspenseWrapper><DocsGlossary /></SuspenseWrapper>} />
    <Route path="*" element={<Navigate to="/docs/overview" replace />} />
  </Route>

  <Route element={<ProtectedRoute />}>
    {/* ... existing dashboard routes */}
  </Route>
</Routes>
```

For now, create stub pages (just `<div>Chapter coming soon</div>`) for chapters not yet implemented so routes don't break.

- [ ] **Step 2: Update Layout.tsx nav**

In `Layout.tsx`, add a "Docs" link. The simplest approach: add it to the HelpMenu component or as a standalone nav link. Since the user wants it in the nav bar, add to the end of the nav links (visible to all roles):

Find the HelpMenu reference and add a direct link near it, or add "Docs" to the nav groups.

- [ ] **Step 3: Update MobileLayout.tsx**

Add "Docs" link to mobile navigation.

- [ ] **Step 4: Update HelpMenu.tsx**

Change "How it works" link from the old URL to `/docs`.

- [ ] **Step 5: Build and test**

```bash
cd src/dashboard && npm run build 2>&1 | tail -5
```

Verify: Navigate to `/docs` → redirects to `/docs/overview`. Navigate to `/docs/nonexistent` → redirects to `/docs/overview`. Sidebar renders with all chapter links.

- [ ] **Step 6: Commit**

```bash
git add src/dashboard/src/App.tsx src/dashboard/src/components/Layout.tsx src/dashboard/src/components/mobile/MobileLayout.tsx src/dashboard/src/components/HelpMenu.tsx src/dashboard/src/pages/docs/
git commit -m "feat: add docs routing and navigation integration"
```

---

### Task 3: Chapter 1 — Overview

**Files:**
- Create: `src/dashboard/src/pages/docs/Overview.tsx`

- [ ] **Step 1: Write the Overview page**

Content:
- **Problem** (2-3 sentences): Art Lounge imports art supplies in bulk with 3-6 month lead times, sells via wholesale + online + retail. Predicting when to reorder 23K+ SKUs across 172 brands is the challenge.
- **Solution** (2-3 sentences): System pulls data from Unicommerce nightly, calculates velocity per channel, projects stockout dates, and recommends reorder quantities with safety buffers.
- **System at a glance** — use a FlowDiagram showing: Unicommerce → Nightly Sync → Calculations → Dashboard → Purchase Orders
- **Key numbers** — small grid of stat cards: 23K+ SKUs, 172 Brands, 3 Facilities, Nightly Sync, 7 Statuses, 98.4% Accuracy

- [ ] **Step 2: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/docs/Overview.tsx
git commit -m "feat: add docs Chapter 1 — Overview"
```

---

### Task 4: Chapter 2 — Data Sources

**Files:**
- Create: `src/dashboard/src/pages/docs/DataSources.tsx`

This is the most content-heavy chapter. Sections use DocSection with anchor IDs.

- [ ] **Step 1: Write sections: UC overview, order lifecycle, facilities**

- **Unicommerce overview**: 2-3 sentences on what UC is (ERP + warehouse management for Art Lounge).
- **Order lifecycle**: FlowDiagram showing Sale Order → Picklist → Shipping Package → Invoice → Dispatch. Brief (1 sentence each) explanation of what each entity means.
- **Three facilities**: Simple table — facility code, name, what it does. ppetpl = Bhiwandi main warehouse (wholesale + online fulfillment). PPETPLKALAGHODA = Kala Ghoda retail store. ALIBHIWANDI = Art Lounge Bhiwandi (stock counting only, no commerce).

- [ ] **Step 2: Write sections: hybrid formula, INVOICES bug, KG shipping**

- **Hybrid formula**: Table showing 4 data sources and what each provides: Transaction Ledger API (supply + BHW demand via PICKLIST), Shipping Package API (KG demand), Inventory Snapshot (current stock), Catalog (SKU master + MRP). Use a CalloutBox explaining why we need 4 sources instead of 1.
- **Why INVOICES excluded**: The billing document bug. Show the concrete example in a small table: "UC Ledger says 1,728 units. Actual UC invoice says 12. That's 144x inflation." CalloutBox with the explanation: invoices are billing documents with packed quantities, not individual unit counts.
- **KG Shipping Packages**: Why Kala Ghoda counter sales (CUSTOM_SHOP channel) don't generate PICKLIST entries — they only appear as Shipping Packages. So for KG, we pull from the Shipping Package API instead.

- [ ] **Step 3: Write sections: nightly sync, drift monitoring**

- **Nightly sync**: FlowDiagram showing the sync steps: Catalog → Ledger (per facility) → KG Shipping Packages → Inventory Snapshots → Pipeline Computation → Drift Check → Email. One sentence per step.
- **Drift monitoring**: What drift is (forward-walked stock vs UC snapshot mismatch). Key stat: 98.4% exact match across 23K SKUs. What causes the 1.6% drift: mostly `inventoryBlocked` (items picked but not yet shipped). FormulaBlock showing: `drift = forward_walk_closing − (inventory + blocked + bad)`.

- [ ] **Step 4: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/src/pages/docs/DataSources.tsx
git commit -m "feat: add docs Chapter 2 — Data Sources"
```

---

### Task 5: Chapter 3 — How We Calculate

**Files:**
- Create: `src/dashboard/src/pages/docs/Calculations.tsx`

- [ ] **Step 1: Write sections: positions, velocity, channels**

- **Stock positions**: Forward walk from Day 0. Show a 5-row TransactionTable building a position: GRN +50, PICKLIST -12, PICKLIST -8, GRN +20, PICKLIST -15 → closing 35. CalloutBox: current sellable stock comes from UC Inventory Snapshot, not the forward walk. Forward walk is for history/velocity.
- **Velocity**: FormulaBlock: `units_sold ÷ in_stock_days × 30 = monthly_velocity`. Worked example: 1,246 units ÷ 270 days × 30 = 138.4/mo. CalloutBox: why we exclude out-of-stock days (prevents velocity dilution — if item was out of stock 3 months, counting those days would halve the real demand signal).
- **Channel breakdown**: Table showing how channels are determined. Wholesale = sale order prefix patterns + Sundry Debtors. Online = MAGENTO2, AMAZON_IN_API, Sales-Flipkart, Sales-Amazon. Store = Kala Ghoda Shipping Packages with CUSTOM_SHOP channel. Total = wholesale + online + store.

- [ ] **Step 2: Write sections: ABC/XYZ, stockout, lead time, buffer**

- **ABC**: Top 80% revenue = A, next 15% = B, bottom 5% = C. Revenue = quantity × MRP from catalog.
- **XYZ**: Coefficient of variation. X (CV < 0.5) = stable demand, Y (0.5–1.0) = variable, Z (> 1.0) = erratic.
- **Stockout projection**: FormulaBlock: `days_left = current_stock ÷ daily_velocity`. Edge cases table: velocity=0 + stock>0 → no demand (Dead Stock), velocity=0 + stock=0 → unknown (Out of Stock), velocity>0 + stock=0 → Lost Sales.
- **Lead time & coverage**: Lead time = days from order to arrival (default 90d for sea freight). Coverage = how long the order should last after arrival. Auto-calculated from turns per year: `turns = min(max(1, 365 ÷ lead_time), 6)`, `coverage = 365 ÷ turns`.
- **Safety buffer**: Multiplier on coverage demand ONLY (not lead time). Default 1.3x. ABC-based: A=1.3, B=1.2, C=1.1. CalloutBox: why buffer is only on coverage — applying to lead time would double-buffer, inflating orders.

- [ ] **Step 3: Write section: the reorder formula + interactive calculator**

- **The reorder formula**: FormulaBlock showing:
  ```
  demand_during_lead  = velocity × lead_time           (no buffer)
  order_for_coverage  = velocity × coverage × buffer   (buffer here only)
  suggested_qty       = demand_lead + order_coverage − current_stock
  ```
  Worked example with real numbers from SKU 6312.

- **Formula calculator**: 5 input fields (stock, velocity/day, lead time days, coverage days, buffer multiplier) + computed output (suggested qty, days to stockout, resulting status). Pure React state — onChange handlers compute results immediately. Show the formula steps as they compute.

- [ ] **Step 4: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/src/pages/docs/Calculations.tsx
git commit -m "feat: add docs Chapter 3 — How We Calculate"
```

---

### Task 6: Chapter 4 — Understanding Statuses

**Files:**
- Create: `src/dashboard/src/pages/docs/Statuses.tsx`

- [ ] **Step 1: Write sections: status table, priority stack, actions**

- **The 7 statuses**: Use StatusTable component. Columns: Priority #, Status (with colored badge), Condition, What It Means, What To Do. Ordered by capital priority.
- **Capital priority stack**: Visual numbered list 1-7 with colors. Brief explanation: "When capital is limited, fund Lost Sales first — you're already losing money. Then Urgent — prevent the next bleed. Then Reorder — keep the pipeline flowing."
- **What to do for each**: Brief action table. One row per status, 1-2 sentences each. E.g., "Lost Sales — Order immediately. Proven demand, zero stock. Every day costs revenue." "Healthy — No rush. Include in next regular PO cycle."

- [ ] **Step 2: Write sections: decision tree, intent overrides**

- **Status decision tree**: Static SVG/CSS flowchart. Start: "Stock > 0?" → Yes/No branches. Each branch: "Velocity > 0?" → further branches leading to status badges. On hover/click of a status node, highlight the path from root. CSS transitions, no animation library.
- **Intent overrides**: Brief explanation of must_stock (forces minimum Reorder status + fallback qty even with zero velocity) and do_not_reorder (shows calculated status but suppresses suggested qty).

- [ ] **Step 3: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/pages/docs/Statuses.tsx
git commit -m "feat: add docs Chapter 4 — Understanding Statuses"
```

---

### Task 7: Chapter 5 — Real SKU Walkthroughs (Data Gathering)

**Files:**
- No files created yet — this task gathers the data

**Important:** The local database has Tally-era schema. The UC-era schema (with `entity`, `entity_type`, `stock_change`, `facility` columns on `transactions`) only exists on **Railway**. Run these queries against Railway's database, or use the Railway CLI / dashboard to execute them. Alternatively, use the dashboard API to pull data for specific SKUs.

Also note: `store_velocity` is NOT a column in `sku_metrics` — it's derived at query time. Use `(total_velocity - wholesale_velocity - online_velocity)` as a proxy, or query the API.

- [ ] **Step 1: Find archetype SKUs via the dashboard API**

Use curl against the Railway API to find representative SKUs:

```bash
# The Workhorse — already known: SKU 6312 (Koh-i-noor Eraser Pencil)

# The Flash Seller — W&N Varnish
curl -s "https://reorder.artlounge.in/api/brands/WINSOR%20%26%20NEWTON/skus?search=varnish&sort=total_velocity&sort_dir=desc" \
  -H "Authorization: Bearer <token>" | python -m json.tool | head -30

# Store Bestseller — browse KG-heavy items via the dashboard at reorder.artlounge.in

# Online Mover — browse online-heavy items via the dashboard

# Dead Stock Sitter — use the Dead Stock page filter

# Sporadic Item — look for low velocity + high CV items
```

Alternatively, open the dashboard in Chrome and browse the brand/SKU pages to find good examples. The implementer should pick 1 SKU per archetype that clearly illustrates the pattern.

- [ ] **Step 2: Pull transaction history for each chosen SKU**

For each archetype SKU, use the dashboard API to get transactions:

```bash
curl -s "https://reorder.artlounge.in/api/brands/<BRAND>/skus/<SKU>/transactions" \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

Also get the SKU's calculation breakdown:

```bash
curl -s "https://reorder.artlounge.in/api/brands/<BRAND>/skus/<SKU>/breakdown" \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

Extract: key metrics (stock, velocity, days left, status), 10-15 representative transactions, and the full calculation chain.

- [ ] **Step 3: Hardcode the data**

Write the extracted data as TypeScript const arrays in the Walkthroughs.tsx file (next task). Each archetype gets its own data object with metrics + transactions. No runtime API calls — this is documentation, not a live view.

No commit for this task — it's a data-gathering step.

---

### Task 8: Chapter 5 — Real SKU Walkthroughs (Implementation)

**Files:**
- Create: `src/dashboard/src/pages/docs/Walkthroughs.tsx`

- [ ] **Step 1: Write the Workhorse walkthrough (6312)**

Use the data gathered in Task 7. Structure:
1. ProfileCard with archetype label, key stats
2. FlowDiagram: UC Ledger → Positions → Velocity → Stockout → Status
3. TransactionTable with ~10 real transactions
4. FormulaBlock: velocity calculation step by step
5. FormulaBlock: stockout + reorder formula
6. Verdict: status badge + suggested qty + one-sentence explanation
7. CalloutBox linking to relevant concepts

- [ ] **Step 2: Write the Flash Seller walkthrough (W&N Varnish)**

Same structure. Emphasize: GRN comes in → sells out fast → Lost Sales status. Show the pattern of stock spikes and immediate depletion in the transaction table.

- [ ] **Step 3: Write remaining 4 walkthroughs**

- Store Bestseller: emphasize KG Shipping Package data path
- Online Mover: emphasize online channel dominance
- Dead Stock Sitter: emphasize zero velocity with stock on hand
- Sporadic Item: emphasize high CV, low confidence

Each follows the same structure but can be more concise — the first two walkthroughs teach the structure, the remaining four just show different profiles.

- [ ] **Step 4: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/src/pages/docs/Walkthroughs.tsx
git commit -m "feat: add docs Chapter 5 — Real SKU Walkthroughs with 6 archetypes"
```

---

### Task 9: Chapter 6 — Using the Dashboard

**Files:**
- Create: `src/dashboard/src/pages/docs/DashboardGuide.tsx`

- [ ] **Step 1: Write page guides**

For each dashboard page, write a brief guide (3-5 bullet points):
- **Home**: command center. Urgent count, priority brands table, quick actions.
- **Brands**: all brands sorted by urgency. Click to drill into SKUs. Filter by name.
- **SKU Detail**: expand a row to see velocity breakdown, stock timeline, transactions. Calculation tab shows full formula walkthrough.
- **Priority SKUs**: triage view. IMMEDIATE/URGENT/WATCH tiers. Filter by status, ABC class.
- **Build PO**: select brand → review suggestions → adjust qtys → export Excel. Custom date ranges for velocity.
- **Dead Stock**: items with stock but no sales. Review and mark as do-not-reorder if appropriate.
- **Overrides**: manually adjust stock or velocity when you know better than the formula. Stale detection warns when overrides drift from reality.
- **Suppliers**: set lead times per brand. Sea vs air freight. Coverage period tuning.
- **Parties**: channel classification rules. How parties map to wholesale/online/store/supplier channels.
- **Settings**: analysis period, buffer mode (ABC only vs ABC×XYZ), velocity type default.

- [ ] **Step 2: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/docs/DashboardGuide.tsx
git commit -m "feat: add docs Chapter 6 — Using the Dashboard"
```

---

### Task 10: Chapter 7 — Daily Workflows

**Files:**
- Create: `src/dashboard/src/pages/docs/Workflows.tsx`

- [ ] **Step 1: Write workflow guides**

Procedural, numbered steps:
- **Morning check (5 min)**: 1. Open Home. 2. Check urgent count — any increase? 3. Scan Priority page for IMMEDIATE tier. 4. Done.
- **Building a PO today**: 1. Go to brand page. 2. Click Build PO. 3. Review suggested quantities. 4. Adjust if needed (overrides, manual edits). 5. Export Excel. 6. Email to supplier.
- **Monthly review**: 1. Check Dead Stock page — anything to liquidate? 2. Review overrides — any stale? 3. Brand overview — trends changing? 4. Suppliers page — lead times still accurate?
- **Tuning buffers & coverage**: When to increase (unreliable supplier, long transit, critical items). When to decrease (fast resupply, stable demand). How coverage auto-calculates from turns.
- **Investigating anomalies**: Stock mismatch → check drift. Velocity wrong → check in-stock days. Status confusing → open Calculation tab.

- [ ] **Step 2: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/docs/Workflows.tsx
git commit -m "feat: add docs Chapter 7 — Daily Workflows"
```

---

### Task 11: Chapter 8 — System Architecture

**Files:**
- Create: `src/dashboard/src/pages/docs/Architecture.tsx`

- [ ] **Step 1: Write architecture page**

- **Data flow diagram**: FlowDiagram showing: UC APIs (4 boxes: Ledger, SP, Snapshot, Catalog) → Nightly Sync (Railway cron) → PostgreSQL → Computation Pipeline → Dashboard (React app).
- **4 API sources**: Table — API name, endpoint, what it provides, frequency.
- **Sync schedule**: Runs nightly at 10:30 PM IST (0 22 * * * UTC). Railway cron service with MODE=sync.
- **Known limitations**: Bullet list — INVOICES excluded, KG PICKLIST incomplete, Ali Bhiwandi stock-counting only, inventoryBlocked causes drift, Export Job API occasionally slow.

- [ ] **Step 2: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/docs/Architecture.tsx
git commit -m "feat: add docs Chapter 8 — System Architecture"
```

---

### Task 12: Chapter 9 — Glossary

**Files:**
- Create: `src/dashboard/src/pages/docs/Glossary.tsx`

- [ ] **Step 1: Write glossary**

Use SearchableList component. Define ~25 terms as a const array:

ABC Class, Buffer (Safety), Channel, Coverage Period, Dead Stock, Drift, Facility, Forward Walk, GRN, Healthy, In-Stock Days, Lead Time, Lost Sales, No Data, Out of Stock, PICKLIST, Reorder, Shipping Package, Snapshot, Stockout, Transaction Ledger, Unicommerce, Urgent, Velocity, XYZ Class.

Each entry: term + 1-2 sentence definition. Link to relevant docs section where applicable.

- [ ] **Step 2: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/docs/Glossary.tsx
git commit -m "feat: add docs Chapter 9 — Glossary"
```

---

### Task 13: Cleanup & Final Integration

**Files:**
- Delete: `src/dashboard/src/pages/Help.tsx`
- Delete: `src/dashboard/public/how-it-works.html`
- Delete: `src/dashboard/public/reorder-logic-playground.html`

- [ ] **Step 1: Remove old files**

Delete the three files. Remove the `Help` lazy import and `/help` route from App.tsx. Remove any references to `how-it-works.html` in HelpMenu or elsewhere.

- [ ] **Step 2: Full build**

```bash
cd src/dashboard && npm run build 2>&1
```

Must be zero errors.

- [ ] **Step 3: Test all docs routes**

Verify manually or with curl that these all load:
- `/docs` → redirects to `/docs/overview`
- `/docs/overview` through `/docs/glossary` → each renders content
- `/docs/nonexistent` → redirects to `/docs/overview`
- Sidebar navigation works between chapters
- Light/dark mode toggle works
- Mobile: sidebar drawer opens/closes

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: remove old Help page and how-it-works.html, finalize docs system"
```

---

### Task 14: Push and Deploy

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

- [ ] **Step 2: Verify on Railway**

After deploy (~2 min), verify at `https://reorder.artlounge.in/docs`:
- Docs load without login
- All 9 chapters render
- Sidebar navigation works
- Light/dark mode toggle works
- "Docs" link in dashboard nav works (when logged in)
