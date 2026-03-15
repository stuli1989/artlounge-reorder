# Mobile Responsiveness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 11 pages of the Art Lounge Stock Intelligence dashboard fully functional on mobile phones with touch-optimized interactions, bottom tab navigation, compact list rows, and bottom sheets.

**Architecture:** Conditional rendering via a `useIsMobile()` hook switches between desktop (unchanged) and mobile layouts at the 768px breakpoint. New shared components (MobileLayout, BottomSheet, MobileListRow, FilterDrawer) provide the mobile shell. Each page gets a mobile variant that reuses existing API calls and React Query cache.

**Tech Stack:** React 19, TypeScript, Tailwind CSS v4, shadcn/ui (Base UI), Recharts, React Query, react-joyride

**Spec:** `docs/superpowers/specs/2026-03-15-mobile-responsiveness-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `src/dashboard/src/hooks/useIsMobile.ts` | Reactive media query hook (< 768px) |
| `src/dashboard/src/components/mobile/MobileLayout.tsx` | Mobile app shell: header + bottom tabs + hamburger drawer |
| `src/dashboard/src/components/mobile/BottomSheet.tsx` | Sheet side="bottom" wrapper with drag handle, max-height, safe-area |
| `src/dashboard/src/components/mobile/MobileListRow.tsx` | Compact 2-line list row with status border, metrics, skeleton variant |
| `src/dashboard/src/components/mobile/FilterDrawer.tsx` | Bottom sheet with filter controls + active chip display |
| `src/dashboard/src/components/mobile/MobileSkuDetail.tsx` | Full-screen SKU detail overlay (chart, metrics, actions) |
| `src/dashboard/src/components/mobile/MobileSortSheet.tsx` | Bottom sheet with sort options |
| `src/dashboard/src/lib/mobile-tour-steps.ts` | Mobile-specific guided tour steps (10-12 steps) |

### Modified Files
| File | Changes |
|------|---------|
| `src/dashboard/src/components/Layout.tsx` | Conditionally render MobileLayout vs desktop header |
| `src/dashboard/src/pages/Home.tsx` | Horizontal scroll summary cards, list rows for priority brands |
| `src/dashboard/src/pages/BrandOverview.tsx` | Mobile card layout, filter drawer, responsive grids |
| `src/dashboard/src/pages/SkuDetail.tsx` | Mobile list rows, full-screen detail overlay, status pill tabs |
| `src/dashboard/src/pages/CriticalSkus.tsx` | Collapsible tier sections with list rows |
| `src/dashboard/src/pages/PoBuilder.tsx` | Collapsible config, list rows, FAB export button |
| `src/dashboard/src/pages/DeadStock.tsx` | List rows, filter drawer for thresholds |
| `src/dashboard/src/pages/PartyClassification.tsx` | List rows, classification bottom sheet |
| `src/dashboard/src/pages/SupplierManagement.tsx` | List rows, full-width stacked form |
| `src/dashboard/src/pages/OverrideReview.tsx` | List rows, action buttons on tap |
| `src/dashboard/src/pages/Settings.tsx` | Stacked accordion sections, full-width inputs |
| `src/dashboard/src/pages/Help.tsx` | TOC dropdown, single-column reflow |
| `src/dashboard/src/components/StockTimeline.tsx` | Date presets replace drag-to-select on mobile |
| `src/dashboard/src/components/GuidedTour.tsx` | Mobile step set, disable desktop tour on mobile |
| `src/dashboard/src/components/CalculationBreakdown.tsx` | Bottom sheet rendering on mobile |
| `src/dashboard/src/App.tsx` | Update LoadingSkeleton for mobile |

---

## Chunk 1: Foundation — Shared Components & Layout Shell

### Task 1: useIsMobile Hook

**Files:**
- Create: `src/dashboard/src/hooks/useIsMobile.ts`

- [ ] **Step 1: Create the hook**

```typescript
import { useState, useEffect } from 'react'

const MOBILE_BREAKPOINT = 768

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth < MOBILE_BREAKPOINT : false
  )

  useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mql.addEventListener('change', handler)
    setIsMobile(mql.matches)
    return () => mql.removeEventListener('change', handler)
  }, [])

  return isMobile
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd src/dashboard && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/hooks/useIsMobile.ts
git commit -m "feat: add useIsMobile reactive media query hook"
```

---

### Task 2: BottomSheet Component

**Files:**
- Create: `src/dashboard/src/components/mobile/BottomSheet.tsx`

- [ ] **Step 1: Create BottomSheet wrapping existing Sheet**

This wraps the existing shadcn Sheet component with `side="bottom"` and adds mobile-specific defaults: a drag handle bar, max-height constraint, and safe-area bottom padding.

```tsx
import * as React from 'react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetClose,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'

interface BottomSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title?: string
  description?: string
  children: React.ReactNode
  className?: string
}

export function BottomSheet({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: BottomSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className={cn(
          'max-h-[85vh] overflow-y-auto rounded-t-xl pb-[env(safe-area-inset-bottom)]',
          className
        )}
        showCloseButton={false}
      >
        {/* Drag handle */}
        <div className="flex justify-center pt-2 pb-1">
          <div className="h-1.5 w-12 rounded-full bg-muted-foreground/30" />
        </div>
        {(title || description) && (
          <SheetHeader className="px-4 pb-2">
            {title && <SheetTitle>{title}</SheetTitle>}
            {description && <SheetDescription>{description}</SheetDescription>}
          </SheetHeader>
        )}
        <div className="px-4 pb-4">{children}</div>
      </SheetContent>
    </Sheet>
  )
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd src/dashboard && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/mobile/BottomSheet.tsx
git commit -m "feat: add BottomSheet component wrapping Sheet side=bottom"
```

---

### Task 3: MobileListRow Component

**Files:**
- Create: `src/dashboard/src/components/mobile/MobileListRow.tsx`

- [ ] **Step 1: Create the reusable list row**

```tsx
import { cn } from '@/lib/utils'

const STATUS_BORDER: Record<string, string> = {
  critical: 'border-l-red-500',
  warning: 'border-l-amber-500',
  ok: 'border-l-green-500',
  out_of_stock: 'border-l-gray-400',
  no_data: 'border-l-gray-400',
}

interface MobileListRowProps {
  title: string
  subtitle?: string
  status?: string
  statusLabel?: string
  metrics?: { label: string; value: string; color?: string }[]
  badges?: React.ReactNode
  onClick?: () => void
  rightContent?: React.ReactNode
  className?: string
  children?: React.ReactNode
}

export function MobileListRow({
  title,
  subtitle,
  status,
  statusLabel,
  metrics,
  badges,
  onClick,
  rightContent,
  className,
  children,
}: MobileListRowProps) {
  const borderClass = status ? STATUS_BORDER[status] ?? 'border-l-gray-300' : 'border-l-transparent'

  return (
    <div
      className={cn(
        'border-l-[3px] px-4 py-3 border-b border-border/50 active:bg-muted/50 transition-colors',
        borderClass,
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {/* Line 1: Title + Status/Right content */}
      <div className="flex items-center justify-between gap-2 mb-0.5">
        <div className="min-w-0 flex-1">
          <span className="font-semibold text-sm truncate block">{title}</span>
          {subtitle && (
            <span className="text-xs text-muted-foreground">{subtitle}</span>
          )}
        </div>
        {statusLabel && status && (
          <StatusBadgeMobile status={status} label={statusLabel} />
        )}
        {rightContent}
      </div>
      {/* Line 2: Metrics + Badges */}
      {(metrics || badges) && (
        <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
          {metrics?.map((m, i) => (
            <span key={i}>
              {m.label}: <b className={cn('text-foreground', m.color)}>{m.value}</b>
            </span>
          ))}
          {badges}
        </div>
      )}
      {children}
    </div>
  )
}

function StatusBadgeMobile({ status, label }: { status: string; label: string }) {
  const colors: Record<string, string> = {
    critical: 'bg-red-900/60 text-red-300',
    warning: 'bg-amber-900/60 text-amber-300',
    ok: 'bg-green-900/60 text-green-300',
    out_of_stock: 'bg-gray-800 text-gray-400',
    no_data: 'bg-gray-800 text-gray-400',
  }
  return (
    <span className={cn('text-[10px] px-2 py-0.5 rounded-full font-medium whitespace-nowrap', colors[status] ?? 'bg-gray-800 text-gray-400')}>
      {label}
    </span>
  )
}

export function MobileListRowSkeleton() {
  return (
    <div className="border-l-[3px] border-l-transparent px-4 py-3 border-b border-border/50 animate-pulse">
      <div className="flex items-center justify-between mb-1">
        <div className="h-4 w-48 bg-muted rounded" />
        <div className="h-4 w-16 bg-muted rounded-full" />
      </div>
      <div className="flex gap-3">
        <div className="h-3 w-16 bg-muted rounded" />
        <div className="h-3 w-16 bg-muted rounded" />
        <div className="h-3 w-16 bg-muted rounded" />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd src/dashboard && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/mobile/MobileListRow.tsx
git commit -m "feat: add MobileListRow component with skeleton variant"
```

---

### Task 4: MobileLayout — App Shell

**Files:**
- Create: `src/dashboard/src/components/mobile/MobileLayout.tsx`
- Modify: `src/dashboard/src/components/Layout.tsx`

- [ ] **Step 1: Create MobileLayout component**

The mobile shell: compact header with hamburger + page title + sync dot, content area, bottom tab bar, and a hamburger drawer using Sheet side="left".

```tsx
import { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSyncStatus, fetchOverrides } from '@/lib/api'
import {
  LayoutDashboard, Package, ShieldAlert, ClipboardList,
  Users, Truck, Pencil, Settings, BookOpen, Skull, Menu, X,
} from 'lucide-react'
import { Sheet, SheetContent } from '@/components/ui/sheet'
import HelpMenu from '@/components/HelpMenu'
import GuidedTour, { isTourCompleted, resetTour } from '@/components/GuidedTour'

const TABS = [
  { path: '/', label: 'Home', icon: LayoutDashboard, exact: true },
  { path: '/brands', label: 'Brands', icon: Package, exact: true },
  { path: '/critical', label: 'Critical', icon: ShieldAlert },
  { path: '/po', label: 'PO', icon: ClipboardList },
]

const DRAWER_GROUPS = [
  {
    label: 'Data Management',
    items: [
      { path: '/parties', label: 'Parties', icon: Users },
      { path: '/suppliers', label: 'Suppliers', icon: Truck },
      { path: '/overrides', label: 'Overrides', icon: Pencil },
      { path: '/brands?filter=dead-stock', label: 'Dead Stock', icon: Skull },
    ],
  },
  {
    label: 'System',
    items: [
      { path: '/settings', label: 'Settings', icon: Settings },
      { path: '/help', label: 'Help Guide', icon: BookOpen },
    ],
  },
]

const freshnessColors = {
  fresh: 'bg-green-500',
  stale: 'bg-amber-500',
  critical: 'bg-red-500',
}

interface MobileLayoutProps {
  tourRunning: boolean
  setTourRunning: (v: boolean) => void
}

export default function MobileLayout({ tourRunning, setTourRunning }: MobileLayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [warningDismissed, setWarningDismissed] = useState(false)

  const handleReplayTour = () => {
    resetTour()
    navigate('/')
    setTimeout(() => setTourRunning(true), 300)
  }

  const { data: sync } = useQuery({
    queryKey: ['syncStatus'],
    queryFn: fetchSyncStatus,
    refetchInterval: 60000,
    refetchIntervalInBackground: false,
  })

  const { data: staleOverrides } = useQuery({
    queryKey: ['overrides', 'stale'],
    queryFn: () => fetchOverrides({ is_stale: true }),
    refetchInterval: 60000,
    refetchIntervalInBackground: false,
  })

  const staleCount = staleOverrides?.length ?? 0
  const unclassifiedCount = sync?.unclassified_parties_count ?? 0
  const hasWarnings = unclassifiedCount > 0 || staleCount > 0

  // Derive page title from path
  const pageTitle = getPageTitle(location.pathname)

  const isTabActive = (path: string, exact?: boolean) =>
    exact ? location.pathname === path : location.pathname.startsWith(path)

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Mobile Header */}
      <header className="border-b bg-card px-4 py-2.5 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setDrawerOpen(true)}
            className="p-1.5 -ml-1.5 rounded-md hover:bg-muted"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="font-semibold text-[15px] truncate">{pageTitle}</span>
        </div>
        <div className="flex items-center gap-2">
          {sync && (
            <span className={`h-2 w-2 rounded-full ${freshnessColors[sync.freshness]}`} />
          )}
          <HelpMenu onReplayTour={handleReplayTour} />
        </div>
      </header>

      {/* Warning notification bar — dismissible per session */}
      {hasWarnings && !warningDismissed && (
        <div className="bg-amber-900/30 border-b border-amber-800/50 px-4 py-2 text-xs text-amber-200 flex items-center gap-2">
          <span className="flex-1 truncate">
            {unclassifiedCount > 0 && `${unclassifiedCount} unclassified parties`}
            {unclassifiedCount > 0 && staleCount > 0 && ' · '}
            {staleCount > 0 && `${staleCount} stale overrides`}
          </span>
          <Link
            to={unclassifiedCount > 0 ? '/parties' : '/overrides'}
            className="text-amber-300 font-medium whitespace-nowrap"
          >
            Review →
          </Link>
          <button
            onClick={() => setWarningDismissed(true)}
            className="text-amber-400/60 hover:text-amber-300 ml-1"
            aria-label="Dismiss"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>

      {/* Bottom Tab Bar */}
      <nav className="border-t bg-card flex pb-[env(safe-area-inset-bottom)] sticky bottom-0 z-40">
        {TABS.map(({ path, label, icon: Icon, exact }) => {
          const active = isTabActive(path, exact)
          return (
            <Link
              key={path}
              to={path}
              className={`flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] transition-colors ${
                active ? 'text-primary' : 'text-muted-foreground'
              }`}
            >
              <Icon className="h-5 w-5" />
              <span className={active ? 'font-semibold' : ''}>{label}</span>
            </Link>
          )
        })}
      </nav>

      {/* Hamburger Drawer */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left" className="w-[280px] p-0" showCloseButton={false}>
          <div className="p-4 border-b">
            <div className="font-bold text-base">Art Lounge</div>
            <div className="text-xs text-muted-foreground mt-0.5">Stock Intelligence</div>
          </div>
          <div className="p-3 flex-1 overflow-y-auto">
            {DRAWER_GROUPS.map((group) => (
              <div key={group.label} className="mb-4">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground/50 px-3 mb-1">
                  {group.label}
                </div>
                {group.items.map(({ path, label, icon: Icon }) => {
                  const active = location.pathname === path
                  return (
                    <Link
                      key={path}
                      to={path}
                      onClick={() => setDrawerOpen(false)}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                        active
                          ? 'bg-primary text-primary-foreground'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </Link>
                  )
                })}
              </div>
            ))}
          </div>
          <div className="p-4 border-t text-xs text-muted-foreground">
            {sync?.last_sync_completed
              ? `Last sync: ${new Date(sync.last_sync_completed).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
              : 'Never synced'}
          </div>
        </SheetContent>
      </Sheet>

      <GuidedTour run={tourRunning} onFinish={() => setTourRunning(false)} />
    </div>
  )
}

function getPageTitle(pathname: string): string {
  if (pathname === '/') return 'Stock Intelligence'
  if (pathname === '/brands') return 'Brands'
  if (pathname.startsWith('/brands/') && pathname.includes('/po')) return 'Build PO'
  if (pathname.startsWith('/brands/') && pathname.includes('/dead-stock')) return 'Dead Stock'
  if (pathname.startsWith('/brands/')) return 'SKU Detail'
  if (pathname === '/critical') return 'Critical SKUs'
  if (pathname === '/po') return 'Build PO'
  if (pathname === '/parties') return 'Parties'
  if (pathname === '/suppliers') return 'Suppliers'
  if (pathname === '/overrides') return 'Overrides'
  if (pathname === '/settings') return 'Settings'
  if (pathname === '/help') return 'Help'
  return 'Stock Intelligence'
}
```

- [ ] **Step 2: Modify Layout.tsx to conditionally render**

In `src/dashboard/src/components/Layout.tsx`, import `useIsMobile` and `MobileLayout`, then wrap the return to conditionally render:

```tsx
// Add at top of file:
import { useIsMobile } from '@/hooks/useIsMobile'
import MobileLayout from '@/components/mobile/MobileLayout'

// In the component body, before the return:
const isMobile = useIsMobile()

if (isMobile) {
  return (
    <MobileLayout
      tourRunning={tourRunning}
      setTourRunning={setTourRunning}
    />
  )
}

// ... existing desktop return stays unchanged
```

- [ ] **Step 3: Build and test**

Run: `cd src/dashboard && npm run build`
Expected: Build succeeds. Open in browser, resize to < 768px — should see mobile header + bottom tabs. Resize back to desktop — should see normal header nav.

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/components/mobile/MobileLayout.tsx src/dashboard/src/components/Layout.tsx
git commit -m "feat: add MobileLayout with bottom tabs and hamburger drawer"
```

---

### Task 5: FilterDrawer Component

**Files:**
- Create: `src/dashboard/src/components/mobile/FilterDrawer.tsx`

- [ ] **Step 1: Create the filter drawer**

A bottom sheet that renders filter controls and shows active filters as dismissible chips.

```tsx
import { BottomSheet } from '@/components/mobile/BottomSheet'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface FilterChip {
  key: string
  label: string
  onRemove: () => void
}

interface FilterDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  chips: FilterChip[]
  children: React.ReactNode
}

export function FilterDrawer({ open, onOpenChange, chips, children }: FilterDrawerProps) {
  return (
    <BottomSheet open={open} onOpenChange={onOpenChange} title="Filters">
      <div className="space-y-4">{children}</div>
    </BottomSheet>
  )
}

export function FilterChips({ chips }: { chips: FilterChip[] }) {
  if (chips.length === 0) return null
  return (
    <div className="flex gap-1.5 flex-wrap">
      {chips.map((chip) => (
        <button
          key={chip.key}
          onClick={chip.onRemove}
          className="inline-flex items-center gap-1 bg-primary/20 text-primary text-xs px-2.5 py-1 rounded-full"
        >
          {chip.label}
          <X className="h-3 w-3 opacity-60" />
        </button>
      ))}
    </div>
  )
}

export function FilterButton({
  activeCount,
  onClick,
}: {
  activeCount: number
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="bg-muted rounded-lg px-3 py-2.5 text-xs flex items-center gap-1.5"
    >
      Filters
      {activeCount > 0 && (
        <span className="bg-primary text-primary-foreground text-[9px] rounded-full w-4 h-4 flex items-center justify-center font-semibold">
          {activeCount}
        </span>
      )}
    </button>
  )
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd src/dashboard && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/mobile/FilterDrawer.tsx
git commit -m "feat: add FilterDrawer bottom sheet with chip display"
```

---

### Task 6: MobileSortSheet Component

**Files:**
- Create: `src/dashboard/src/components/mobile/MobileSortSheet.tsx`

- [ ] **Step 1: Create the sort bottom sheet**

```tsx
import { BottomSheet } from '@/components/mobile/BottomSheet'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SortOption {
  value: string
  label: string
}

interface MobileSortSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  options: SortOption[]
  value: string
  direction: 'asc' | 'desc'
  onSort: (value: string) => void
  onToggleDirection: () => void
}

export function MobileSortSheet({
  open,
  onOpenChange,
  options,
  value,
  direction,
  onSort,
  onToggleDirection,
}: MobileSortSheetProps) {
  return (
    <BottomSheet open={open} onOpenChange={onOpenChange} title="Sort by">
      <div className="space-y-1">
        {options.map((opt) => (
          <button
            key={opt.value}
            onClick={() => {
              onSort(opt.value)
              onOpenChange(false)
            }}
            className={cn(
              'w-full text-left px-3 py-2.5 rounded-lg text-sm flex items-center justify-between transition-colors',
              value === opt.value ? 'bg-primary/10 text-primary' : 'hover:bg-muted'
            )}
          >
            {opt.label}
            {value === opt.value && <Check className="h-4 w-4" />}
          </button>
        ))}
      </div>
      <button
        onClick={onToggleDirection}
        className="w-full mt-3 px-3 py-2.5 rounded-lg text-sm bg-muted text-center"
      >
        Direction: {direction === 'asc' ? '↑ Ascending' : '↓ Descending'}
      </button>
    </BottomSheet>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/src/components/mobile/MobileSortSheet.tsx
git commit -m "feat: add MobileSortSheet component"
```

---

## Chunk 2: Core Pages — Home, Brands, SKU Detail

### Task 7: Home Page — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/Home.tsx`

- [ ] **Step 1: Add mobile layout**

Import `useIsMobile` and conditionally render mobile vs desktop content. Mobile changes:
- Summary cards: wrap in `flex gap-2.5 overflow-x-auto` with `min-w-[130px]` per card (horizontal scroll strip) when mobile
- Priority brands: render as `MobileListRow` components instead of Table rows
- Search: full-width, no max-w-sm constraint

Key changes to make:
1. Import `useIsMobile` and `MobileListRow`
2. Summary cards section: `{isMobile ? <MobileHomeSummary /> : <DesktopGrid />}`
3. Priority table: `{isMobile ? <MobilePriorityList /> : <DesktopPriorityTable />}`
4. Remove `max-w-7xl` padding (MobileLayout handles it) — wrap page content in `className={isMobile ? 'px-4 py-4' : ''}`

- [ ] **Step 2: Build and test**

Run: `cd src/dashboard && npm run build`
Expected: Build succeeds. Mobile view shows horizontal-scroll summary cards and compact brand list rows.

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/Home.tsx
git commit -m "feat: mobile layout for Home page — scroll cards + list rows"
```

---

### Task 8: Brand Overview — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/BrandOverview.tsx`

- [ ] **Step 1: Add mobile layout**

Mobile changes:
1. Summary metric cards (grid-cols-6): on mobile, render as `flex overflow-x-auto gap-2` horizontal scroll strip with `min-w-[100px]` per card
2. Filters: replace inline controls with sticky search + `FilterButton` + `FilterChips`. Filter bottom sheet contains: critical-only toggle, sort selector
3. Brand list: always show card view on mobile (no compact table). Each card uses the design from the mockup — brand name, health %, 4-cell status grid (Crit/Warn/OK/Dead)
4. View mode toggle: hidden on mobile (cards only)

- [ ] **Step 2: Build and test**

Run: `cd src/dashboard && npm run build`
Expected: Mobile shows horizontal metric strip, sticky search with filter button, brand cards with status grid.

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/BrandOverview.tsx
git commit -m "feat: mobile layout for Brand Overview — cards with status grid"
```

---

### Task 9: MobileSkuDetail — Full-Screen Detail Overlay

**Files:**
- Create: `src/dashboard/src/components/mobile/MobileSkuDetail.tsx`

- [ ] **Step 1: Create the full-screen SKU detail view**

This renders when a user taps a SKU row on mobile. It's a full-screen overlay within the same route, driven by component state. Uses History API for back-button support.

Key sections to render:
1. Header: back arrow + SKU name + Part No + status badge
2. 2×2 metric grid: Current Stock, Days to Stockout, Total Velocity, Suggested Qty
3. Channel velocity breakdown rows (Wholesale / Online / Store)
4. Stock timeline chart with date preset buttons (import StockTimeline, pass `disableDragSelect` prop)
5. Classification badges: ABC, XYZ, Buffer multiplier
6. Action buttons: "View Calculations" (opens CalculationBreakdown in BottomSheet), "Override" (opens override form in BottomSheet)

The component receives the full SKU data object and `onBack` callback.

```tsx
// Key interface:
interface MobileSkuDetailProps {
  sku: SkuMetric  // from existing types
  categoryName: string
  onBack: () => void
  velocityType: 'flat' | 'wma'
}
```

On mount, push a history entry. Listen for `popstate` to call `onBack`. Clean up on unmount.

- [ ] **Step 2: Build and test**

Run: `cd src/dashboard && npm run build`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/mobile/MobileSkuDetail.tsx
git commit -m "feat: add MobileSkuDetail full-screen overlay"
```

---

### Task 10: SKU Detail Page — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/SkuDetail.tsx`
- Modify: `src/dashboard/src/components/StockTimeline.tsx`

- [ ] **Step 1: Modify StockTimeline for mobile**

Add a `disableDragSelect?: boolean` prop to StockTimeline. When true:
- Disable onMouseDown/onMouseMove/onMouseUp handlers on the chart
- Show date preset buttons below the chart (7d, 30d, 90d, All)
- Preset buttons filter the positions data passed to the chart by date range
- Remove the drag selection ReferenceArea

- [ ] **Step 2: Add mobile layout to SkuDetail**

Mobile changes:
1. Header: show back arrow + brand name + SKU count (remove classification explainer, velocity toggle, date range selector — these move to filter drawer)
2. Summary cards (grid-cols-5): horizontal scroll strip on mobile
3. Filters: sticky search + horizontal scrolling status pill tabs (replace Select dropdown). Filter button for advanced filters (ABC, XYZ, hazardous, dead stock, intent)
4. Sort: button in header opens MobileSortSheet
5. SKU rows: render as MobileListRow instead of TableRow
6. Expand behavior: on mobile, set `selectedSku` state → render MobileSkuDetail overlay
7. Pagination: simplified — just Previous/Next buttons, no page size selector
8. Save and restore scroll position when opening/closing detail overlay

- [ ] **Step 3: Build and test**

Run: `cd src/dashboard && npm run build`
Expected: Mobile shows compact list rows with status pills, tap opens full-screen detail.

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/pages/SkuDetail.tsx src/dashboard/src/components/StockTimeline.tsx
git commit -m "feat: mobile layout for SKU Detail — list rows + full-screen detail overlay"
```

---

## Chunk 3: Remaining Daily Workflow Pages

### Task 11: Critical SKUs — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/CriticalSkus.tsx`

- [ ] **Step 1: Add mobile layout**

Mobile changes:
1. Header: title only, classification explainer + velocity toggle move to a "..." menu or hidden
2. Filters: sticky search + filter button (status, ABC)
3. Tier sections: keep collapsible Card wrappers but render SKU rows as MobileListRow inside
4. Table columns: replaced by MobileListRow (title=SKU name, status, metrics=[Stock, Velocity, Days Left])
5. Tap navigates to full-screen detail (reuse MobileSkuDetail, need to pass brand context)

- [ ] **Step 2: Build and test**

Run: `cd src/dashboard && npm run build`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/CriticalSkus.tsx
git commit -m "feat: mobile layout for Critical SKUs — list rows in collapsible tiers"
```

---

### Task 12: PO Builder — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/PoBuilder.tsx`

- [ ] **Step 1: Add mobile layout**

Mobile changes:
1. Config section: wrap in a collapsible Card. Show "Config ▾" header that expands/collapses. Stack all inputs vertically (full-width). Lead time selector, buffer slider, include checkboxes all stack.
2. SKU list: MobileListRow with qty shown in the metrics line. Tap row opens a BottomSheet for editing qty + notes for that SKU. Qty input must have `inputmode="numeric"` for numeric keyboard.
3. Export: floating action button (fixed bottom-right, 56px circle, above bottom tabs z-index). Uses Download icon.
4. "Add Custom SKUs" button: in header area, opens SkuInputDialog as BottomSheet on mobile.
5. Totals display: sticky bar above the FAB showing "X items · X units"

- [ ] **Step 2: Build and test**

Run: `cd src/dashboard && npm run build`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/PoBuilder.tsx
git commit -m "feat: mobile layout for PO Builder — collapsible config, list rows, FAB export"
```

---

## Chunk 4: Admin & Setup Pages

### Task 13: Dead Stock — Mobile Layout + Virtualization

**Files:**
- Modify: `src/dashboard/src/pages/DeadStock.tsx`
- Modify: `src/dashboard/package.json` (add `@tanstack/react-virtual`)

- [ ] **Step 1: Install react-virtual**

Run: `cd src/dashboard && npm install @tanstack/react-virtual`

Dead Stock loads ALL items for a brand without pagination (can be 1000+). On mobile, rendering 1000+ MobileListRow components causes scroll jank. Virtual scrolling renders only visible rows.

- [ ] **Step 2: Add mobile layout with virtual list**

Mobile changes:
1. Dead/Slow tabs stay as Tabs at top
2. SKU rows: MobileListRow inside a `useVirtualizer` container from `@tanstack/react-virtual`. Each row estimated at 60px height. Only visible rows render.
3. Threshold config: moves into FilterDrawer (bottom sheet)
4. Expandable rows on mobile: tap navigates to MobileSkuDetail (consistent with SKU Detail page)
5. Reorder intent selector: renders inline (compact enough)
6. Desktop rendering stays unchanged (no virtualization on desktop — pagination handles it)

- [ ] **Step 3: Build and test, commit**

```bash
git add src/dashboard/src/pages/DeadStock.tsx src/dashboard/package.json src/dashboard/package-lock.json
git commit -m "feat: mobile layout for Dead Stock — virtualized list rows, filter drawer"
```

---

### Task 14: Party Classification — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/PartyClassification.tsx`

- [ ] **Step 1: Add mobile layout**

Mobile changes:
1. Table → MobileListRow: party name as title, current classification as status badge
2. Tap row opens BottomSheet with classification picker (6 options as large tap-friendly buttons)
3. Search: sticky at top, full-width

- [ ] **Step 2: Build and test, commit**

```bash
git add src/dashboard/src/pages/PartyClassification.tsx
git commit -m "feat: mobile layout for Party Classification — list rows with bottom sheet picker"
```

---

### Task 15: Supplier Management — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/SupplierManagement.tsx`

- [ ] **Step 1: Add mobile layout**

Mobile changes:
1. Supplier list: MobileListRow with supplier name, lead time, buffer override
2. Add button: in header area (+ icon)
3. Edit: tap row opens BottomSheet or full-screen form overlay with stacked full-width inputs
4. Delete: confirmation via BottomSheet
5. Form inputs: all full-width, stacked vertically, `inputmode="decimal"` on numeric fields

- [ ] **Step 2: Build and test, commit**

```bash
git add src/dashboard/src/pages/SupplierManagement.tsx
git commit -m "feat: mobile layout for Supplier Management — list rows, stacked forms"
```

---

### Task 16: Override Review — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/OverrideReview.tsx`

- [ ] **Step 1: Add mobile layout**

Mobile changes:
1. Table → MobileListRow: override type + SKU name as title, value + age as metrics
2. Keep/Remove buttons: shown below the row content on tap (not swipe)
3. Stale filter toggle: at top, full-width

- [ ] **Step 2: Build and test, commit**

```bash
git add src/dashboard/src/pages/OverrideReview.tsx
git commit -m "feat: mobile layout for Override Review — list rows with action buttons"
```

---

## Chunk 5: Settings, Help, Charts, Tour

### Task 17: Settings — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/Settings.tsx`

- [ ] **Step 1: Add mobile layout**

Mobile changes:
1. Remove sidebar (w-[200px] shrink-0 sticky): hide on mobile
2. Sections render as stacked collapsible panels (using Collapsible or custom accordion)
3. Each section header: icon + title + chevron, tap to expand/collapse
4. Form inputs: full-width, stack vertically (remove grid-cols-3 on mobile)
5. Save button: sticky at bottom of viewport (`fixed bottom-0 left-0 right-0 p-4 bg-background border-t z-30` — above bottom tabs)
6. Number inputs: add `inputmode="decimal"`

- [ ] **Step 2: Build and test, commit**

```bash
git add src/dashboard/src/pages/Settings.tsx
git commit -m "feat: mobile layout for Settings — stacked accordion sections"
```

---

### Task 18: Help Page — Mobile Layout

**Files:**
- Modify: `src/dashboard/src/pages/Help.tsx`

- [ ] **Step 1: Add mobile layout**

Mobile changes:
1. Sidebar scroll-spy TOC: replace with a sticky dropdown Select at top of page (picks section to scroll to)
2. Content grids (grid-cols-2, grid-cols-3): reflow to single column on mobile
3. Formula boxes: full-width
4. Page guide cards (grid-cols-2): stack to single column
5. Glossary grid (grid-cols-2): stack to single column
6. All content padding: reduce from px-8 to px-4

- [ ] **Step 2: Build and test, commit**

```bash
git add src/dashboard/src/pages/Help.tsx
git commit -m "feat: mobile layout for Help — dropdown TOC, single-column reflow"
```

---

### Task 19: CalculationBreakdown — Bottom Sheet on Mobile

**Files:**
- Modify: `src/dashboard/src/components/CalculationBreakdown.tsx`

- [ ] **Step 1: Add mobile rendering**

When `useIsMobile()` is true:
1. Wrap content in `BottomSheet` instead of `Dialog`
2. Override forms inside also use `BottomSheet` instead of `Dialog`
3. Grid layouts inside (grid-cols-3 etc.) stack to single column on mobile

- [ ] **Step 2: Build and test, commit**

```bash
git add src/dashboard/src/components/CalculationBreakdown.tsx
git commit -m "feat: CalculationBreakdown renders as bottom sheet on mobile"
```

---

### Task 20: StockTimeline — Mobile Chart Enhancements

**Files:**
- Modify: `src/dashboard/src/components/StockTimeline.tsx`

This may have been partially done in Task 10. Verify:
1. `disableDragSelect` prop disables mouse handlers
2. Date preset buttons render below chart when `disableDragSelect` is true
3. Transaction table below chart: on mobile, show simplified columns (Date, Party, Qty only) or use MobileListRow format
4. Chart height: reduce to `height={160}` on mobile for more list space

- [ ] **Step 1: Finalize mobile chart, commit**

```bash
git add src/dashboard/src/components/StockTimeline.tsx
git commit -m "feat: StockTimeline mobile — date presets, reduced height, simplified transactions"
```

---

### Task 21: Guided Tour — Mobile Steps

**Files:**
- Create: `src/dashboard/src/lib/mobile-tour-steps.ts`
- Modify: `src/dashboard/src/components/GuidedTour.tsx`

- [ ] **Step 1: Create mobile tour steps**

```typescript
// mobile-tour-steps.ts
import { type Step } from 'react-joyride'

export const mobileTourSteps: Step[] = [
  {
    target: 'body',
    content: 'Welcome to Art Lounge Stock Intelligence! Let me show you around the mobile experience.',
    placement: 'center',
    disableBeacon: true,
    title: 'Welcome!',
  },
  // ... 10-12 steps targeting mobile elements with data-tour-mobile attributes
  // Target bottom tab bar, list rows, filter button, sort button, etc.
]

export const MOBILE_STEP_ROUTE_MAP: Record<number, string> = {
  0: '/',
  // ... route mapping for mobile steps
}
```

- [ ] **Step 2: Modify GuidedTour to select step set**

In GuidedTour.tsx:
- Import `useIsMobile`
- If mobile, use `mobileTourSteps` and `MOBILE_STEP_ROUTE_MAP`
- If desktop, use existing `tourSteps` and `STEP_ROUTE_MAP`
- Mobile tour uses `placement: 'top'` or `'bottom'` only (never left/right)

- [ ] **Step 3: Add `data-tour-mobile` attributes to mobile components**

Add `data-tour-mobile="..."` attributes to:
- MobileLayout bottom tab items
- MobileListRow first item
- FilterButton
- MobileSortSheet trigger
- BottomSheet content area

- [ ] **Step 4: Build and test, commit**

```bash
git add src/dashboard/src/lib/mobile-tour-steps.ts src/dashboard/src/components/GuidedTour.tsx
git commit -m "feat: mobile-specific guided tour with 12 steps"
```

---

## Chunk 6: Polish & Testing

### Task 22: App.tsx — Mobile Loading Skeleton

**Files:**
- Modify: `src/dashboard/src/App.tsx`

- [ ] **Step 1: Update LoadingSkeleton for mobile**

The current LoadingSkeleton uses `grid-cols-5`. On mobile, show:
- 2 skeleton bars (mimicking MobileListRow)
- Single column layout
- Use `useIsMobile()` to conditionally render

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/src/App.tsx
git commit -m "feat: mobile-aware loading skeleton"
```

---

### Task 23: Global CSS — Safe Areas & Touch Targets

**Files:**
- Modify: `src/dashboard/src/index.css`

- [ ] **Step 1: Add mobile-specific global styles**

```css
/* Safe area support for iOS */
@supports (padding-bottom: env(safe-area-inset-bottom)) {
  .pb-safe {
    padding-bottom: env(safe-area-inset-bottom);
  }
}

/* Ensure minimum touch targets on mobile */
@media (max-width: 767px) {
  button, [role="button"], a, input, select, textarea {
    min-height: 44px;
  }

  /* Prevent zoom on input focus (iOS) */
  input, select, textarea {
    font-size: 16px;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/src/index.css
git commit -m "feat: global CSS for safe areas and mobile touch targets"
```

---

### Task 24: Full Build & Cross-Page Testing

- [ ] **Step 1: Full production build**

Run: `cd src/dashboard && npm run build`
Expected: Clean build, no TypeScript errors, no warnings.

- [ ] **Step 2: Test all pages at mobile width**

Open browser, set viewport to 375×812 (iPhone 13). Navigate every page:
1. Home — horizontal scroll cards, brand list rows
2. Brands — filter chips, brand cards with status grid
3. SKU Detail — list rows, tap to full-screen detail, chart with presets
4. Critical — collapsible tiers, list rows
5. PO Builder — collapsible config, list rows, FAB export
6. Dead Stock — tabs, list rows
7. Parties — list rows, classification sheet
8. Suppliers — list rows, stacked form
9. Overrides — list rows, action buttons
10. Settings — accordion sections, sticky save
11. Help — dropdown TOC, single-column

- [ ] **Step 3: Test all pages at desktop width**

Verify nothing is broken at > 1024px. Every page should render exactly as before.

- [ ] **Step 4: Test bottom tabs and drawer navigation**

Tap each bottom tab, verify correct page loads. Open hamburger, tap each drawer item, verify navigation + drawer closes.

- [ ] **Step 5: Test sort, filter, search on mobile**

On SKU Detail and Brand Overview, test search input, filter drawer, sort sheet. Verify chips appear and dismiss correctly.

- [ ] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix: mobile responsiveness polish and cross-page fixes"
```

---

### Task 25: Deploy

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

Railway auto-deploys from main. Wait for deployment to complete.

- [ ] **Step 2: Test on actual phone**

Open https://artlounge-reorder-production.up.railway.app on a real phone (Android + iPhone if possible). Walk through the full daily workflow:
1. Home → check criticals
2. Brands → tap a brand
3. SKU Detail → tap a SKU → view chart → back
4. Critical → check tiers
5. PO Builder → adjust qty → export
6. Settings → change buffer → save

- [ ] **Step 3: Fix any issues found on real devices**

Mobile browsers may reveal issues not visible in desktop responsive mode (safe areas, scroll behavior, touch targets, viewport quirks).
