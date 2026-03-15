import { useState, useMemo, useEffect, Fragment } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchCriticalSkus, fetchSettings } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TooltipProvider } from '@/components/ui/tooltip'
import StatusBadge from '@/components/StatusBadge'
import SkuSecondaryLine from '@/components/SkuSecondaryLine'
import VelocityToggle from '@/components/VelocityToggle'
import ClassificationExplainer from '@/components/ClassificationExplainer'
import { Search, ChevronDown, ChevronRight } from 'lucide-react'
import { vel, daysDisplay } from '@/lib/formatters'
import { useIsMobile } from '@/hooks/useIsMobile'
import { MobileListRow, MobileListRowSkeleton } from '@/components/mobile/MobileListRow'
import { FilterButton, FilterDrawer } from '@/components/mobile/FilterDrawer'

const IMMEDIATE_DAYS = 7
const URGENT_DAYS = 30
const DEFAULT_SHOW = 5

type CriticalItem = Record<string, unknown>

function tierOf(item: CriticalItem): 'immediate' | 'urgent' | 'watch' {
  const abc = item.abc_class as string
  const days = item.days_to_stockout as number | null
  const status = item.reorder_status as string

  if (abc === 'A' && status === 'critical' && (days === null || days === 0 || days < IMMEDIATE_DAYS)) {
    return 'immediate'
  }
  if (abc === 'A' && status === 'critical' && days !== null && days >= IMMEDIATE_DAYS && days <= URGENT_DAYS) {
    return 'urgent'
  }
  return 'watch'
}

const tierConfig = {
  immediate: {
    title: 'IMMEDIATE',
    emoji: '🔴',
    color: 'border-red-300 bg-red-50',
    headerColor: 'text-red-700',
    description: 'A-class items with less than 7 days of stock. These are your top revenue drivers about to run out.',
  },
  urgent: {
    title: 'URGENT',
    emoji: '🟠',
    color: 'border-orange-300 bg-orange-50',
    headerColor: 'text-orange-700',
    description: 'A-class items with 7-30 days of stock remaining. Plan POs now to avoid stockout.',
  },
  watch: {
    title: 'WATCH',
    emoji: '🟡',
    color: 'border-yellow-300 bg-yellow-50',
    headerColor: 'text-yellow-700',
    description: 'B/C class critical items and all warnings. Monitor and include in next PO cycle.',
  },
}

function TierCard({
  tier,
  items,
  velocityType,
  isMobile,
}: {
  tier: 'immediate' | 'urgent' | 'watch'
  items: CriticalItem[]
  velocityType: 'flat' | 'wma'
  isMobile: boolean
}) {
  const navigate = useNavigate()
  const config = tierConfig[tier]
  const [isExpanded, setIsExpanded] = useState(tier !== 'watch')
  const [showAll, setShowAll] = useState(false)

  if (items.length === 0) return null

  const displayItems = showAll ? items : items.slice(0, DEFAULT_SHOW)

  return (
    <Card className={`border ${config.color}`}>
      <CardHeader
        className="cursor-pointer pb-2"
        onClick={() => setIsExpanded(v => !v)}
      >
        <div className="flex items-center gap-2">
          {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <CardTitle className={`text-sm font-bold ${config.headerColor}`}>
            {config.emoji} {config.title} — {items.length} items
          </CardTitle>
        </div>
        {!isMobile && (
          <p className="text-xs text-muted-foreground ml-6">{config.description}</p>
        )}
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-0">
          {isMobile ? (
            <div className="-mx-4">
              {displayItems.map((r) => {
                const velValue = velocityType === 'wma'
                  ? (r.wma_total_velocity as number || 0)
                  : (r.total_velocity as number || 0)
                const daysLeft = r.days_to_stockout as number | null
                const daysStr = daysLeft === null ? 'N/A' : daysLeft === 0 ? 'OUT' : `${daysLeft}d`
                return (
                  <MobileListRow
                    key={r.stock_item_name as string}
                    title={r.stock_item_name as string}
                    subtitle={r.category_name as string}
                    status={r.reorder_status as string}
                    statusLabel={(r.reorder_status as string).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    metrics={[
                      { label: 'Stk', value: String(r.current_stock as number) },
                      { label: 'Vel', value: vel(velValue) },
                      { label: 'Out', value: daysStr },
                    ]}
                    onClick={() => navigate(`/brands/${encodeURIComponent(r.category_name as string)}/skus`)}
                  />
                )
              })}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[80px]">Status</TableHead>
                  <TableHead className="text-xs">Brand</TableHead>
                  <TableHead>SKU Name</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="text-right">
                    {velocityType === 'wma' ? 'WMA /mo' : 'Vel /mo'}
                  </TableHead>
                  <TableHead className="text-right">Days Left</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayItems.map((r) => {
                  const velValue = velocityType === 'wma'
                    ? (r.wma_total_velocity as number || 0)
                    : (r.total_velocity as number || 0)
                  return (
                    <Fragment key={r.stock_item_name as string}>
                      <TableRow
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => navigate(`/brands/${encodeURIComponent(r.category_name as string)}/skus`)}
                      >
                        <TableCell><StatusBadge status={r.reorder_status as 'critical' | 'warning' | 'ok' | 'out_of_stock' | 'no_data'} /></TableCell>
                        <TableCell className="font-medium text-xs">{r.category_name as string}</TableCell>
                        <TableCell className="max-w-[280px] truncate" title={r.stock_item_name as string}>
                          {r.stock_item_name as string}
                        </TableCell>
                        <TableCell className="text-right">{r.current_stock as number}</TableCell>
                        <TableCell className="text-right">{vel(velValue)}</TableCell>
                        <TableCell className="text-right">{daysDisplay(r.days_to_stockout as number | null)}</TableCell>
                      </TableRow>
                      <TableRow className="border-0">
                        <TableCell colSpan={6} className="pt-0 pb-2 pl-12">
                          <SkuSecondaryLine
                            abc_class={r.abc_class as string}
                            xyz_class={r.xyz_class as string}
                            part_no={r.part_no as string}
                          />
                        </TableCell>
                      </TableRow>
                    </Fragment>
                  )
                })}
              </TableBody>
            </Table>
          )}
          {items.length > DEFAULT_SHOW && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-2 text-muted-foreground"
              onClick={() => setShowAll(v => !v)}
            >
              {showAll ? 'Show less' : `View all ${items.length} items`}
            </Button>
          )}
        </CardContent>
      )}
    </Card>
  )
}

export default function CriticalSkus() {
  const [searchParams] = useSearchParams()
  const isMobile = useIsMobile()

  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || 'critical,warning')
  const [abcFilter, setAbcFilter] = useState<string>(searchParams.get('abc_class') || '')
  const [velocityType, setVelocityType] = useState<'flat' | 'wma'>('flat')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false)
  const pageSize = 500

  // Load analysis defaults from settings
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    staleTime: 5 * 60 * 1000,
  })
  const [settingsApplied, setSettingsApplied] = useState(false)
  useEffect(() => {
    if (settings && !settingsApplied) {
      if (settings.default_velocity_type === 'wma') setVelocityType('wma')
      setSettingsApplied(true)
    }
  }, [settings, settingsApplied])

  const { data, isLoading } = useQuery({
    queryKey: ['criticalSkus', statusFilter, abcFilter, velocityType, page],
    queryFn: () => {
      const params: Record<string, string | number | boolean> = {
        status: statusFilter,
        velocity_type: velocityType,
        limit: pageSize,
        offset: page * pageSize,
      }
      if (abcFilter) params.abc_class = abcFilter
      return fetchCriticalSkus(params)
    },
  })

  const items = data?.items || []
  const total = data?.total ?? 0

  // Client-side search filter
  const filtered = search
    ? items.filter(i =>
        (i.stock_item_name as string)?.toLowerCase().includes(search.toLowerCase()) ||
        (i.category_name as string)?.toLowerCase().includes(search.toLowerCase())
      )
    : items

  // Split into tiers
  const tiers = useMemo(() => {
    const groups: Record<string, CriticalItem[]> = { immediate: [], urgent: [], watch: [] }
    for (const item of filtered) {
      groups[tierOf(item)].push(item)
    }
    return groups
  }, [filtered])

  const activeFilterCount = (statusFilter !== 'critical,warning' ? 1 : 0) + (abcFilter ? 1 : 0)

  if (isMobile) {
    return (
      <TooltipProvider>
        <div className="px-4 py-4 space-y-4">
          <h2 className="text-lg font-semibold">Critical SKUs</h2>

          {/* Search + Filter */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search SKUs or brands..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-9 h-10"
              />
            </div>
            <FilterButton activeCount={activeFilterCount} onClick={() => setFilterDrawerOpen(true)} />
          </div>

          {/* Tiered Groups */}
          {isLoading ? (
            <div className="space-y-0 -mx-4">
              {Array.from({ length: 6 }).map((_, i) => <MobileListRowSkeleton key={i} />)}
            </div>
          ) : (
            <div className="space-y-3">
              {(['immediate', 'urgent', 'watch'] as const).map(tier => (
                <TierCard
                  key={tier}
                  tier={tier}
                  items={tiers[tier]}
                  velocityType={velocityType}
                  isMobile
                />
              ))}

              {filtered.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  No critical SKUs found
                </div>
              )}
            </div>
          )}

          {/* Pagination */}
          {total > pageSize && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {page * pageSize + 1}-{Math.min((page + 1) * pageSize, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                  Prev
                </Button>
                <Button variant="outline" size="sm" disabled={(page + 1) * pageSize >= total} onClick={() => setPage(p => p + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}

          {/* Filter Drawer */}
          <FilterDrawer open={filterDrawerOpen} onOpenChange={setFilterDrawerOpen}>
            <div className="space-y-4">
              <div>
                <div className="text-sm font-medium mb-2">Status</div>
                {[
                  { value: 'critical,warning', label: 'Critical & Warning' },
                  { value: 'critical', label: 'Critical Only' },
                  { value: 'warning', label: 'Warning Only' },
                  { value: 'out_of_stock', label: 'Out of Stock' },
                ].map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => { setStatusFilter(opt.value); setPage(0) }}
                    className={`w-full text-left px-3 py-2.5 rounded text-sm ${statusFilter === opt.value ? 'bg-primary/10 text-primary font-medium' : 'text-foreground'}`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <div>
                <div className="text-sm font-medium mb-2">ABC Class</div>
                {[
                  { value: '', label: 'All Classes' },
                  { value: 'A', label: 'A Class' },
                  { value: 'B', label: 'B Class' },
                  { value: 'C', label: 'C Class' },
                ].map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => { setAbcFilter(opt.value); setPage(0) }}
                    className={`w-full text-left px-3 py-2.5 rounded text-sm ${abcFilter === opt.value ? 'bg-primary/10 text-primary font-medium' : 'text-foreground'}`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </FilterDrawer>
        </div>
      </TooltipProvider>
    )
  }

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Critical SKUs — Triage</h2>
          <div className="flex items-center gap-3">
            <ClassificationExplainer />
            <VelocityToggle value={velocityType} onChange={setVelocityType} />
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search SKUs or brands..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={statusFilter} onValueChange={v => { if (v) { setStatusFilter(v); setPage(0) } }}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Status filter" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="critical,warning">Critical & Warning</SelectItem>
              <SelectItem value="critical">Critical Only</SelectItem>
              <SelectItem value="warning">Warning Only</SelectItem>
              <SelectItem value="out_of_stock">Out of Stock</SelectItem>
            </SelectContent>
          </Select>
          <Select value={abcFilter || 'all'} onValueChange={v => { if (v) { setAbcFilter(v === 'all' ? '' : v); setPage(0) } }}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="ABC Class" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Classes</SelectItem>
              <SelectItem value="A">A Class</SelectItem>
              <SelectItem value="B">B Class</SelectItem>
              <SelectItem value="C">C Class</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Tiered Groups */}
        {isLoading ? (
          <div className="text-center py-12 text-muted-foreground">Loading critical SKUs...</div>
        ) : (
          <div className="space-y-4">
            {(['immediate', 'urgent', 'watch'] as const).map(tier => (
              <TierCard
                key={tier}
                tier={tier}
                items={tiers[tier]}
                velocityType={velocityType}
                isMobile={false}
              />
            ))}

            {filtered.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                No critical SKUs found
              </div>
            )}
          </div>
        )}

        {/* Pagination */}
        {total > pageSize && (
          <div className="border-t px-4 py-3 flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, total)} of {total}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                Previous
              </Button>
              <Button variant="outline" size="sm" disabled={(page + 1) * pageSize >= total} onClick={() => setPage(p => p + 1)}>
                Next
              </Button>
            </div>
          </div>
        )}

        {/* Inline explainer footer */}
        <div className="border rounded-lg bg-muted/30 p-4 text-xs text-muted-foreground space-y-1">
          <p><strong>ABC:</strong> A = top 80% revenue, B = next 15%, C = bottom 5%</p>
          <p><strong>Trends:</strong> ↗ = demand increasing (WMA &gt; flat avg), ↘ = decreasing</p>
          <p><strong>Tiers:</strong> IMMEDIATE = A-class &lt;{IMMEDIATE_DAYS}d, URGENT = A-class {IMMEDIATE_DAYS}-{URGENT_DAYS}d, WATCH = everything else</p>
        </div>
      </div>
    </TooltipProvider>
  )
}
