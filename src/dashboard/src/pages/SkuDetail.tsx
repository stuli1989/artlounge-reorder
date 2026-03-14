import { useState, useMemo, useEffect, useCallback, memo, Fragment } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSkusPage, fetchBrands } from '@/lib/api'
import type { SkuCounts, SkuMetrics } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import StatusBadge from '@/components/StatusBadge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import StockTimelineChart from '@/components/StockTimelineChart'
import TransactionHistory from '@/components/TransactionHistory'
import CalculationBreakdown from '@/components/CalculationBreakdown'
import ReorderIntentSelector from '@/components/ReorderIntentSelector'
import { Badge } from '@/components/ui/badge'
import AbcBadge from '@/components/AbcBadge'
import VelocityToggle from '@/components/VelocityToggle'
import TrendIndicator from '@/components/TrendIndicator'
import ClassificationExplainer from '@/components/ClassificationExplainer'
import { ArrowLeft, ChevronDown, ChevronRight, FileSpreadsheet, Search, Pencil, AlertTriangle, StickyNote, Calendar, Snowflake, Filter } from 'lucide-react'
import { vel, daysColor } from '@/lib/formatters'

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
  critical: 0,
  warning: 0,
  ok: 0,
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
        <TableCell className="font-mono font-semibold text-sm">{s.part_no || '\u2014'}</TableCell>
        <TableCell className="max-w-[280px] truncate" title={s.stock_item_name}>
          <span className="inline-flex items-center gap-1">
            {s.stock_item_name}
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
                  {s.stock_override_stale && ' \u2014 STALE: Tally data changed'}
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
                <TabsTrigger value="timeline">Stock Timeline</TabsTrigger>
                <TabsTrigger value="transactions">Transactions</TabsTrigger>
                <TabsTrigger value="calculation">Calculation</TabsTrigger>
              </TabsList>
              <TabsContent value="timeline" className="pt-4">
                <StockTimelineChart categoryName={decodedName} stockItemName={s.stock_item_name} />
              </TabsContent>
              <TabsContent value="transactions" className="pt-4">
                <TransactionHistory categoryName={decodedName} stockItemName={s.stock_item_name} />
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

export default function SkuDetail() {
  const { categoryName } = useParams<{ categoryName: string }>()
  const navigate = useNavigate()
  const decodedName = decodeURIComponent(categoryName || '')

  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(100)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

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
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')

  const analysisRange = useMemo(() => {
    if (rangePreset === 'custom') {
      if (customFrom || customTo) return { from: customFrom, to: customTo || formatDateForInput(new Date()) }
      return null
    }
    return getPresetRange(rangePreset)
  }, [rangePreset, customFrom, customTo])

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedSearch(search.trim())
    }, 300)
    return () => window.clearTimeout(handle)
  }, [search])

  const handleToggleRow = useCallback((name: string) => {
    setExpandedRow(prev => prev === name ? null : name)
  }, [])

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => fetchBrands(),
    staleTime: 5 * 60 * 1000,
  })
  const brandLeadTime = brands?.find(b => b.category_name === decodedName)?.supplier_lead_time ?? undefined

  const { data: skuPage, isLoading, isFetching } = useQuery({
    queryKey: ['skus', decodedName, statusFilter, debouncedSearch, analysisRange?.from, analysisRange?.to, page, pageSize, abcFilter, hideInactive, velocityType, xyzFilter, hazardousFilter, deadStockFilter, intentFilter],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (statusFilter === 'critical') params.status = 'critical'
      else if (statusFilter === 'critical_warning') params.status = 'critical,warning'
      else if (statusFilter === 'out_of_stock') params.status = 'out_of_stock'
      if (deadStockFilter) params.dead_stock = 'true'
      if (hazardousFilter) params.hazardous = 'true'
      if (intentFilter === 'must_stock') params.reorder_intent = 'must_stock'
      else if (intentFilter === 'do_not_reorder') params.reorder_intent = 'do_not_reorder'
      if (debouncedSearch) params.search = debouncedSearch
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

  const skus = skuPage?.items || []
  const totalSkus = skuPage?.total ?? 0
  const counts = skuPage?.counts ?? DEFAULT_COUNTS
  const pageStart = totalSkus === 0 ? 0 : page * pageSize + 1
  const pageEnd = Math.min((page + 1) * pageSize, totalSkus)
  const hasPreviousPage = page > 0
  const hasNextPage = pageEnd < totalSkus

  const poSearchParams = analysisRange
    ? `?from_date=${encodeURIComponent(analysisRange.from)}&to_date=${encodeURIComponent(analysisRange.to)}`
    : ''

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
            { label: 'Critical', value: counts.critical, color: 'text-red-600' },
            { label: 'Warning', value: counts.warning, color: 'text-amber-600' },
            { label: 'OK', value: counts.ok, color: 'text-green-600' },
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
        <div className="flex items-center gap-4 flex-wrap">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search SKUs..."
              value={search}
              onChange={e => {
                setSearch(e.target.value)
                setPage(0)
                setExpandedRow(null)
              }}
              className="pl-9"
            />
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
              <SelectItem value="critical">Critical Only</SelectItem>
              <SelectItem value="critical_warning">Critical & Warning</SelectItem>
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
          <div className="border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8"></TableHead>
                  <TableHead className="w-[80px]">Status</TableHead>
                  <TableHead className="w-[110px]">Part No</TableHead>
                  <TableHead>SKU Name</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="text-right">Velocity /mo</TableHead>
                  <TableHead className="text-center w-[60px]">ABC</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
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
