import { useState, useMemo, useEffect, useCallback, useRef, memo, Fragment } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSkusPage, fetchBrands, fetchSettings } from '@/lib/api'
import type { SkuCounts, SkuMetrics } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import StatusBadge from '@/components/StatusBadge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import StockTimeline from '@/components/StockTimeline'
import CalculationBreakdown from '@/components/CalculationBreakdown'
import ReorderIntentSelector from '@/components/ReorderIntentSelector'
import { Badge } from '@/components/ui/badge'
import AbcBadge from '@/components/AbcBadge'
import VelocityToggle from '@/components/VelocityToggle'
import TrendIndicator from '@/components/TrendIndicator'
import ClassificationExplainer from '@/components/ClassificationExplainer'
import { ArrowLeft, ChevronDown, ChevronRight, FileSpreadsheet, Pencil, AlertTriangle, StickyNote, Calendar, Snowflake, Filter, ArrowUpDown } from 'lucide-react'
import { vel, daysColor } from '@/lib/formatters'
import HelpTip from '@/components/HelpTip'
import { useIsMobile } from '@/hooks/useIsMobile'
import { MobileListRow, MobileListRowSkeleton } from '@/components/mobile/MobileListRow'
import UniversalSearch from '@/components/UniversalSearch'
import { FilterButton, FilterChips, FilterDrawer } from '@/components/mobile/FilterDrawer'
import type { FilterChip } from '@/components/mobile/FilterDrawer'
import { MobileSortSheet } from '@/components/mobile/MobileSortSheet'
import MobileSkuDetail from '@/components/mobile/MobileSkuDetail'

function formatDateForInput(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function getPresetRange(preset: string): { from: string; to: string } | null {
  if (preset === 'full_fy') return null
  const today = new Date()
  const to = formatDateForInput(today)
  let from: Date
  switch (preset) {
    case '6m': from = new Date(today); from.setMonth(from.getMonth() - 6); break
    case '3m': from = new Date(today); from.setMonth(from.getMonth() - 3); break
    case '2m': from = new Date(today); from.setMonth(from.getMonth() - 2); break
    case '30d': from = new Date(today); from.setDate(from.getDate() - 30); break
    default: return null
  }
  return { from: formatDateForInput(from), to }
}

const DEFAULT_COUNTS: SkuCounts = {
  urgent: 0,
  reorder: 0,
  healthy: 0,
  out_of_stock: 0,
  no_data: 0,
  dead_stock: 0,
}

const SkuRow = memo(function SkuRow({
  s,
  isExpanded,
  onToggle,
  decodedName,
  analysisRange,
  velocityType,
  supplierLeadTime,
}: {
  s: SkuMetrics
  isExpanded: boolean
  onToggle: (name: string) => void
  decodedName: string
  analysisRange: { from: string; to: string } | null
  velocityType: 'flat' | 'wma'
  supplierLeadTime?: number
}) {
  const stock = s.effective_stock ?? s.current_stock
  const daysLeft = s.effective_days_to_stockout ?? s.days_to_stockout
  const totalVel = velocityType === 'wma' ? (s.wma_total_velocity ?? 0) : (s.effective_velocity ?? s.total_velocity)
  const wholesaleVel = velocityType === 'wma' ? (s.wma_wholesale_velocity ?? 0) : (s.effective_wholesale_velocity ?? s.wholesale_velocity)
  const onlineVel = velocityType === 'wma' ? (s.wma_online_velocity ?? 0) : (s.effective_online_velocity ?? s.online_velocity)
  const storeVel = s.effective_store_velocity ?? s.store_velocity
  const suggestedQty = s.effective_suggested_qty ?? s.reorder_qty_suggested
  const leadTime = supplierLeadTime ?? 90

  return (
    <Fragment>
      {/* Primary row — 7 columns */}
      <TableRow
        className="cursor-pointer hover:bg-muted/50"
        onClick={() => onToggle(s.stock_item_name)}
      >
        <TableCell>
          {isExpanded
            ? <ChevronDown className="h-4 w-4" />
            : <ChevronRight className="h-4 w-4" />}
        </TableCell>
        <TableCell><StatusBadge status={s.effective_status ?? s.reorder_status} /></TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">{s.stock_item_name}</TableCell>
        <TableCell className="max-w-[280px]" title={s.part_no || s.stock_item_name}>
          <span className="inline-flex items-center gap-1">
            {s.part_no || s.stock_item_name}
            {s.is_hazardous && (
              <Tooltip>
                <TooltipTrigger><span className="text-amber-500 text-xs">{'\u25A0'}</span></TooltipTrigger>
                <TooltipContent>Hazardous material</TooltipContent>
              </Tooltip>
            )}
            {s.reorder_intent === 'must_stock' && (
              <Badge className="bg-purple-100 text-purple-700 hover:bg-purple-100 text-[10px] px-1 py-0">Must Stock</Badge>
            )}
            {s.reorder_intent === 'do_not_reorder' && (
              <Badge className="bg-gray-100 text-gray-500 hover:bg-gray-100 text-[10px] px-1 py-0">DNR</Badge>
            )}
            {s.is_dead_stock && (
              <Tooltip>
                <TooltipTrigger>
                  <Snowflake className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                </TooltipTrigger>
                <TooltipContent>Dead stock — no sales for {s.days_since_last_sale ?? '\u221E'} days</TooltipContent>
              </Tooltip>
            )}
            {s.has_note && (
              <Tooltip>
                <TooltipTrigger>
                  <StickyNote className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                </TooltipTrigger>
                <TooltipContent>Has annotation note</TooltipContent>
              </Tooltip>
            )}
          </span>
        </TableCell>
        <TableCell className={`text-right ${stock <= 0 ? 'text-red-600 font-medium' : ''}`}>
          <span className="inline-flex items-center gap-1 justify-end">
            {stock}
            {s.has_stock_override && (
              <Tooltip>
                <TooltipTrigger>
                  {s.stock_override_stale
                    ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                    : <Pencil className="h-3.5 w-3.5 text-blue-500 shrink-0" />}
                </TooltipTrigger>
                <TooltipContent>
                  Stock override active (computed: {s.current_stock})
                  {s.stock_override_stale && ' \u2014 STALE: data changed'}
                </TooltipContent>
              </Tooltip>
            )}
          </span>
        </TableCell>
        <TableCell className="text-right font-medium">
          <span className="inline-flex items-center gap-1 justify-end">
            {vel(totalVel)}
            <TrendIndicator direction={s.trend_direction} ratio={s.trend_ratio} />
            {s.has_velocity_override && (
              <Tooltip>
                <TooltipTrigger>
                  {s.velocity_override_stale
                    ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                    : <Pencil className="h-3.5 w-3.5 text-blue-500 shrink-0" />}
                </TooltipTrigger>
                <TooltipContent>
                  Velocity override active (computed: {vel(s.total_velocity)}/mo)
                  {s.velocity_override_stale && ' \u2014 STALE'}
                </TooltipContent>
              </Tooltip>
            )}
          </span>
        </TableCell>
        <TableCell className="text-center">
          <AbcBadge value={s.abc_class} />
        </TableCell>
      </TableRow>

      {/* Expanded detail with summary strip */}
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={7} className="bg-muted/30 p-4">
            {/* Summary strip */}
            <div className="grid grid-cols-3 gap-4 mb-4 bg-background rounded-lg border p-4">
              {/* Left: Velocity by Channel */}
              <div>
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Velocity by Channel</h4>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
                      Wholesale
                    </span>
                    <span className="font-medium">{vel(wholesaleVel)}/mo</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-purple-500 inline-block" />
                      Online
                    </span>
                    <span className="font-medium">{vel(onlineVel)}/mo</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                      Store
                    </span>
                    <span className="font-medium">{vel(storeVel)}/mo</span>
                  </div>
                  <div className="flex items-center justify-between text-sm border-t pt-1.5 mt-1.5">
                    <span className="font-semibold">Total</span>
                    <span className="font-semibold inline-flex items-center gap-1">
                      {vel(totalVel)}/mo
                      <TrendIndicator direction={s.trend_direction} ratio={s.trend_ratio} />
                    </span>
                  </div>
                </div>
              </div>

              {/* Middle: Stock & Stockout */}
              <div>
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Stock & Stockout</h4>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span>Units in Stock</span>
                    <span className={`font-semibold ${stock <= 0 ? 'text-red-600' : ''}`}>{stock}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span>Days Left</span>
                    <span className={`font-semibold ${daysColor(daysLeft)}`}>
                      {daysLeft === null ? 'N/A' : daysLeft === 0 ? 'OUT' : `${daysLeft}d`}
                    </span>
                  </div>
                  {s.estimated_stockout_date && (
                    <div className="flex items-center justify-between text-sm">
                      <span>Stockout Date</span>
                      <span className="text-muted-foreground">{s.estimated_stockout_date}</span>
                    </div>
                  )}
                  {s.last_import_date && (
                    <div className="flex items-center justify-between text-sm border-t pt-1.5 mt-1.5">
                      <span>Last Import</span>
                      <span className="text-muted-foreground">{s.last_import_date} ({s.last_import_qty ?? 0} pcs)</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Right: Reorder */}
              <div>
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Reorder</h4>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span>Suggested Qty</span>
                    <span className="font-semibold">{suggestedQty ?? '\u2014'}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span>Lead Time</span>
                    <span className="text-muted-foreground">{leadTime}d</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span>Safety Buffer</span>
                    <span className="text-muted-foreground">{s.safety_buffer}x</span>
                  </div>
                  <div className="flex items-center justify-between text-sm border-t pt-1.5 mt-1.5">
                    <span>Intent</span>
                    <span onClick={e => e.stopPropagation()}>
                      <ReorderIntentSelector
                        stockItemName={s.stock_item_name}
                        currentIntent={s.reorder_intent || 'normal'}
                      />
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="timeline">
              <TabsList>
                <TabsTrigger value="timeline">Timeline & Transactions</TabsTrigger>
                <TabsTrigger value="calculation" data-tour="calculation-tab">Calculation</TabsTrigger>
              </TabsList>
              <TabsContent value="timeline" className="pt-4">
                <div data-tour="stock-timeline">
                  <StockTimeline categoryName={decodedName} stockItemName={s.stock_item_name} />
                </div>
              </TabsContent>
              <TabsContent value="calculation" className="pt-4">
                <CalculationBreakdown
                  categoryName={decodedName}
                  stockItemName={s.stock_item_name}
                  fromDate={analysisRange?.from}
                  toDate={analysisRange?.to}
                />
              </TabsContent>
            </Tabs>
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  )
})

const SKU_SORT_OPTIONS = [
  { value: 'stock_item_name', label: 'Name' },
  { value: 'reorder_status', label: 'Status' },
  { value: 'current_stock', label: 'Stock' },
  { value: 'total_velocity', label: 'Velocity' },
  { value: 'days_to_stockout', label: 'Days to Stockout' },
  { value: 'abc_class', label: 'ABC Class' },
]

export default function SkuDetail() {
  const { categoryName } = useParams<{ categoryName: string }>()
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const decodedName = decodeURIComponent(categoryName || '')

  const [searchParams, setSearchParams] = useSearchParams()
  const [activeSearch, setActiveSearch] = useState<string | null>(null)

  // Capture highlight param into local state whenever URL changes, then clean URL
  // Runs on mount AND when navigating to same route with new highlight (same-brand SKU click)
  const highlightParam = searchParams.get('highlight')
  const prevCategoryRef = useRef(categoryName)
  useEffect(() => {
    if (highlightParam) {
      setActiveSearch(highlightParam)
      setPage(0)
      setSearchParams(prev => {
        prev.delete('highlight')
        return prev
      }, { replace: true })
    } else if (prevCategoryRef.current !== categoryName) {
      // Navigated to a different brand without highlight — clear stale search
      setActiveSearch(null)
      setPage(0)
    }
    prevCategoryRef.current = categoryName
  }, [highlightParam, categoryName, setSearchParams])

  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(100)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  // Mobile-specific state
  const [selectedSku, setSelectedSku] = useState<SkuMetrics | null>(null)
  const [scrollPosition, setScrollPosition] = useState(0)
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false)
  const [mobileSortOpen, setMobileSortOpen] = useState(false)
  const [mobileSortCol, setMobileSortCol] = useState('reorder_status')
  const [mobileSortDir, setMobileSortDir] = useState<'asc' | 'desc'>('desc')

  // V2 controls
  const [velocityType, setVelocityType] = useState<'flat' | 'wma'>('flat')
  const [abcFilter, setAbcFilter] = useState('')
  const [hideInactive, setHideInactive] = useState(true)

  // More filters collapse
  const [showMoreFilters, setShowMoreFilters] = useState(false)
  const [xyzFilter, setXyzFilter] = useState('')
  const [hazardousFilter, setHazardousFilter] = useState(false)
  const [deadStockFilter, setDeadStockFilter] = useState(false)
  const [intentFilter, setIntentFilter] = useState('')

  // Count of active hidden filters
  const hiddenFilterCount = [
    xyzFilter,
    hazardousFilter,
    deadStockFilter,
    intentFilter,
    !hideInactive,
  ].filter(Boolean).length

  // Analysis date range state
  const [rangePreset, setRangePreset] = useState('full_fy')

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
      if (settings.default_date_range && settings.default_date_range !== 'full_fy') {
        setRangePreset(settings.default_date_range)
      }
      setSettingsApplied(true)
    }
  }, [settings, settingsApplied])
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')

  const analysisRange = useMemo(() => {
    if (rangePreset === 'custom') {
      if (customFrom || customTo) return { from: customFrom, to: customTo || formatDateForInput(new Date()) }
      return null
    }
    return getPresetRange(rangePreset)
  }, [rangePreset, customFrom, customTo])

  const handleToggleRow = useCallback((name: string) => {
    setExpandedRow(prev => prev === name ? null : name)
  }, [])

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => fetchBrands(),
    staleTime: 5 * 60 * 1000,
  })
  const brandLeadTime = brands?.find(b => b.category_name === decodedName)?.supplier_lead_time ?? undefined

  const { data: skuPage, isLoading, isFetching, isError, refetch } = useQuery({
    queryKey: ['skus', decodedName, statusFilter, activeSearch, analysisRange?.from, analysisRange?.to, page, pageSize, abcFilter, hideInactive, velocityType, xyzFilter, hazardousFilter, deadStockFilter, intentFilter],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (statusFilter === 'urgent') params.status = 'urgent'
      else if (statusFilter === 'urgent_reorder') params.status = 'urgent,reorder'
      else if (statusFilter === 'out_of_stock') params.status = 'out_of_stock'
      if (deadStockFilter) params.dead_stock = 'true'
      if (hazardousFilter) params.hazardous = 'true'
      if (intentFilter === 'must_stock') params.reorder_intent = 'must_stock'
      else if (intentFilter === 'do_not_reorder') params.reorder_intent = 'do_not_reorder'
      if (activeSearch) params.search = activeSearch
      if (analysisRange) {
        if (analysisRange.from) params.from_date = analysisRange.from
        if (analysisRange.to) params.to_date = analysisRange.to
      }
      if (abcFilter) params.abc_class = abcFilter
      if (xyzFilter) params.xyz_class = xyzFilter
      params.hide_inactive = String(hideInactive)
      params.velocity_type = velocityType
      return fetchSkusPage(decodedName, params, {
        limit: pageSize,
        offset: page * pageSize,
      })
    },
    enabled: !!decodedName,
    placeholderData: previous => previous,
  })

  const skusRaw = skuPage?.items || []
  // Client-side sorting for mobile — memoized to avoid re-sorting on every render
  const skus = useMemo(() => {
    if (!isMobile || mobileSortCol === 'reorder_status') return skusRaw
    return [...skusRaw].sort((a, b) => {
      const key = mobileSortCol as keyof typeof a
      const av = a[key] ?? 0
      const bv = b[key] ?? 0
      const cmp = typeof av === 'string' ? av.localeCompare(bv as string) : (av as number) - (bv as number)
      return mobileSortDir === 'asc' ? cmp : -cmp
    })
  }, [skusRaw, isMobile, mobileSortCol, mobileSortDir])
  const totalSkus = skuPage?.total ?? 0
  const counts = skuPage?.counts ?? DEFAULT_COUNTS
  const pageStart = totalSkus === 0 ? 0 : page * pageSize + 1
  const pageEnd = Math.min((page + 1) * pageSize, totalSkus)
  const hasPreviousPage = page > 0
  const hasNextPage = pageEnd < totalSkus

  const poSearchParams = analysisRange
    ? `?from_date=${encodeURIComponent(analysisRange.from)}&to_date=${encodeURIComponent(analysisRange.to)}`
    : ''

  // Mobile filter chips
  const mobileFilterChips: FilterChip[] = []
  if (abcFilter) mobileFilterChips.push({ key: 'abc', label: `ABC: ${abcFilter}`, onRemove: () => { setAbcFilter(''); setPage(0) } })
  if (xyzFilter) mobileFilterChips.push({ key: 'xyz', label: `XYZ: ${xyzFilter}`, onRemove: () => { setXyzFilter(''); setPage(0) } })
  if (hazardousFilter) mobileFilterChips.push({ key: 'haz', label: 'Hazardous', onRemove: () => { setHazardousFilter(false); setPage(0) } })
  if (deadStockFilter) mobileFilterChips.push({ key: 'dead', label: 'Dead Stock', onRemove: () => { setDeadStockFilter(false); setPage(0) } })
  if (intentFilter) mobileFilterChips.push({ key: 'intent', label: `Intent: ${intentFilter}`, onRemove: () => { setIntentFilter(''); setPage(0) } })
  if (!hideInactive) mobileFilterChips.push({ key: 'inactive', label: 'Show Inactive', onRemove: () => { setHideInactive(true); setPage(0) } })
  if (rangePreset !== 'full_fy') mobileFilterChips.push({ key: 'range', label: `Range: ${rangePreset}`, onRemove: () => { setRangePreset('full_fy'); setPage(0) } })

  const mobileFilterCount = mobileFilterChips.length + (velocityType !== 'flat' ? 1 : 0)

  const statusPills = [
    { value: 'all', label: 'All', count: totalSkus },
    { value: 'urgent', label: 'Urgent', count: counts.urgent, color: 'text-red-600' },
    { value: 'urgent_reorder', label: 'Reorder', count: counts.reorder, color: 'text-amber-600' },
    { value: 'out_of_stock', label: 'OOS', count: counts.out_of_stock, color: 'text-red-500' },
  ]

  if (isError) return <div className="p-8 text-center text-muted-foreground">Failed to load SKUs. <button onClick={() => refetch()} className="text-primary hover:underline">Retry</button></div>

  // ==================== MOBILE LAYOUT ====================
  if (isMobile) {
    // If a SKU is selected, show full-screen detail overlay
    if (selectedSku) {
      return (
        <MobileSkuDetail
          sku={selectedSku}
          categoryName={decodedName}
          velocityType={velocityType}
          analysisRange={analysisRange}
          onBack={() => {
            setSelectedSku(null)
            // Restore scroll position after next paint
            requestAnimationFrame(() => {
              window.scrollTo(0, scrollPosition)
            })
          }}
        />
      )
    }

    return (
      <div className="px-4 py-4 space-y-4">
        {/* Header */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/brands')}
            className="p-1.5 -ml-1 rounded-md hover:bg-muted transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold truncate">{decodedName}</h2>
            <span className="text-xs text-muted-foreground">{isLoading && !skuPage ? '...' : totalSkus} SKUs</span>
          </div>
          <button
            onClick={() => setMobileSortOpen(true)}
            className="p-1.5 rounded-md hover:bg-muted transition-colors"
            aria-label="Sort"
          >
            <ArrowUpDown className="h-4 w-4" />
          </button>
        </div>

        {/* Summary Cards — horizontal scroll */}
        <div className="flex gap-2 overflow-x-auto pb-1 -mx-4 px-4">
          {[
            { label: 'Urgent', value: counts.urgent, color: 'text-red-600' },
            { label: 'Reorder', value: counts.reorder, color: 'text-amber-600' },
            { label: 'Healthy', value: counts.healthy, color: 'text-green-600' },
            { label: 'OOS', value: counts.out_of_stock, color: 'text-red-500' },
            { label: 'Dead', value: counts.dead_stock, color: 'text-blue-600' },
          ].map(c => (
            <Card key={c.label} className="min-w-[90px] flex-shrink-0">
              <CardContent className="pt-2 pb-2 px-3">
                <div className={`text-lg font-bold ${c.color}`}>{c.value}</div>
                <div className="text-[10px] text-muted-foreground">{c.label}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Search + Filter button */}
        <div className="flex items-center gap-2">
          <div className="flex-1">
            <UniversalSearch scope={decodedName} />
          </div>
          <FilterButton activeCount={mobileFilterCount} onClick={() => setMobileFilterOpen(true)} />
        </div>
        {activeSearch && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Showing results for: <strong>{activeSearch}</strong></span>
            <button className="text-primary underline text-xs" onClick={() => setActiveSearch(null)}>Clear</button>
          </div>
        )}

        {/* Status pill tabs — horizontal scroll */}
        <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-4 px-4">
          {statusPills.map(pill => (
            <button
              key={pill.value}
              onClick={() => { setStatusFilter(pill.value); setPage(0) }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                statusFilter === pill.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              }`}
            >
              {pill.label}
              {pill.count > 0 && ` (${pill.count})`}
            </button>
          ))}
        </div>

        {/* Filter chips */}
        <FilterChips chips={mobileFilterChips} />

        {/* SKU list — MobileListRow */}
        {isLoading ? (
          <div className="-mx-4">
            {Array.from({ length: 8 }).map((_, i) => <MobileListRowSkeleton key={i} />)}
          </div>
        ) : (
          <div className="-mx-4">
            {skus.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">No SKUs found</div>
            ) : (
              skus.map((s: SkuMetrics) => {
                const stock = s.effective_stock ?? s.current_stock
                const totalV = velocityType === 'wma' ? (s.wma_total_velocity ?? 0) : (s.effective_velocity ?? s.total_velocity)
                const daysLeft = s.effective_days_to_stockout ?? s.days_to_stockout
                const status = s.effective_status ?? s.reorder_status
                const statusLabel = status === 'out_of_stock' ? 'Out of Stock'
                  : status === 'no_data' ? 'No Data'
                  : status.charAt(0).toUpperCase() + status.slice(1)
                return (
                  <MobileListRow
                    key={s.stock_item_name}
                    title={s.part_no || s.stock_item_name}
                    subtitle={`Part No: ${s.stock_item_name}`}
                    status={status}
                    statusLabel={statusLabel}
                    metrics={[
                      { label: 'Stk', value: stock.toLocaleString() },
                      { label: 'Vel', value: `${vel(totalV)}/mo` },
                      { label: 'Out', value: daysLeft === null ? 'N/A' : daysLeft === 0 ? 'OUT' : `${daysLeft}d` },
                    ]}
                    badges={s.abc_class ? <AbcBadge value={s.abc_class} /> : undefined}
                    onClick={() => {
                      setScrollPosition(window.scrollY)
                      setSelectedSku(s)
                    }}
                  />
                )
              })
            )}

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <span className="text-xs text-muted-foreground">
                {pageStart}-{pageEnd} of {totalSkus}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!hasPreviousPage}
                  onClick={() => setPage(p => Math.max(p - 1, 0))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!hasNextPage}
                  onClick={() => setPage(p => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Mobile Filter Drawer */}
        <FilterDrawer open={mobileFilterOpen} onOpenChange={setMobileFilterOpen}>
          <div className="space-y-4">
            <div>
              <div className="text-sm font-medium mb-2">Velocity Type</div>
              <VelocityToggle value={velocityType} onChange={setVelocityType} />
            </div>
            <div>
              <div className="text-sm font-medium mb-2">Date Range</div>
              <Select value={rangePreset} onValueChange={v => {
                if (!v) return
                setRangePreset(v)
                setPage(0)
              }}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Analysis period" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full_fy">Full Financial Year</SelectItem>
                  <SelectItem value="6m">Last 6 Months</SelectItem>
                  <SelectItem value="3m">Last 3 Months</SelectItem>
                  <SelectItem value="2m">Last 2 Months</SelectItem>
                  <SelectItem value="30d">Last 30 Days</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <div className="text-sm font-medium mb-2">ABC Class</div>
              <Select value={abcFilter || 'all'} onValueChange={v => { if (v) { setAbcFilter(v === 'all' ? '' : v); setPage(0) } }}>
                <SelectTrigger className="w-full">
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
            <div>
              <div className="text-sm font-medium mb-2">XYZ Class</div>
              <Select value={xyzFilter || 'all'} onValueChange={v => { if (v) { setXyzFilter(v === 'all' ? '' : v); setPage(0) } }}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="XYZ Class" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All XYZ</SelectItem>
                  <SelectItem value="X">X Class</SelectItem>
                  <SelectItem value="Y">Y Class</SelectItem>
                  <SelectItem value="Z">Z Class</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <div className="text-sm font-medium mb-2">Intent</div>
              <Select value={intentFilter || 'all'} onValueChange={v => { if (v) { setIntentFilter(v === 'all' ? '' : v); setPage(0) } }}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Intent" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Intents</SelectItem>
                  <SelectItem value="must_stock">Must Stock</SelectItem>
                  <SelectItem value="do_not_reorder">Do Not Reorder</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={hazardousFilter}
                onChange={e => { setHazardousFilter(e.target.checked); setPage(0) }}
                className="rounded border-gray-300"
              />
              <span className="text-sm">Hazardous only</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={deadStockFilter}
                onChange={e => { setDeadStockFilter(e.target.checked); setPage(0) }}
                className="rounded border-gray-300"
              />
              <span className="text-sm">Dead stock only</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={!hideInactive}
                onChange={e => { setHideInactive(!e.target.checked); setPage(0) }}
                className="rounded border-gray-300"
              />
              <span className="text-sm">Show inactive</span>
            </label>
          </div>
        </FilterDrawer>

        {/* Mobile Sort Sheet */}
        <MobileSortSheet
          open={mobileSortOpen}
          onOpenChange={setMobileSortOpen}
          options={SKU_SORT_OPTIONS}
          value={mobileSortCol}
          direction={mobileSortDir}
          onSort={(val) => { setMobileSortCol(val); setMobileSortDir('desc') }}
          onToggleDirection={() => setMobileSortDir(d => d === 'desc' ? 'asc' : 'desc')}
        />
      </div>
    )
  }

  // ==================== DESKTOP LAYOUT ====================
  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate('/brands')}>
              <ArrowLeft className="h-4 w-4 mr-1" /> Back
            </Button>
            <h2 className="text-xl font-semibold">{decodedName}</h2>
            <span className="text-muted-foreground">{isLoading && !skuPage ? '...' : totalSkus} SKUs</span>
          </div>
          <div className="flex items-center gap-3">
            <ClassificationExplainer />
            <VelocityToggle value={velocityType} onChange={setVelocityType} />
            {/* Date Range Selector */}
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <Select value={rangePreset} onValueChange={v => {
                if (!v) return
                setRangePreset(v)
                setPage(0)
                setExpandedRow(null)
              }}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Analysis period" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full_fy">Full Financial Year</SelectItem>
                  <SelectItem value="6m">Last 6 Months</SelectItem>
                  <SelectItem value="3m">Last 3 Months</SelectItem>
                  <SelectItem value="2m">Last 2 Months</SelectItem>
                  <SelectItem value="30d">Last 30 Days</SelectItem>
                  <SelectItem value="custom">Custom Range</SelectItem>
                </SelectContent>
              </Select>
              {rangePreset === 'custom' && (
                <div className="flex items-center gap-1">
                  <input
                    type="date"
                    value={customFrom}
                    onChange={e => {
                      setCustomFrom(e.target.value)
                      setPage(0)
                      setExpandedRow(null)
                    }}
                    className="border rounded px-2 py-1 text-sm h-9"
                  />
                  <span className="text-muted-foreground text-sm">to</span>
                  <input
                    type="date"
                    value={customTo}
                    onChange={e => {
                      setCustomTo(e.target.value)
                      setPage(0)
                      setExpandedRow(null)
                    }}
                    className="border rounded px-2 py-1 text-sm h-9"
                  />
                </div>
              )}
            </div>
            <Button onClick={() => navigate(`/brands/${categoryName}/po${poSearchParams}`)}>
              <FileSpreadsheet className="h-4 w-4 mr-1" /> Build PO
            </Button>
          </div>
        </div>

        {/* Active range indicator */}
        {analysisRange && (
          <div className="text-xs text-muted-foreground bg-muted/50 rounded px-3 py-1.5 border flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5" />
            Velocities recalculated for: <strong className="text-foreground">{analysisRange.from} — {analysisRange.to}</strong>
            <span>(stock values remain current)</span>
          </div>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-5 gap-4">
          {[
            { label: 'Urgent', value: counts.urgent, color: 'text-red-600' },
            { label: 'Reorder', value: counts.reorder, color: 'text-amber-600' },
            { label: 'Healthy', value: counts.healthy, color: 'text-green-600' },
            { label: 'Out of Stock', value: counts.out_of_stock, color: 'text-red-500' },
            { label: 'Dead Stock', value: counts.dead_stock, color: 'text-blue-600' },
          ].map(c => (
            <Card key={c.label}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{c.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${c.color}`}>{c.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Filters — always visible */}
        {activeSearch && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Showing results for: <strong>{activeSearch}</strong></span>
            <button className="text-primary underline text-xs" onClick={() => setActiveSearch(null)}>Clear</button>
          </div>
        )}
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex-1 max-w-sm">
            <UniversalSearch scope={decodedName} />
          </div>
          <Select value={statusFilter} onValueChange={v => {
            if (!v) return
            setStatusFilter(v)
            setPage(0)
            setExpandedRow(null)
          }}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="urgent">Urgent Only</SelectItem>
              <SelectItem value="urgent_reorder">Urgent & Reorder</SelectItem>
              <SelectItem value="out_of_stock">Out of Stock</SelectItem>
            </SelectContent>
          </Select>
          <Select value={abcFilter || 'all'} onValueChange={v => { if (v) { setAbcFilter(v === 'all' ? '' : v); setPage(0); setExpandedRow(null) } }}>
            <SelectTrigger className="w-[130px]">
              <SelectValue placeholder="ABC Class" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Classes</SelectItem>
              <SelectItem value="A">A Class</SelectItem>
              <SelectItem value="B">B Class</SelectItem>
              <SelectItem value="C">C Class</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowMoreFilters(v => !v)}
            className="gap-1"
          >
            <Filter className="h-3.5 w-3.5" />
            More filters
            {hiddenFilterCount > 0 && (
              <Badge className="bg-primary text-primary-foreground text-[10px] px-1.5 py-0 ml-1">{hiddenFilterCount}</Badge>
            )}
          </Button>
          {isFetching && (
            <span className="text-xs text-muted-foreground">Updating...</span>
          )}
        </div>

        {/* More filters — collapsible */}
        {showMoreFilters && (
          <div className="flex items-center gap-4 pl-1 flex-wrap">
            <Select value={xyzFilter || 'all'} onValueChange={v => { if (v) { setXyzFilter(v === 'all' ? '' : v); setPage(0); setExpandedRow(null) } }}>
              <SelectTrigger className="w-[130px]">
                <SelectValue placeholder="XYZ Class" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All XYZ</SelectItem>
                <SelectItem value="X">X Class</SelectItem>
                <SelectItem value="Y">Y Class</SelectItem>
                <SelectItem value="Z">Z Class</SelectItem>
              </SelectContent>
            </Select>
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={hazardousFilter}
                onChange={e => { setHazardousFilter(e.target.checked); setPage(0); setExpandedRow(null) }}
                className="rounded border-gray-300"
              />
              Hazardous only
            </label>
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={deadStockFilter}
                onChange={e => { setDeadStockFilter(e.target.checked); setPage(0); setExpandedRow(null) }}
                className="rounded border-gray-300"
              />
              Dead stock
            </label>
            <Select value={intentFilter || 'all'} onValueChange={v => { if (v) { setIntentFilter(v === 'all' ? '' : v); setPage(0); setExpandedRow(null) } }}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Intent" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Intents</SelectItem>
                <SelectItem value="must_stock">Must Stock</SelectItem>
                <SelectItem value="do_not_reorder">Do Not Reorder</SelectItem>
              </SelectContent>
            </Select>
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={!hideInactive}
                onChange={e => { setHideInactive(!e.target.checked); setPage(0); setExpandedRow(null) }}
                className="rounded border-gray-300"
              />
              Show inactive
            </label>
          </div>
        )}

        {/* Table — 7 columns */}
        {isLoading ? (
          <div className="border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  {Array.from({ length: 7 }).map((_, i) => (
                    <TableHead key={i}><div className="h-4 w-full bg-muted animate-pulse rounded" /></TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 7 }).map((_, j) => (
                      <TableCell key={j}><div className="h-4 w-full bg-muted animate-pulse rounded" /></TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="border rounded-lg" data-tour="sku-table">
            <Table>
              <TableHeader>
                <TableRow data-tour="sku-columns">
                  <TableHead className="w-8"></TableHead>
                  <TableHead className="w-[80px]">Status <HelpTip tip="Reorder urgency: Critical (order now), Warning (order soon), OK (sufficient stock), Out of Stock (zero inventory)." helpAnchor="stockout-projection" /></TableHead>
                  <TableHead className="w-[110px]">Part No</TableHead>
                  <TableHead>Product Name</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="text-right">Velocity /mo <HelpTip tip="Units sold per day, calculated from in-stock days only. Split by channel because wholesale, online, and store are parallel demand tracks." helpAnchor="velocity" /></TableHead>
                  <TableHead className="text-center w-[60px]">ABC <HelpTip tip="Revenue classification: A = top 80%, B = next 15%, C = bottom 5%. Drives buffer size and reorder priority." helpAnchor="abc-classification" /></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody data-tour="sku-expand-hint">
                {skus.map((s: SkuMetrics) => (
                  <SkuRow
                    key={s.stock_item_name}
                    s={s}
                    isExpanded={expandedRow === s.stock_item_name}
                    onToggle={handleToggleRow}
                    decodedName={decodedName}
                    analysisRange={analysisRange}
                    velocityType={velocityType}
                    supplierLeadTime={brandLeadTime}
                  />
                ))}
                {skus.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                      No SKUs found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
              <div className="border-t px-4 py-3 flex items-center justify-between gap-3">
                <div className="text-sm text-muted-foreground">
                  Showing {pageStart}-{pageEnd} of {totalSkus}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Rows</span>
                  <Select
                    value={String(pageSize)}
                    onValueChange={value => {
                      if (!value) return
                      setPageSize(Number(value))
                      setPage(0)
                      setExpandedRow(null)
                    }}
                  >
                    <SelectTrigger className="h-8 w-[90px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="50">50</SelectItem>
                      <SelectItem value="100">100</SelectItem>
                      <SelectItem value="200">200</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasPreviousPage}
                    onClick={() => {
                      setExpandedRow(null)
                      setPage(p => Math.max(p - 1, 0))
                    }}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasNextPage}
                    onClick={() => {
                      setExpandedRow(null)
                      setPage(p => p + 1)
                    }}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>
          )}
      </div>
    </TooltipProvider>
  )
}
