import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Separator } from '@/components/ui/separator'
import { Rocket, Lightbulb, Layout, CalendarCheck, BookOpen, ArrowRight } from 'lucide-react'

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

/* ---------- component ---------- */

export default function Help() {
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

  /* ---------- render ---------- */
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-3">
        <BookOpen className="h-5 w-5 text-muted-foreground" />
        <h2 className="text-xl font-semibold">Help &amp; Reference</h2>
      </div>

      {/* Layout: sidebar + content */}
      <div className="flex gap-6">
        {/* Sidebar */}
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

        {/* Content Area */}
        <div className="flex-1 space-y-10 min-w-0">

          {/* ============================================================
              GETTING STARTED
             ============================================================ */}
          <section id="getting-started">
            <h3 className="text-lg font-semibold text-foreground mb-3">Getting Started</h3>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Stock Intelligence tracks every SKU Art Lounge carries, monitors how fast each one is
              selling across wholesale, online, and store channels, and tells you when to reorder and
              how much. All data syncs nightly from Tally Prime. The system pulls stock levels,
              transactions, and party information, then calculates velocities, projects stockout
              dates, and generates reorder suggestions. Built for the purchasing and inventory team
              &mdash; use it daily to check what needs ordering, weekly to review dead stock and
              overrides, and whenever you are building a purchase order.
            </p>
          </section>

          <Separator />

          {/* ============================================================
              KEY CONCEPTS
             ============================================================ */}
          <div className="space-y-8">
            <h3 className="text-lg font-semibold text-foreground">Key Concepts</h3>

            {/* --- Three Channels --- */}
            <section id="three-channels" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Three Parallel Demand Tracks</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Art Lounge serves three markets simultaneously, each with its own demand pattern.
                <strong className="text-foreground"> Wholesale</strong> covers B2B retailers and
                institutions &mdash; large irregular orders (50&ndash;500 units) with low predictability.
                <strong className="text-foreground"> Online</strong> (Magento, Amazon, Flipkart) serves
                individual consumers &mdash; a steady trickle of 1&ndash;3 units per day that is the most
                predictable channel.
                <strong className="text-foreground"> Store</strong> (physical retail) handles walk-in
                customers with moderate volume and somewhat seasonal patterns.
              </p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                All three draw from the same physical stock. The system tracks them as parallel
                pipelines: each gets its own velocity, and the total velocity is the sum of all three
                (the combined drain rate). If total velocity is 5 units/day, it matters whether that
                is 4 wholesale + 0.5 online + 0.5 store (risky &mdash; one client could stop buying)
                versus 1 wholesale + 3 online + 1 store (stable consumer demand).
              </p>
            </section>

            {/* --- Velocity --- */}
            <section id="velocity" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Velocity</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Velocity is the number of units sold per day, counting only days when the item was in
                stock. Out-of-stock days are excluded so velocity reflects actual demand, not supply
                gaps. <strong className="text-foreground">Flat velocity</strong> treats all days
                equally &mdash; a simple average. <strong className="text-foreground">WMA (Weighted
                Moving Average)</strong> gives more weight to recent sales, making it more responsive
                to changes in demand. The <strong className="text-foreground">trend indicator</strong>{' '}
                compares recent 90-day WMA to the yearly average so you can spot accelerating or
                decelerating demand at a glance.
              </p>
            </section>

            {/* --- ABC Classification --- */}
            <section id="abc-classification" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">ABC Classification</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                <strong className="text-foreground">A-class:</strong> the top 80% of revenue &mdash;
                highest priority items that deserve the largest safety buffers.{' '}
                <strong className="text-foreground">B-class:</strong> the next 15% of revenue &mdash;
                moderate priority.{' '}
                <strong className="text-foreground">C-class:</strong> the bottom 5% plus zero-revenue
                items &mdash; minimal buffers. ABC classification drives reorder priority: A-class
                critical items are surfaced and flagged first.
              </p>
            </section>

            {/* --- Lead Time & Buffer --- */}
            <section id="lead-time-buffer" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Lead Time &amp; Buffer</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                <strong className="text-foreground">Lead time</strong> is the number of days from
                placing an order to receiving the goods &mdash; typically 90&ndash;180 days by sea for
                imports. The <strong className="text-foreground">buffer</strong> is a safety-stock
                multiplier that varies by ABC class: A-class 1.5x, B-class 1.0x, C-class 0.5x. The
                balancing act: too little buffer means stockouts between shipments; too much means
                capital locked in unsold inventory. Lead times are set per supplier on the Suppliers
                page.
              </p>
            </section>

            {/* --- Stockout Projection --- */}
            <section id="stockout-projection" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Stockout Projection</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                The formula is straightforward: current stock divided by total daily velocity equals
                days remaining.{' '}
                <strong className="text-foreground">Critical</strong> means days remaining is less
                than lead time plus buffer &mdash; you need to order now.{' '}
                <strong className="text-foreground">Warning</strong> means you are approaching the
                threshold.{' '}
                <strong className="text-foreground">OK</strong> means you have comfortable runway.{' '}
                <strong className="text-foreground">Out of Stock</strong> means zero inventory on
                hand.{' '}
                <strong className="text-foreground">No Data</strong> means there is insufficient
                sales history to make a projection.
              </p>
            </section>

            {/* --- Reorder Quantity --- */}
            <section id="reorder-quantity" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Reorder Quantity</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Formula: <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                (velocity x (lead_time + buffer_days)) - current_stock</code>. In plain English:
                &ldquo;How much to order so you don&rsquo;t run out before the next shipment
                arrives.&rdquo; The PO Builder page uses this formula to pre-fill quantities, which
                you can then adjust before exporting.
              </p>
            </section>

            {/* --- Overrides --- */}
            <section id="overrides" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Overrides</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Override velocity, stock level, or add notes when you know something the system does
                not &mdash; a big order coming, a product being discontinued, or a seasonal shift.
                Every override requires a reason so the team understands why the numbers were changed.
                The system flags &ldquo;stale&rdquo; overrides when the underlying data drifts
                significantly from the overridden value, prompting you to review and refresh.
              </p>
            </section>

            {/* --- Channel Classification --- */}
            <section id="channel-classification" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Channel Classification</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Every Tally transaction has a party name. Each party must be classified into one of
                six channels: wholesale, online, store, supplier, internal, or ignore. This
                classification drives channel-level velocity separation. You manage classifications on
                the <Link to="/parties" className="text-primary hover:underline">Parties</Link> page.
                Unclassified parties trigger a warning banner on the Home page &mdash; classify them
                promptly so velocity calculations stay accurate.
              </p>
            </section>
          </div>

          <Separator />

          {/* ============================================================
              PAGE GUIDES
             ============================================================ */}
          <div className="space-y-8">
            <h3 className="text-lg font-semibold text-foreground">Page Guides</h3>

            <section id="page-home" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Home</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                The Home page is your dashboard landing screen. It shows summary cards with total
                SKUs, critical counts, out-of-stock counts, and the last sync timestamp. Use it as
                your daily starting point to see the overall health of inventory at a glance. Tip:
                click any summary card to jump straight to the filtered view (e.g., clicking
                &ldquo;Critical&rdquo; takes you to the Critical SKUs page).
              </p>
            </section>

            <section id="page-brands" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Brands</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                The Brands page lists every brand (stock category from Tally) with aggregated metrics:
                total SKUs, critical count, out-of-stock count, and revenue. Click any brand row to
                drill into its SKUs. You can sort by any column and search by brand name. Tip: sort
                by &ldquo;Critical&rdquo; descending to find brands that need the most attention
                right now.
              </p>
            </section>

            <section id="page-sku-detail" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">SKU Detail</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                The SKU Detail page shows every item within a brand. Each row displays Part No, SKU
                name, current stock, velocity (total and per-channel), days left, reorder status, and
                ABC class. Click any row to expand the stock timeline chart and transaction history.
                Tip: use the calculation breakdown button to see exactly how days-left and reorder
                quantity were computed for any SKU.
              </p>
            </section>

            <section id="page-critical" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Critical SKUs</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                A cross-brand view of every SKU whose days-left is below the reorder threshold.
                Items are sorted by urgency so the most critical appear first. Use this page each
                morning to identify what needs ordering immediately. Tip: you can add items directly
                to a purchase order from this page without navigating to the brand first.
              </p>
            </section>

            <section id="page-po-builder" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Build PO (Purchase Order)</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                The PO Builder lets you assemble a purchase order for a specific supplier/brand. It
                pre-fills reorder quantities based on the system&rsquo;s calculations, but you can
                adjust every line. When ready, export to Excel for sharing with suppliers. Tip: build
                POs brand-by-brand so each export maps to a single supplier conversation.
              </p>
            </section>

            <section id="page-dead-stock" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Dead Stock</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Shows items with zero sales activity for longer than the configured threshold (default
                30 days). These are candidates for markdowns, bundling, or discontinuation. The page
                also flags slow movers &mdash; items selling below the slow-mover velocity threshold.
                Tip: review this monthly and update overrides for items you plan to keep despite low
                movement.
              </p>
            </section>

            <section id="page-parties" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Parties</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Every party (customer/supplier) from Tally is listed here with its current channel
                classification. Unclassified parties appear at the top with a warning. Classify each
                party as wholesale, online, store, supplier, internal, or ignore. Tip: after the
                first sync, work through all unclassified parties before relying on channel-level
                velocity numbers.
              </p>
            </section>

            <section id="page-suppliers" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Suppliers</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Manage supplier records and their lead times (sea, air, default). Lead times feed
                directly into the stockout projection and reorder quantity calculations. You can add,
                edit, or delete suppliers and assign brands to them. Tip: set realistic lead times
                &mdash; overly optimistic numbers lead to late reorders and stockouts.
              </p>
            </section>

            <section id="page-overrides" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Overrides</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Review all active overrides in one place. Each override shows who set it, the reason,
                and whether it has gone stale (the underlying system value has drifted). Stale
                overrides should be refreshed or removed. Tip: check this page monthly to clean up
                overrides that are no longer relevant.
              </p>
            </section>

            <section id="page-settings" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Settings</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Configure safety buffer multipliers, default velocity calculation method, default
                date range, dead stock thresholds, and view classification rules. Changes take effect
                on the next nightly sync. Tip: start with the defaults and adjust only after
                reviewing a few weeks of recommendations against actual ordering decisions.
              </p>
            </section>
          </div>

          <Separator />

          {/* ============================================================
              DAILY WORKFLOWS
             ============================================================ */}
          <div className="space-y-8">
            <h3 className="text-lg font-semibold text-foreground">Daily Workflows</h3>

            <section id="workflow-morning" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Morning Check</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Start on the <Link to="/" className="text-primary hover:underline">Home</Link> page
                to see if the nightly sync succeeded and review summary numbers. Then go to{' '}
                <Link to="/critical" className="text-primary hover:underline">Critical SKUs</Link>{' '}
                to see what needs ordering today. For anything urgent, jump to the{' '}
                <Link to="/po" className="text-primary hover:underline">PO Builder</Link>, assemble
                the order, and export to Excel.
              </p>
              <div className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
                <span className="font-medium text-foreground">Flow:</span>
                Home <ArrowRight className="h-3.5 w-3.5 shrink-0" /> Critical SKUs{' '}
                <ArrowRight className="h-3.5 w-3.5 shrink-0" /> PO Builder{' '}
                <ArrowRight className="h-3.5 w-3.5 shrink-0" /> Export
              </div>
            </section>

            <section id="workflow-deep-dive" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Deep Dive</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                When you want to understand a specific SKU, search for it or navigate through{' '}
                <Link to="/brands" className="text-primary hover:underline">Brands</Link>. On the
                SKU Detail page, expand the stock timeline to see how inventory has moved over time.
                Use the calculation breakdown to verify the days-left and reorder math. If you
                disagree with the system&rsquo;s numbers, add an override with a clear reason.
              </p>
              <div className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
                <span className="font-medium text-foreground">Flow:</span>
                Search / Brands <ArrowRight className="h-3.5 w-3.5 shrink-0" /> SKU Detail{' '}
                <ArrowRight className="h-3.5 w-3.5 shrink-0" /> Timeline{' '}
                <ArrowRight className="h-3.5 w-3.5 shrink-0" /> Calculation{' '}
                <ArrowRight className="h-3.5 w-3.5 shrink-0" /> Override
              </div>
            </section>

            <section id="workflow-monthly" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Monthly Review</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Once a month, visit the{' '}
                <Link to="/overrides" className="text-primary hover:underline">Overrides</Link> page
                to clean up stale entries. Then check{' '}
                <Link to="/brands/*/dead-stock" className="text-primary hover:underline">Dead Stock</Link>{' '}
                across brands to identify items for markdown or discontinuation. Finally, review the{' '}
                <Link to="/parties" className="text-primary hover:underline">Parties</Link> page for
                any new unclassified parties that appeared since the last review.
              </p>
              <div className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
                <span className="font-medium text-foreground">Flow:</span>
                Overrides <ArrowRight className="h-3.5 w-3.5 shrink-0" /> Dead Stock{' '}
                <ArrowRight className="h-3.5 w-3.5 shrink-0" /> Parties
              </div>
            </section>

            <section id="workflow-setup" className="space-y-2 scroll-mt-6">
              <h4 className="text-base font-medium text-foreground">Setup After Sync</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">
                After the first sync (or when a banner warns about unclassified parties), go to the{' '}
                <Link to="/parties" className="text-primary hover:underline">Parties</Link> page and
                classify every unclassified party. This is critical because channel-level velocity
                depends on correct party classification. Without it, all sales are lumped together and
                the wholesale/online/store split will be inaccurate.
              </p>
              <div className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
                <span className="font-medium text-foreground">Flow:</span>
                Notice banner <ArrowRight className="h-3.5 w-3.5 shrink-0" /> Parties{' '}
                <ArrowRight className="h-3.5 w-3.5 shrink-0" /> Classify all
              </div>
            </section>
          </div>

          <Separator />

          {/* ============================================================
              GLOSSARY
             ============================================================ */}
          <section id="glossary" className="space-y-4 scroll-mt-6">
            <h3 className="text-lg font-semibold text-foreground">Glossary</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Quick reference for terms used throughout the application.
            </p>

            <div className="border rounded-lg divide-y">
              {[
                {
                  term: 'ABC Classification',
                  definition: 'Revenue-based grouping: A = top 80%, B = next 15%, C = bottom 5%. Drives buffer size and priority.',
                  anchor: 'abc-classification',
                },
                {
                  term: 'Buffer',
                  definition: 'Extra days of stock beyond lead time, scaled by ABC class (A=1.5x, B=1.0x, C=0.5x).',
                  anchor: 'lead-time-buffer',
                },
                {
                  term: 'Channel',
                  definition: 'One of three demand tracks: wholesale, online, or store. Each has independent velocity.',
                  anchor: 'three-channels',
                },
                {
                  term: 'Critical',
                  definition: 'SKU whose days remaining is less than lead time + buffer. Needs immediate reorder.',
                  anchor: 'stockout-projection',
                },
                {
                  term: 'Days Left',
                  definition: 'Current stock divided by total daily velocity. How long until stockout at current sell rate.',
                  anchor: 'stockout-projection',
                },
                {
                  term: 'Dead Stock',
                  definition: 'Items with no sales activity for longer than the dead stock threshold (default 30 days).',
                  anchor: 'page-dead-stock',
                },
                {
                  term: 'Lead Time',
                  definition: 'Days from placing an order to receiving goods. Set per supplier (typically 90-180 days by sea).',
                  anchor: 'lead-time-buffer',
                },
                {
                  term: 'Override',
                  definition: 'Manual adjustment to velocity or stock when you know better than the system. Requires a reason.',
                  anchor: 'overrides',
                },
                {
                  term: 'Party',
                  definition: 'A customer or supplier name from Tally. Must be classified into a channel for velocity separation.',
                  anchor: 'channel-classification',
                },
                {
                  term: 'Reorder Quantity',
                  definition: 'Formula: (velocity x (lead_time + buffer_days)) - current_stock. Pre-filled in PO Builder.',
                  anchor: 'reorder-quantity',
                },
                {
                  term: 'Staleness',
                  definition: 'An override is "stale" when the underlying system value has drifted significantly from the overridden value.',
                  anchor: 'overrides',
                },
                {
                  term: 'Velocity',
                  definition: 'Units sold per day, excluding out-of-stock days. Available as flat average or weighted moving average.',
                  anchor: 'velocity',
                },
                {
                  term: 'WMA',
                  definition: 'Weighted Moving Average — velocity calculation that gives more weight to recent sales periods.',
                  anchor: 'velocity',
                },
                {
                  term: 'XYZ Classification',
                  definition: 'Demand variability grouping: X = stable (CV<0.5), Y = variable (0.5-1.0), Z = unpredictable (CV>1.0).',
                  anchor: 'abc-classification',
                },
              ].map(({ term, definition, anchor }) => (
                <div key={term} className="flex items-start gap-4 px-4 py-3">
                  <span className="text-sm font-medium text-foreground w-[160px] shrink-0">{term}</span>
                  <span className="text-sm text-muted-foreground flex-1">{definition}</span>
                  <button
                    onClick={() => scrollToSection(anchor)}
                    className="text-xs text-primary hover:underline shrink-0 mt-0.5"
                  >
                    Learn more
                  </button>
                </div>
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
