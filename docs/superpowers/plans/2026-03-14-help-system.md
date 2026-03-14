# Help System & Onboarding Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a three-layer help system (guided tour, contextual tooltips, help page) so the Art Lounge team can learn and use the Stock Intelligence dashboard without external training.

**Architecture:** Three interconnected layers sharing consistent terminology. A `HelpTip` component provides contextual tooltips with "Learn more" links to the `/help` page. A `GuidedTour` component runs an 18-step walkthrough on first visit. A `HelpMenu` in the header provides access to both.

**Tech Stack:** React 19, TypeScript, shadcn/ui (Popover), react-joyride, Tailwind CSS, React Router 7

**Spec:** `docs/superpowers/specs/2026-03-14-help-system-design.md`

---

## Chunk 1: Foundation Components

### Task 1: Install Dependencies

**Files:**
- Modify: `src/dashboard/package.json`

- [ ] **Step 1: Install shadcn Popover component**

```bash
cd src/dashboard && npx shadcn@latest add popover
```

Expected: Creates `src/dashboard/src/components/ui/popover.tsx`

- [ ] **Step 2: Install react-joyride**

```bash
cd src/dashboard && npm install react-joyride
```

- [ ] **Step 3: Verify installation**

```bash
cd src/dashboard && npx tsc --noEmit
```

Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/package.json src/dashboard/package-lock.json src/dashboard/src/components/ui/popover.tsx
git commit -m "feat: add popover component and react-joyride for help system"
```

---

### Task 2: HelpTip Component

**Files:**
- Create: `src/dashboard/src/components/HelpTip.tsx`

- [ ] **Step 1: Create HelpTip component**

```tsx
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Info } from 'lucide-react'
import { Link } from 'react-router-dom'

interface HelpTipProps {
  tip: string
  helpAnchor?: string
}

export default function HelpTip({ tip, helpAnchor }: HelpTipProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center justify-center h-4 w-4 rounded-full text-muted-foreground/60 hover:text-muted-foreground transition-colors"
          aria-label="More info"
        >
          <Info className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72 text-sm" side="top" align="start">
        <p className="text-muted-foreground leading-relaxed">{tip}</p>
        {helpAnchor && (
          <Link
            to={`/help#${helpAnchor}`}
            className="inline-block mt-2 text-xs font-medium text-primary hover:underline"
          >
            Learn more &rarr;
          </Link>
        )}
      </PopoverContent>
    </Popover>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd src/dashboard && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/HelpTip.tsx
git commit -m "feat: add HelpTip contextual tooltip component"
```

---

### Task 3: HelpMenu Component

**Files:**
- Create: `src/dashboard/src/components/HelpMenu.tsx`

The header "?" button with dropdown for "Help Guide" and "Replay Tour".

- [ ] **Step 1: Create HelpMenu component**

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { HelpCircle, BookOpen, Play } from 'lucide-react'

interface HelpMenuProps {
  onReplayTour: () => void
}

export default function HelpMenu({ onReplayTour }: HelpMenuProps) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
          aria-label="Help"
        >
          <HelpCircle className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-48 p-1" align="end">
        <button
          className="flex items-center gap-2 w-full rounded px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
          onClick={() => {
            setOpen(false)
            navigate('/help')
          }}
        >
          <BookOpen className="h-4 w-4 text-muted-foreground" />
          Help Guide
        </button>
        <button
          className="flex items-center gap-2 w-full rounded px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
          onClick={() => {
            setOpen(false)
            onReplayTour()
          }}
        >
          <Play className="h-4 w-4 text-muted-foreground" />
          Replay Tour
        </button>
      </PopoverContent>
    </Popover>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd src/dashboard && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/HelpMenu.tsx
git commit -m "feat: add HelpMenu dropdown component"
```

---

## Chunk 2: Help Guide Page

### Task 4: Help Page

**Files:**
- Create: `src/dashboard/src/pages/Help.tsx`
- Modify: `src/dashboard/src/App.tsx` (add route)

This is the largest single file — the full reference manual. Reuses the Settings page sidebar + scroll-spy pattern.

- [ ] **Step 1: Create Help page with sidebar navigation and all content sections**

Create `src/dashboard/src/pages/Help.tsx`. This is a long file with all the help content. The structure follows the Settings.tsx pattern:
- `HELP_SECTIONS` array with id/label/icon
- `activeSection` state with scroll-spy via `getBoundingClientRect`
- Left sidebar nav (fixed) + right scrollable content
- Each section has an `id` attribute matching the sidebar for deep-linking from tooltips

Content sections (matching spec):
1. **getting-started** — What the tool does, data source, who it's for
2. **three-channels** — Parallel demand tracks explanation (wholesale/online/store)
3. **velocity** — Sell-through rate, in-stock days, flat vs WMA, trend
4. **abc-classification** — A/B/C revenue tiers, priority implications
5. **lead-time-buffer** — Lead time, safety buffer, ABC buffer multipliers
6. **stockout-projection** — Days remaining formula, status thresholds
7. **reorder-quantity** — Reorder formula, PO Builder connection
8. **overrides** — When to override, staleness, drift
9. **channel-classification** — Party classification, impact on velocity
10. **page-home** — Home page guide
11. **page-brands** — Brands page guide
12. **page-sku-detail** — SKU Detail page guide
13. **page-critical** — Critical SKUs page guide
14. **page-po-builder** — PO Builder page guide
15. **page-dead-stock** — Dead Stock page guide
16. **page-parties** — Parties page guide
17. **page-suppliers** — Suppliers page guide
18. **page-overrides** — Overrides page guide
19. **page-settings** — Settings page guide
20. **workflow-morning** — Morning check workflow
21. **workflow-deep-dive** — SKU investigation workflow
22. **workflow-monthly** — Monthly housekeeping workflow
23. **workflow-setup** — New party classification workflow
24. **glossary** — Alphabetical term reference

The sidebar groups these into 5 top-level sections: Getting Started, Key Concepts, Page Guides, Daily Workflows, Glossary. Each sidebar item scrolls to its section.

Full prose content comes from the spec's Key Concepts section (2.1-2.8), expanded Page-by-Page Guides, Workflows, and Glossary.

**Important implementation notes:**
- Sidebar icons: `Rocket` (getting started), `Lightbulb` (concepts), `Layout` (pages), `CalendarCheck` (workflows), `BookOpen` (glossary)
- Use `useEffect` with scroll event listener on content container (same as Settings.tsx)
- On mount, check `window.location.hash` and scroll to that section (for deep-links from HelpTip)
- Each section uses `<h2>` for section title, `<h3>` for subsections
- Use Tailwind prose-like styling: `text-sm leading-relaxed text-muted-foreground` for body text, `font-semibold text-foreground` for headings

- [ ] **Step 2: Add route to App.tsx**

In `src/dashboard/src/App.tsx`, add the lazy import and route:

```tsx
// Add with other lazy imports at the top
const Help = lazy(() => import('./pages/Help'))

// Add inside the <Route element={<Layout />}> block, after the last route
<Route path="/help" element={<SuspenseWrapper><Help /></SuspenseWrapper>} />
```

- [ ] **Step 3: Verify build**

```bash
cd src/dashboard && npx tsc --noEmit
```

- [ ] **Step 4: Test locally**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000
```

Open `http://localhost:5173/help` — verify sidebar nav works, scroll-spy highlights correct section, deep-link anchors work (try `/help#velocity`).

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/src/pages/Help.tsx src/dashboard/src/App.tsx
git commit -m "feat: add Help guide page with full reference content"
```

---

## Chunk 3: Guided Tour

### Task 5: GuidedTour Component

**Files:**
- Create: `src/dashboard/src/components/GuidedTour.tsx`
- Create: `src/dashboard/src/lib/tour-steps.ts` (step definitions separated from component)

Split into two files: step definitions (data) and tour component (logic).

- [ ] **Step 1: Create tour step definitions**

Create `src/dashboard/src/lib/tour-steps.ts`:

```tsx
import type { Step } from 'react-joyride'

// Route each step group maps to
export const TOUR_ROUTES: Record<string, string> = {
  home: '/',
  brands: '/brands',
  skuDetail: '/brands/WINSOR%20%26%20NEWTON/skus',
  poBuilder: '/brands/WINSOR%20%26%20NEWTON/po',
}

// Step ranges for each route
export const STEP_ROUTE_MAP: { start: number; end: number; route: string }[] = [
  { start: 0, end: 4, route: TOUR_ROUTES.home },
  { start: 5, end: 7, route: TOUR_ROUTES.brands },
  { start: 8, end: 13, route: TOUR_ROUTES.skuDetail },
  { start: 14, end: 16, route: TOUR_ROUTES.poBuilder },
  { start: 17, end: 17, route: TOUR_ROUTES.home },
]

export const TOUR_STEPS: Step[] = [
  // ── Home (0-4) ──
  {
    target: 'body',
    placement: 'center',
    disableBeacon: true,
    content: 'Welcome to Stock Intelligence! This dashboard tracks 22,000+ SKUs across 167 brands and tells you what to reorder and when. All data syncs nightly from Tally. Let\'s take a quick tour.',
    title: 'Welcome to Stock Intelligence',
  },
  {
    target: '[data-tour="sync-indicator"]',
    content: 'This shows when data last synced from Tally. A green dot means data is fresh. Syncs run nightly so you always have yesterday\'s numbers.',
    title: 'Data Freshness',
  },
  {
    target: '[data-tour="summary-cards"]',
    content: 'Your daily snapshot. Critical SKUs need ordering now — the red number tells you how many. Click any card to drill in.',
    title: 'Summary Cards',
  },
  {
    target: '[data-tour="brand-search"]',
    content: 'Type any brand name to jump straight to its SKU list. Useful when you know exactly what you\'re looking for.',
    title: 'Brand Search',
  },
  {
    target: '[data-tour="priority-table"]',
    content: 'Brands sorted by urgency — most critical items at the top. Click any row to see that brand\'s individual SKUs.',
    title: 'Priority Brands',
  },

  // ── Brands (5-7) ──
  {
    target: '[data-tour="brand-cards"]',
    content: 'Each card summarizes a brand\'s health — how many critical SKUs, warnings, and dead stock items. Red and amber numbers need attention.',
    title: 'Brand Health Summary',
  },
  {
    target: '[data-tour="brand-filters"]',
    content: 'Filter to only brands with critical items, or sort by any column to focus your review.',
    title: 'Filters & Sorting',
  },
  {
    target: '[data-tour="brand-table"]',
    content: 'Click any brand row to see all its individual SKUs. Let\'s drill into one.',
    title: 'Drill Into a Brand',
  },

  // ── SKU Detail (8-13) ──
  {
    target: '[data-tour="sku-table"]',
    content: 'Every SKU for this brand. Status badges tell you at a glance what needs attention — red means act now, amber means plan ahead.',
    title: 'SKU Table',
  },
  {
    target: '[data-tour="sku-columns"]',
    content: 'Each column tells part of the story. Status shows urgency, Stock shows what you have, Velocity shows how fast it sells across all channels, and ABC shows revenue importance.',
    title: 'Understanding the Columns',
  },
  {
    target: '[data-tour="sku-expand-hint"]',
    content: 'Click any SKU row to expand it. You\'ll see the full story — stock history chart, sales breakdown by channel, and exactly how the reorder suggestion was calculated.',
    title: 'Expand for Details',
  },
  {
    target: '[data-tour="stock-timeline"]',
    content: 'This chart shows daily stock levels over time. You can see when stock ran out and when it was replenished. Drag across the chart to zoom into a date range.',
    title: 'Stock Timeline',
  },
  {
    target: '[data-tour="calculation-tab"]',
    content: 'This tab breaks down exactly how the reorder number was calculated — velocity from each channel, lead time, safety buffer. Every number is explained and traceable.',
    title: 'Calculation Breakdown',
  },
  {
    target: '[data-tour="override-buttons"]',
    content: 'If the system\'s estimate doesn\'t match reality — maybe you know a big wholesale order is coming, or a product is seasonal — click Adjust to set your own value. You\'ll need to provide a reason.',
    title: 'Overrides',
  },

  // ── PO Builder (14-16) ──
  {
    target: '[data-tour="po-table"]',
    content: 'The purchase order builder shows suggested quantities for every SKU that needs reordering. Toggle items in or out, adjust quantities, and add notes for your supplier.',
    title: 'Purchase Order Builder',
  },
  {
    target: '[data-tour="po-config"]',
    content: 'Configure lead time type and buffer settings for this order. These affect the suggested quantities.',
    title: 'PO Configuration',
  },
  {
    target: '[data-tour="po-export"]',
    content: 'Export to Excel — ready to send to your supplier. The export includes all quantities, part numbers, and notes.',
    title: 'Export to Excel',
  },

  // ── Wrap-up (17) ──
  {
    target: '[data-tour="help-menu"]',
    placement: 'bottom',
    content: 'That\'s the core workflow! You can replay this tour anytime from here. The Help Guide has detailed explanations of every concept, page-by-page guides, and daily workflow checklists.',
    title: 'You\'re All Set!',
  },
]
```

- [ ] **Step 2: Create GuidedTour component**

Create `src/dashboard/src/components/GuidedTour.tsx`:

```tsx
import { useState, useCallback, useEffect } from 'react'
import Joyride, { CallBackProps, STATUS, EVENTS, ACTIONS } from 'react-joyride'
import { useNavigate, useLocation } from 'react-router-dom'
import { TOUR_STEPS, STEP_ROUTE_MAP } from '@/lib/tour-steps'

const TOUR_STORAGE_KEY = 'tourCompleted'

function getRouteForStep(stepIndex: number): string | null {
  for (const mapping of STEP_ROUTE_MAP) {
    if (stepIndex >= mapping.start && stepIndex <= mapping.end) {
      return mapping.route
    }
  }
  return null
}

// Wait for a DOM element to appear (handles lazy loading + async data)
function waitForTarget(selector: string, timeoutMs = 5000): Promise<Element | null> {
  return new Promise((resolve) => {
    const el = document.querySelector(selector)
    if (el) { resolve(el); return }

    const start = Date.now()
    const poll = () => {
      const el = document.querySelector(selector)
      if (el) { resolve(el); return }
      if (Date.now() - start > timeoutMs) { resolve(null); return }
      requestAnimationFrame(poll)
    }
    requestAnimationFrame(poll)
  })
}

interface GuidedTourProps {
  run: boolean
  onFinish: () => void
}

export default function GuidedTour({ run, onFinish }: GuidedTourProps) {
  const [stepIndex, setStepIndex] = useState(0)
  const [isReady, setIsReady] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()

  // When navigating between pages, wait for the target element
  useEffect(() => {
    if (!run || !isReady) return
    const step = TOUR_STEPS[stepIndex]
    if (!step || step.target === 'body') return

    const target = step.target as string
    setIsReady(false)
    waitForTarget(target).then((el) => {
      // Even if element not found, proceed (joyride will skip gracefully)
      setIsReady(true)
    })
  }, [stepIndex, location.pathname, run])

  const handleCallback = useCallback((data: CallBackProps) => {
    const { action, index, status, type } = data

    // Tour finished or skipped
    if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
      localStorage.setItem(TOUR_STORAGE_KEY, 'true')
      onFinish()
      return
    }

    if (type === EVENTS.STEP_AFTER) {
      const nextIndex = action === ACTIONS.PREV ? index - 1 : index + 1

      if (nextIndex < 0 || nextIndex >= TOUR_STEPS.length) return

      const currentRoute = getRouteForStep(index)
      const nextRoute = getRouteForStep(nextIndex)

      if (nextRoute && nextRoute !== currentRoute) {
        // Need to navigate to a different page
        setIsReady(false)
        navigate(nextRoute)
        // Small delay for navigation + lazy load
        setTimeout(() => {
          setStepIndex(nextIndex)
        }, 300)
      } else {
        setStepIndex(nextIndex)
      }
    }
  }, [navigate, onFinish])

  if (!run) return null

  return (
    <Joyride
      steps={TOUR_STEPS}
      stepIndex={stepIndex}
      run={run && isReady}
      continuous
      showSkipButton
      showProgress
      disableOverlayClose
      spotlightClicks={false}
      callback={handleCallback}
      locale={{
        back: 'Back',
        close: 'Close',
        last: 'Finish',
        next: 'Next',
        skip: 'Skip tour',
      }}
      styles={{
        options: {
          primaryColor: '#18181b',
          zIndex: 10000,
        },
        tooltip: {
          borderRadius: '8px',
          fontSize: '14px',
        },
        tooltipTitle: {
          fontSize: '15px',
          fontWeight: 600,
        },
        buttonNext: {
          borderRadius: '6px',
          fontSize: '13px',
          padding: '8px 16px',
        },
        buttonBack: {
          color: '#71717a',
          fontSize: '13px',
        },
        buttonSkip: {
          color: '#a1a1aa',
          fontSize: '12px',
        },
      }}
    />
  )
}

// Export helpers for external use
export function isTourCompleted(): boolean {
  return localStorage.getItem(TOUR_STORAGE_KEY) === 'true'
}

export function resetTour(): void {
  localStorage.removeItem(TOUR_STORAGE_KEY)
}
```

- [ ] **Step 3: Verify build**

```bash
cd src/dashboard && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/lib/tour-steps.ts src/dashboard/src/components/GuidedTour.tsx
git commit -m "feat: add GuidedTour component with 18-step walkthrough"
```

---

## Chunk 4: Wiring & Integration

### Task 6: Wire Components into Layout and App

**Files:**
- Modify: `src/dashboard/src/components/Layout.tsx`

Add HelpMenu to header, mount GuidedTour, add data-tour attributes to sync indicator.

- [ ] **Step 1: Update Layout.tsx**

Add imports at the top:

```tsx
import HelpMenu from '@/components/HelpMenu'
import GuidedTour, { isTourCompleted, resetTour } from '@/components/GuidedTour'
import HelpTip from '@/components/HelpTip'
```

Add tour state inside the Layout component function:

```tsx
const [tourRunning, setTourRunning] = useState(() => !isTourCompleted())

const handleReplayTour = () => {
  resetTour()
  navigate('/')
  setTimeout(() => setTourRunning(true), 300)
}
```

Add `data-tour="sync-indicator"` attribute to the sync status container div. Add a HelpTip next to the sync text.

Add `data-tour="help-menu"` wrapper around HelpMenu. Insert the HelpMenu after the sync indicator in the header:

```tsx
<div data-tour="help-menu">
  <HelpMenu onReplayTour={handleReplayTour} />
</div>
```

Mount GuidedTour at the end of the Layout component's return, after `<Outlet />`:

```tsx
<GuidedTour run={tourRunning} onFinish={() => setTourRunning(false)} />
```

- [ ] **Step 2: Verify build**

```bash
cd src/dashboard && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/Layout.tsx
git commit -m "feat: wire HelpMenu and GuidedTour into Layout header"
```

---

### Task 7: Add data-tour Attributes and HelpTips to Existing Pages

**Files:**
- Modify: `src/dashboard/src/pages/Home.tsx`
- Modify: `src/dashboard/src/pages/BrandOverview.tsx`
- Modify: `src/dashboard/src/pages/SkuDetail.tsx`
- Modify: `src/dashboard/src/components/CalculationBreakdown.tsx`
- Modify: `src/dashboard/src/pages/PoBuilder.tsx`
- Modify: `src/dashboard/src/pages/Settings.tsx`

- [ ] **Step 1: Home.tsx — Add data-tour attributes and 1 HelpTip**

Import HelpTip. Add these attributes:
- `data-tour="summary-cards"` on the `grid grid-cols-3 gap-4` cards container
- `data-tour="brand-search"` on the brand search/combobox wrapper
- `data-tour="priority-table"` on the priority brands table container
- Add `<HelpTip tip="SKUs with less than lead time + buffer days of stock at current sell-through rate." helpAnchor="stockout-projection" />` next to the "Critical SKUs" card title

- [ ] **Step 2: BrandOverview.tsx — Add data-tour attributes and 2 HelpTips**

Import HelpTip. Add these attributes:
- `data-tour="brand-cards"` on the summary cards grid
- `data-tour="brand-filters"` on the filter/sort controls area
- `data-tour="brand-table"` on the table container
- Add HelpTip next to "Health" column header: `tip="Combined health indicator: count of critical, warning, and ok SKUs for this brand."` `helpAnchor="stockout-projection"`
- Add HelpTip next to "Dead / Slow" column header: `tip="Dead stock (zero sales beyond threshold) and slow movers (very low velocity)."` `helpAnchor="page-dead-stock"`

- [ ] **Step 3: SkuDetail.tsx — Add data-tour attributes and 4 HelpTips**

Import HelpTip. Add these attributes:
- `data-tour="sku-table"` on the table wrapper
- `data-tour="sku-columns"` on the `<TableHeader>` row
- `data-tour="sku-expand-hint"` on the first SKU row's expand button (or the table body)
- `data-tour="stock-timeline"` on the StockTimeline component wrapper (inside expanded row)
- `data-tour="calculation-tab"` on the Calculation tab trigger
- `data-tour="override-buttons"` on the override buttons container in CalculationBreakdown

Add HelpTips to column headers:
- "Status" header: `tip="Reorder urgency based on days of stock remaining: Critical (order now), Warning (order soon), OK (sufficient stock), Out of Stock (zero inventory)."` `helpAnchor="stockout-projection"`
- "Velocity /mo" header: `tip="Units sold per day, calculated from in-stock days only. Split by channel because wholesale, online, and store are parallel demand tracks drawing from the same inventory."` `helpAnchor="velocity"`
- "ABC" header: `tip="Revenue classification: A = top 80% revenue (highest priority), B = next 15%, C = bottom 5%. Drives buffer size and reorder priority."` `helpAnchor="abc-classification"`
- "Days Left" (in expanded summary strip, if present): `tip="Projected days until stockout at current total velocity."` `helpAnchor="stockout-projection"`

- [ ] **Step 4: CalculationBreakdown.tsx — Add 2 HelpTips**

Import HelpTip (already has other imports). Add:
- HelpTip next to "Buffer mode" label: `tip="Safety stock multiplier. Global uses ABC-class defaults. Per-SKU lets you set a custom buffer for this item."` `helpAnchor="lead-time-buffer"`
- HelpTip next to "Methodology" collapsible section header: `tip="Expand to see exactly how each number was calculated, with formulas and source data."` `helpAnchor="velocity"`
- Add `data-tour="override-buttons"` on the override forms container div

- [ ] **Step 5: PoBuilder.tsx — Add data-tour attributes and 1 HelpTip**

Import HelpTip. Add:
- `data-tour="po-table"` on the PO items table wrapper
- `data-tour="po-config"` on the configuration controls area (lead time type, buffer override)
- `data-tour="po-export"` on the Export button
- HelpTip next to "Suggested Qty" column header: `tip="Recommended order quantity: enough to cover lead time + buffer period at current velocity, minus current stock."` `helpAnchor="reorder-quantity"`

- [ ] **Step 6: Settings.tsx — Add 1 HelpTip**

Import HelpTip. Add:
- HelpTip next to the XYZ classification toggle: `tip="Demand variability scoring. Currently 99.6% of SKUs are Z-class (sporadic), so this adds little discrimination for art supplies."` `helpAnchor="abc-classification"`

- [ ] **Step 7: Verify full build**

```bash
cd src/dashboard && npx tsc --noEmit
```

- [ ] **Step 8: Commit**

```bash
git add src/dashboard/src/pages/Home.tsx src/dashboard/src/pages/BrandOverview.tsx src/dashboard/src/pages/SkuDetail.tsx src/dashboard/src/components/CalculationBreakdown.tsx src/dashboard/src/pages/PoBuilder.tsx src/dashboard/src/pages/Settings.tsx
git commit -m "feat: add data-tour attributes and HelpTip tooltips across all pages"
```

---

## Chunk 5: Final Integration & Deployment

### Task 8: End-to-End Testing

- [ ] **Step 1: Start local dev server**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000
```

In another terminal:
```bash
cd src/dashboard && npm run dev
```

- [ ] **Step 2: Test guided tour**

1. Clear localStorage: open browser console, run `localStorage.removeItem('tourCompleted')`
2. Refresh page — tour should auto-start
3. Click through all 18 steps — verify each spotlight targets the correct element
4. Verify page navigation works (Home → Brands → SKU Detail → PO Builder → Home)
5. After finishing, verify tour doesn't auto-start on refresh
6. Click "?" → "Replay Tour" — verify tour restarts

- [ ] **Step 3: Test HelpTip tooltips**

1. On Home page: click ⓘ next to Critical SKUs card — verify popover shows, "Learn more" links to /help#stockout-projection
2. On Brand Overview: check "Health" and "Dead / Slow" column header tooltips
3. On SKU Detail: check Status, Velocity, ABC column tooltips
4. On Calculation Breakdown: check Buffer mode and Methodology tooltips
5. On PO Builder: check Suggested Qty tooltip
6. On Settings: check XYZ toggle tooltip

- [ ] **Step 4: Test Help page**

1. Navigate to /help — verify sidebar renders with 5 sections
2. Click sidebar items — verify smooth scroll to section
3. Scroll manually — verify scroll-spy highlights correct sidebar item
4. Test deep links: navigate to /help#velocity — verify page scrolls to velocity section
5. Click "Learn more" from any tooltip — verify it lands on the correct section

- [ ] **Step 5: Verify production build**

```bash
cd src/dashboard && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 6: Commit and push**

```bash
git add -A
git commit -m "feat: complete help system — tour, tooltips, and help guide page"
git push origin main
```

This push triggers auto-deploy to Railway.

- [ ] **Step 7: Verify on production**

Open https://artlounge-reorder-production.up.railway.app — verify tour starts, tooltips work, help page loads.
