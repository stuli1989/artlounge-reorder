import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Rocket, Lightbulb, Layout, CalendarCheck, BookOpen, ArrowRight,
  Package, Database, Users, LayoutDashboard, ShieldAlert, ClipboardList,
  Truck, Pencil, Settings, Search, Snowflake, TrendingUp, TrendingDown, Minus,
  Info,
} from 'lucide-react'
import { useIsMobile } from '@/hooks/useIsMobile'

/* ---------- sidebar data ---------- */

interface SidebarItem {
  id: string
  label: string
  children?: { id: string; label: string }[]
}

interface SidebarGroup {
  id: string
  label: string
  icon: React.ElementType
  items: SidebarItem[]
}

const SIDEBAR_SECTIONS: SidebarGroup[] = [
  {
    id: 'getting-started',
    label: 'Getting Started',
    icon: Rocket,
    items: [{ id: 'getting-started', label: 'Overview' }],
  },
  {
    id: 'key-concepts',
    label: 'Key Concepts',
    icon: Lightbulb,
    items: [
      { id: 'three-channels', label: 'Three Channels' },
      { id: 'velocity', label: 'Velocity' },
      { id: 'abc-classification', label: 'ABC Classification' },
      { id: 'lead-time-buffer', label: 'Lead Time & Buffer' },
      { id: 'stockout-projection', label: 'Stockout Projection' },
      { id: 'reorder-quantity', label: 'Reorder Quantity' },
      { id: 'overrides', label: 'Overrides' },
      { id: 'channel-classification', label: 'Channel Classification' },
    ],
  },
  {
    id: 'page-guides',
    label: 'Page Guides',
    icon: Layout,
    items: [
      { id: 'page-home', label: 'Home' },
      { id: 'page-brands', label: 'Brands' },
      { id: 'page-sku-detail', label: 'SKU Detail' },
      { id: 'page-critical', label: 'Critical SKUs' },
      { id: 'page-po-builder', label: 'Build PO' },
      { id: 'page-dead-stock', label: 'Dead Stock' },
      { id: 'page-parties', label: 'Parties' },
      { id: 'page-suppliers', label: 'Suppliers' },
      { id: 'page-overrides', label: 'Overrides' },
      { id: 'page-settings', label: 'Settings' },
    ],
  },
  {
    id: 'daily-workflows',
    label: 'Daily Workflows',
    icon: CalendarCheck,
    items: [
      { id: 'workflow-morning', label: 'Morning Check' },
      { id: 'workflow-deep-dive', label: 'Deep Dive' },
      { id: 'workflow-monthly', label: 'Monthly Review' },
      { id: 'workflow-setup', label: 'Setup After Sync' },
    ],
  },
  {
    id: 'glossary',
    label: 'Glossary',
    icon: BookOpen,
    items: [{ id: 'glossary', label: 'All Terms' }],
  },
]

/** Flat list of every navigable section id */
const ALL_SECTION_IDS = SIDEBAR_SECTIONS.flatMap(g => g.items.map(i => i.id))

/* ---------- helper components ---------- */

/** A styled box for visual formulas */
function FormulaBox({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center px-3 py-1.5 rounded-lg bg-muted text-sm font-medium text-foreground ${className}`}>
      {children}
    </span>
  )
}

/** Operator symbol between formula boxes */
function FormulaOp({ children }: { children: React.ReactNode }) {
  return (
    <span className="mx-2 text-muted-foreground font-bold text-base">{children}</span>
  )
}

/** A numbered step circle */
function StepCircle({ n }: { n: number }) {
  return (
    <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
      {n}
    </span>
  )
}

/** A flow arrow between step items */
function FlowArrow() {
  return <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
}

/* ---------- component ---------- */

export default function Help() {
  const isMobile = useIsMobile()
  const [activeSection, setActiveSection] = useState(ALL_SECTION_IDS[0])

  /* scroll-to-hash on mount */
  useEffect(() => {
    const hash = window.location.hash.replace('#', '')
    if (hash) {
      // small delay so the DOM is rendered
      requestAnimationFrame(() => {
        const el = document.getElementById(hash)
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' })
          setActiveSection(hash)
        }
      })
    }
  }, [])

  /* scroll-spy — listen on window since the page itself scrolls, not the content div */
  useEffect(() => {
    // Cache element refs once — the help page doesn't add/remove sections
    const sectionEls = ALL_SECTION_IDS
      .map(id => ({ id, el: document.getElementById(id) }))
      .filter((s): s is { id: string; el: HTMLElement } => s.el !== null)

    let rafId: number | null = null
    const handleScroll = () => {
      if (rafId) return
      rafId = requestAnimationFrame(() => {
        rafId = null
        for (const section of [...sectionEls].reverse()) {
          const rect = section.el.getBoundingClientRect()
          if (rect.top <= 200) {
            setActiveSection(prev => prev === section.id ? prev : section.id)
            break
          }
        }
      })
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', handleScroll)
      if (rafId) cancelAnimationFrame(rafId)
    }
  }, [])

  const scrollToSection = (id: string) => {
    setActiveSection(id)
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    // update URL hash without a full navigation
    window.history.replaceState(null, '', `#${id}`)
  }

  /* ---------- page guide data ---------- */
  const pageGuides: { id: string; icon: React.ElementType; name: string; desc: string; to: string }[] = [
    { id: 'page-home', icon: LayoutDashboard, name: 'Home', desc: 'Summary cards, sync status, and overall inventory health at a glance.', to: '/' },
    { id: 'page-brands', icon: Package, name: 'Brands', desc: 'Every brand with aggregated metrics. Sort by critical count to find hot spots.', to: '/brands' },
    { id: 'page-sku-detail', icon: Search, name: 'SKU Detail', desc: 'Per-item stock timeline, velocity breakdown, and calculation details.', to: '/brands' },
    { id: 'page-critical', icon: ShieldAlert, name: 'Critical SKUs', desc: 'Cross-brand view of every SKU below reorder threshold, sorted by urgency.', to: '/critical' },
    { id: 'page-po-builder', icon: ClipboardList, name: 'Build PO', desc: 'Assemble purchase orders with pre-filled quantities and export to Excel.', to: '/po' },
    { id: 'page-dead-stock', icon: Snowflake, name: 'Dead Stock', desc: 'Items with zero sales activity. Candidates for markdown or discontinuation.', to: '/brands' },
    { id: 'page-parties', icon: Users, name: 'Parties', desc: 'Classify every Tally party into wholesale, online, or store channels.', to: '/parties' },
    { id: 'page-suppliers', icon: Truck, name: 'Suppliers', desc: 'Manage supplier records and lead times that feed reorder calculations.', to: '/suppliers' },
    { id: 'page-overrides', icon: Pencil, name: 'Overrides', desc: 'Review all active overrides. Stale ones are flagged for refresh.', to: '/overrides' },
    { id: 'page-settings', icon: Settings, name: 'Settings', desc: 'Configure buffers, velocity method, dead stock thresholds, and rules.', to: '/settings' },
  ]

  /* ---------- glossary data ---------- */
  const glossaryItems = [
    { term: 'ABC Classification', definition: 'Revenue grouping: A = top 80%, B = next 15%, C = bottom 5%.', anchor: 'abc-classification' },
    { term: 'Buffer', definition: 'Extra stock days beyond lead time, scaled by ABC class.', anchor: 'lead-time-buffer' },
    { term: 'Channel', definition: 'Demand track: wholesale, online, or store.', anchor: 'three-channels' },
    { term: 'Coverage Period', definition: 'Days of stock an order provides after arrival. Auto-calculated from lead time or set per supplier. Adjustable per-PO.', anchor: 'lead-time-buffer' },
    { term: 'Critical', definition: 'Days left < lead time + buffer. Order now.', anchor: 'stockout-projection' },
    { term: 'Days Left', definition: 'Stock / velocity = time until stockout.', anchor: 'stockout-projection' },
    { term: 'Dead Stock', definition: 'No sales for longer than the threshold (default 30 days).', anchor: 'page-dead-stock' },
    { term: 'Lead Time', definition: 'Days from order to delivery. Set per supplier.', anchor: 'lead-time-buffer' },
    { term: 'Override', definition: 'Manual adjustment to velocity or stock. Requires a reason.', anchor: 'overrides' },
    { term: 'Party', definition: 'Customer or supplier name from Tally.', anchor: 'channel-classification' },
    { term: 'Reorder Qty', definition: '(velocity x coverage) - current stock.', anchor: 'reorder-quantity' },
    { term: 'Staleness', definition: 'Override is stale when system data has drifted.', anchor: 'overrides' },
    { term: 'Velocity', definition: 'Units sold per day, excluding out-of-stock days.', anchor: 'velocity' },
    { term: 'WMA', definition: 'Weighted Moving Average. More weight on recent sales.', anchor: 'velocity' },
    { term: 'XYZ Class', definition: 'Demand variability: X = stable, Y = variable, Z = erratic.', anchor: 'abc-classification' },
  ]

  /* ---------- build flat TOC options for mobile ---------- */
  const tocOptions = SIDEBAR_SECTIONS.flatMap(group =>
    group.items.map(item => ({
      id: item.id,
      label: `${group.label} - ${item.label}`,
    }))
  )

  /* ---------- render ---------- */
  return (
    <div className={isMobile ? 'space-y-4 px-4 py-4' : 'space-y-6'}>
      {/* Page Header */}
      {!isMobile && (
        <div className="flex items-center gap-3">
          <BookOpen className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Help &amp; Reference</h2>
        </div>
      )}

      {/* Mobile: sticky TOC dropdown */}
      {isMobile && (
        <div className="sticky top-0 z-20 bg-background pb-2 -mx-4 px-4 pt-1 border-b">
          <Select value={activeSection} onValueChange={v => {
            if (v) scrollToSection(v)
          }}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Jump to section..." />
            </SelectTrigger>
            <SelectContent>
              {tocOptions.map(opt => (
                <SelectItem key={opt.id} value={opt.id}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Layout: sidebar + content */}
      <div className={isMobile ? '' : 'flex gap-6'}>
        {/* Sidebar — desktop only */}
        {!isMobile && (
          <nav className="w-[200px] shrink-0 space-y-4 sticky top-6 self-start max-h-[calc(100vh-6rem)] overflow-y-auto">
            {SIDEBAR_SECTIONS.map(({ id, label, icon: Icon, items }) => (
              <div key={id} className="space-y-0.5">
                <div className="flex items-center gap-2 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  {label}
                </div>
                {items.map(item => (
                  <button
                    key={item.id}
                    onClick={() => scrollToSection(item.id)}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors text-left ${
                      activeSection === item.id
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            ))}
          </nav>
        )}

        {/* Content Area */}
        <div className={`${isMobile ? '' : 'flex-1'} space-y-10 min-w-0`}>

          {/* ============================================================
              GETTING STARTED
             ============================================================ */}
          <section id="getting-started" className="scroll-mt-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">Getting Started</h3>
            <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-3'} gap-4`}>
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-blue-50">
                      <Package className="h-5 w-5 text-blue-600" />
                    </div>
                    <CardTitle className="text-sm">What It Does</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Tracks 22,000+ SKUs across 167 brands. Tells you what to reorder and when.
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-green-50">
                      <Database className="h-5 w-5 text-green-600" />
                    </div>
                    <CardTitle className="text-sm">Data Source</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Syncs nightly from Tally Prime. Stock levels, transactions, and party data.
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-purple-50">
                      <Users className="h-5 w-5 text-purple-600" />
                    </div>
                    <CardTitle className="text-sm">Built For</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    The purchasing team. Daily ordering, weekly dead stock review, monthly cleanup.
                  </p>
                </CardContent>
              </Card>
            </div>
          </section>

          <Separator />

          {/* ============================================================
              THE BIG PICTURE — VISUAL FLOW
             ============================================================ */}
          <section className="scroll-mt-6">
            <h3 className="text-lg font-semibold text-foreground mb-4">The Big Picture</h3>
            <Card>
              <CardContent className="py-2">
                {/* Main flow */}
                <div className="flex items-center justify-center gap-2 flex-wrap py-4">
                  <button onClick={() => scrollToSection('three-channels')} className="px-3 py-2 rounded-lg bg-blue-50 border border-blue-200 text-sm font-medium text-blue-700 hover:bg-blue-100 transition-colors cursor-pointer">
                    3 Channels
                  </button>
                  <FlowArrow />
                  <button onClick={() => scrollToSection('velocity')} className="px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-sm font-medium text-emerald-700 hover:bg-emerald-100 transition-colors cursor-pointer">
                    Velocity / Channel
                  </button>
                  <FlowArrow />
                  <button onClick={() => scrollToSection('stockout-projection')} className="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-sm font-medium text-amber-700 hover:bg-amber-100 transition-colors cursor-pointer">
                    Stockout Projection
                  </button>
                  <FlowArrow />
                  <button onClick={() => scrollToSection('reorder-quantity')} className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm font-medium text-red-700 hover:bg-red-100 transition-colors cursor-pointer">
                    Reorder Quantity
                  </button>
                  <FlowArrow />
                  <button onClick={() => scrollToSection('page-po-builder')} className="px-3 py-2 rounded-lg bg-purple-50 border border-purple-200 text-sm font-medium text-purple-700 hover:bg-purple-100 transition-colors cursor-pointer">
                    Purchase Order
                  </button>
                </div>
                {/* Supporting concepts */}
                <div className="flex items-center justify-center gap-8 pb-2 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground">Feeds into channels:</span>
                    <button onClick={() => scrollToSection('channel-classification')} className="px-2 py-1 rounded bg-slate-100 border border-slate-200 font-medium text-slate-600 hover:bg-slate-200 transition-colors cursor-pointer">
                      Party Classification
                    </button>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-muted-foreground">Feeds into projection:</span>
                    <button onClick={() => scrollToSection('lead-time-buffer')} className="px-2 py-1 rounded bg-slate-100 border border-slate-200 font-medium text-slate-600 hover:bg-slate-200 transition-colors cursor-pointer">
                      Lead Time + ABC Buffer
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </section>

          <Separator />

          {/* ============================================================
              KEY CONCEPTS
             ============================================================ */}
          <div className="space-y-8">
            <h3 className="text-lg font-semibold text-foreground">Key Concepts</h3>

            {/* --- Three Channels --- */}
            <section id="three-channels" className="space-y-4 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Three Parallel Demand Tracks</h4>
              <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-3'} gap-4`}>
                <Card className="bg-blue-50/50 border-blue-200 ring-blue-200">
                  <CardHeader>
                    <CardTitle className="text-sm text-blue-800">Wholesale</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <p className="text-sm text-blue-700">B2B retailers &amp; institutions</p>
                    <p className="text-xs text-blue-600/70">50-500 units per order</p>
                    <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100 mt-1">Low predictability</Badge>
                  </CardContent>
                </Card>

                <Card className="bg-green-50/50 border-green-200 ring-green-200">
                  <CardHeader>
                    <CardTitle className="text-sm text-green-800">Online</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <p className="text-sm text-green-700">Magento, Amazon, Flipkart</p>
                    <p className="text-xs text-green-600/70">1-3 units/day steady</p>
                    <Badge className="bg-green-100 text-green-700 hover:bg-green-100 mt-1">Most predictable</Badge>
                  </CardContent>
                </Card>

                <Card className="bg-amber-50/50 border-amber-200 ring-amber-200">
                  <CardHeader>
                    <CardTitle className="text-sm text-amber-800">Store</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <p className="text-sm text-amber-700">Walk-in customers</p>
                    <p className="text-xs text-amber-600/70">Moderate volume</p>
                    <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100 mt-1">Somewhat seasonal</Badge>
                  </CardContent>
                </Card>
              </div>

              <div className="flex gap-3 items-start bg-muted/50 rounded-lg px-4 py-3">
                <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                <p className="text-sm text-muted-foreground">
                  All three drain the same inventory. A wholesale spike of 200 units and 200 individual
                  online sales look the same in totals but mean very different things for forecasting.
                </p>
              </div>
            </section>

            {/* --- Velocity --- */}
            <section id="velocity" className="space-y-4 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Velocity</h4>

              {/* Visual formula */}
              <Card>
                <CardContent className="py-2">
                  <div className="flex items-center justify-center gap-1 flex-wrap py-3">
                    <FormulaBox className="bg-blue-50 text-blue-700">Units Sold</FormulaBox>
                    <FormulaOp>/</FormulaOp>
                    <FormulaBox className="bg-emerald-50 text-emerald-700">In-Stock Days</FormulaBox>
                    <FormulaOp>=</FormulaOp>
                    <FormulaBox className="bg-purple-50 text-purple-700 font-semibold">Daily Velocity</FormulaBox>
                  </div>
                </CardContent>
              </Card>

              {/* Flat vs WMA comparison */}
              <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-2'} gap-4`}>
                <Card size="sm">
                  <CardContent>
                    <p className="text-sm font-medium text-foreground mb-1">Flat Average</p>
                    <p className="text-xs text-muted-foreground">Treats all days equally. Simple and stable.</p>
                  </CardContent>
                </Card>
                <Card size="sm">
                  <CardContent>
                    <p className="text-sm font-medium text-foreground mb-1">WMA (Weighted Moving Average)</p>
                    <p className="text-xs text-muted-foreground">More weight on recent sales. Responds to demand shifts.</p>
                  </CardContent>
                </Card>
              </div>

              {/* Trend arrows */}
              <div className="flex items-center gap-6 text-sm">
                <span className="text-muted-foreground font-medium">Trend indicators:</span>
                <span className="flex items-center gap-1.5 text-green-600">
                  <TrendingUp className="h-4 w-4" /> Accelerating
                </span>
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <Minus className="h-4 w-4" /> Flat
                </span>
                <span className="flex items-center gap-1.5 text-red-500">
                  <TrendingDown className="h-4 w-4" /> Decelerating
                </span>
              </div>
            </section>

            {/* --- ABC Classification --- */}
            <section id="abc-classification" className="space-y-3 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">ABC Classification</h4>

              <div className="space-y-2">
                {/* A tier */}
                <div className="flex items-center gap-3">
                  <Badge className="bg-red-100 text-red-700 hover:bg-red-100 w-8 justify-center">A</Badge>
                  <div className="flex-1 h-3 rounded-full bg-red-100 relative overflow-hidden">
                    <div className="absolute inset-y-0 left-0 w-[80%] bg-red-500 rounded-full" />
                  </div>
                  <span className="text-sm text-muted-foreground w-[280px] shrink-0">Top 80% revenue — highest priority, buffer 1.5x</span>
                </div>
                {/* B tier */}
                <div className="flex items-center gap-3">
                  <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100 w-8 justify-center">B</Badge>
                  <div className="flex-1 h-3 rounded-full bg-amber-100 relative overflow-hidden">
                    <div className="absolute inset-y-0 left-0 w-[55%] bg-amber-500 rounded-full" />
                  </div>
                  <span className="text-sm text-muted-foreground w-[280px] shrink-0">Next 15% revenue — moderate priority, buffer 1.0x</span>
                </div>
                {/* C tier */}
                <div className="flex items-center gap-3">
                  <Badge className="bg-gray-100 text-gray-600 hover:bg-gray-100 w-8 justify-center">C</Badge>
                  <div className="flex-1 h-3 rounded-full bg-gray-100 relative overflow-hidden">
                    <div className="absolute inset-y-0 left-0 w-[25%] bg-gray-400 rounded-full" />
                  </div>
                  <span className="text-sm text-muted-foreground w-[280px] shrink-0">Bottom 5% + zero — minimal priority, buffer 0.5x</span>
                </div>
              </div>
            </section>

            {/* --- Lead Time & Buffer --- */}
            <section id="lead-time-buffer" className="space-y-4 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Lead Time &amp; Buffer</h4>

              <Card>
                <CardContent className="py-2">
                  <div className="flex items-center justify-center gap-1 flex-wrap py-3">
                    <FormulaBox className="bg-blue-50 text-blue-700">Lead Time (days to arrive)</FormulaBox>
                    <FormulaOp>+</FormulaOp>
                    <FormulaBox className="bg-cyan-50 text-cyan-700">Coverage Period (days after arrival)</FormulaBox>
                    <FormulaOp>=</FormulaOp>
                    <FormulaBox className="bg-purple-50 text-purple-700 font-semibold">Total Coverage</FormulaBox>
                  </div>
                </CardContent>
              </Card>

              <div className="flex gap-3 items-start bg-muted/50 rounded-lg px-4 py-3">
                <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                <p className="text-sm text-muted-foreground">
                  Coverage period = how many months of stock each order provides after arrival.
                  Auto-calculated from lead time (turns per year) or set per supplier. Adjustable per-PO in the PO Builder.
                </p>
              </div>
            </section>

            {/* --- Stockout Projection --- */}
            <section id="stockout-projection" className="space-y-4 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Stockout Projection</h4>

              <Card>
                <CardContent className="py-2">
                  <div className="flex items-center justify-center gap-1 flex-wrap py-3">
                    <FormulaBox className="bg-blue-50 text-blue-700">Current Stock</FormulaBox>
                    <FormulaOp>/</FormulaOp>
                    <FormulaBox className="bg-emerald-50 text-emerald-700">Daily Velocity</FormulaBox>
                    <FormulaOp>=</FormulaOp>
                    <FormulaBox className="bg-purple-50 text-purple-700 font-semibold">Days Left</FormulaBox>
                  </div>
                </CardContent>
              </Card>

              {/* Status badges */}
              <div className="grid grid-cols-1 gap-2">
                <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-red-50/50 border border-red-100">
                  <Badge className="bg-red-100 text-red-700 hover:bg-red-100">Critical</Badge>
                  <span className="text-sm text-muted-foreground">Order now. Stock will not last until next shipment arrives.</span>
                </div>
                <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-amber-50/50 border border-amber-100">
                  <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">Warning</Badge>
                  <span className="text-sm text-muted-foreground">Plan your order soon. Approaching reorder threshold.</span>
                </div>
                <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-green-50/50 border border-green-100">
                  <Badge className="bg-green-100 text-green-700 hover:bg-green-100">OK</Badge>
                  <span className="text-sm text-muted-foreground">Comfortable runway. No action needed right now.</span>
                </div>
                <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-slate-50 border border-slate-200">
                  <Badge className="bg-slate-700 text-white hover:bg-slate-700">Out of Stock</Badge>
                  <span className="text-sm text-muted-foreground">Zero inventory on hand.</span>
                </div>
                <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-gray-50 border border-gray-200">
                  <Badge className="bg-gray-100 text-gray-500 hover:bg-gray-100">No Data</Badge>
                  <span className="text-sm text-muted-foreground">Not enough sales history to project.</span>
                </div>
              </div>
            </section>

            {/* --- Reorder Quantity --- */}
            <section id="reorder-quantity" className="space-y-4 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Reorder Quantity</h4>

              <Card>
                <CardContent className="py-2">
                  <div className="flex items-center justify-center gap-1 flex-wrap py-3">
                    <FormulaOp>(</FormulaOp>
                    <FormulaBox className="bg-emerald-50 text-emerald-700">Velocity</FormulaBox>
                    <FormulaOp>x</FormulaOp>
                    <FormulaBox className="bg-purple-50 text-purple-700">Total Coverage</FormulaBox>
                    <FormulaOp>x</FormulaOp>
                    <FormulaBox className="bg-amber-50 text-amber-700">Safety Buffer</FormulaBox>
                    <FormulaOp>)</FormulaOp>
                    <FormulaOp>-</FormulaOp>
                    <FormulaBox className="bg-blue-50 text-blue-700">Current Stock</FormulaBox>
                    <FormulaOp>=</FormulaOp>
                    <FormulaBox className="bg-red-50 text-red-700 font-semibold">Order Qty</FormulaBox>
                  </div>
                  <p className="text-xs text-center text-muted-foreground pb-2">
                    How much to order so stock lasts through lead time plus the coverage period. Adjustable per-PO in the PO Builder.
                  </p>
                </CardContent>
              </Card>
            </section>

            {/* --- Overrides --- */}
            <section id="overrides" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Overrides</h4>
              <Card size="sm">
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    When you know better than the data — override velocity, stock, or add notes.
                    Every override needs a reason and gets flagged when data drifts.
                  </p>
                </CardContent>
              </Card>
            </section>

            {/* --- Channel Classification --- */}
            <section id="channel-classification" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Channel Classification</h4>
              <Card size="sm">
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Classify every Tally party into wholesale / online / store on the{' '}
                    <Link to="/parties" className="text-primary hover:underline font-medium">Parties page</Link>.
                    Unclassified parties = inaccurate velocity.
                  </p>
                </CardContent>
              </Card>
            </section>
          </div>

          <Separator />

          {/* ============================================================
              PAGE GUIDES
             ============================================================ */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-foreground">Page Guides</h3>

            <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-2'} gap-3`}>
              {pageGuides.map(({ id, icon: Icon, name, desc, to }) => (
                <section key={id} id={id} className="scroll-mt-6">
                  <Link to={to} className="block group">
                    <Card size="sm" className="transition-colors hover:bg-muted/30">
                      <CardContent>
                        <div className="flex items-start gap-3">
                          <div className="p-1.5 rounded-md bg-muted shrink-0 mt-0.5">
                            <Icon className="h-4 w-4 text-muted-foreground" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-foreground">{name}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
                            <span className="inline-flex items-center gap-1 text-xs text-primary mt-1.5 group-hover:underline">
                              Go to page <ArrowRight className="h-3 w-3" />
                            </span>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                </section>
              ))}
            </div>
          </div>

          <Separator />

          {/* ============================================================
              DAILY WORKFLOWS
             ============================================================ */}
          <div className="space-y-6">
            <h3 className="text-lg font-semibold text-foreground">Daily Workflows</h3>

            {/* Morning Check */}
            <section id="workflow-morning" className="space-y-3 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Morning Check</h4>
              <p className="text-sm text-muted-foreground">Check sync status, review critical items, and build POs for anything urgent.</p>
              <div className="flex items-center gap-3 flex-wrap">
                <StepCircle n={1} />
                <span className="text-sm">Home</span>
                <FlowArrow />
                <StepCircle n={2} />
                <span className="text-sm">Critical SKUs</span>
                <FlowArrow />
                <StepCircle n={3} />
                <span className="text-sm">PO Builder</span>
                <FlowArrow />
                <StepCircle n={4} />
                <span className="text-sm">Export</span>
              </div>
            </section>

            {/* Deep Dive */}
            <section id="workflow-deep-dive" className="space-y-3 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Deep Dive</h4>
              <p className="text-sm text-muted-foreground">Investigate a specific SKU. View timeline, verify calculations, add overrides.</p>
              <div className="flex items-center gap-3 flex-wrap">
                <StepCircle n={1} />
                <span className="text-sm">Search / Brands</span>
                <FlowArrow />
                <StepCircle n={2} />
                <span className="text-sm">SKU Detail</span>
                <FlowArrow />
                <StepCircle n={3} />
                <span className="text-sm">Timeline</span>
                <FlowArrow />
                <StepCircle n={4} />
                <span className="text-sm">Calculation</span>
                <FlowArrow />
                <StepCircle n={5} />
                <span className="text-sm">Override</span>
              </div>
            </section>

            {/* Monthly Review */}
            <section id="workflow-monthly" className="space-y-3 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Monthly Review</h4>
              <p className="text-sm text-muted-foreground">Clean up stale overrides, review dead stock, classify new parties.</p>
              <div className="flex items-center gap-3 flex-wrap">
                <StepCircle n={1} />
                <span className="text-sm">Overrides</span>
                <FlowArrow />
                <StepCircle n={2} />
                <span className="text-sm">Dead Stock</span>
                <FlowArrow />
                <StepCircle n={3} />
                <span className="text-sm">Parties</span>
              </div>
            </section>

            {/* Setup After Sync */}
            <section id="workflow-setup" className="space-y-3 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Setup After Sync</h4>
              <p className="text-sm text-muted-foreground">When the banner warns about unclassified parties, classify them immediately.</p>
              <div className="flex items-center gap-3 flex-wrap">
                <StepCircle n={1} />
                <span className="text-sm">Notice banner</span>
                <FlowArrow />
                <StepCircle n={2} />
                <span className="text-sm">Parties</span>
                <FlowArrow />
                <StepCircle n={3} />
                <span className="text-sm">Classify all</span>
              </div>
            </section>
          </div>

          <Separator />

          {/* ============================================================
              GLOSSARY
             ============================================================ */}
          <section id="glossary" className="space-y-4 scroll-mt-6">
            <h3 className="text-lg font-semibold text-foreground">Glossary</h3>

            <div className={`grid ${isMobile ? 'grid-cols-1' : 'grid-cols-2'} gap-2`}>
              {glossaryItems.map(({ term, definition, anchor }) => (
                <button
                  key={term}
                  onClick={() => scrollToSection(anchor)}
                  className="flex items-start gap-3 px-3 py-2.5 rounded-lg border border-border/50 text-left hover:bg-muted/30 transition-colors cursor-pointer"
                >
                  <span className="text-sm font-medium text-foreground whitespace-nowrap">{term}</span>
                  <span className="text-xs text-muted-foreground flex-1">{definition}</span>
                </button>
              ))}
            </div>
          </section>

          {/* bottom spacer */}
          <div className="h-16" />
        </div>
      </div>
    </div>
  )
}
