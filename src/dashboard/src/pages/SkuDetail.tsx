import { useState, useMemo, Fragment } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchSkus, toggleHazardous } from '@/lib/api'
import type { SkuMetrics } from '@/lib/types'
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
import { ArrowLeft, ChevronDown, ChevronRight, FileSpreadsheet, Search, Pencil, AlertTriangle, StickyNote, Calendar, Flame, Snowflake } from 'lucide-react'

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

export default function SkuDetail() {
  const { categoryName } = useParams<{ categoryName: string }>()
  const navigate = useNavigate()
  const decodedName = decodeURIComponent(categoryName || '')

  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

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

  const queryClient = useQueryClient()

  const hazardousMutation = useMutation({
    mutationFn: ({ name, value }: { name: string; value: boolean }) => toggleHazardous(name, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['skus', decodedName] }),
  })

  const { data: skus, isLoading } = useQuery({
    queryKey: ['skus', decodedName, statusFilter, search, analysisRange?.from, analysisRange?.to],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (statusFilter === 'critical') params.status = 'critical'
      else if (statusFilter === 'critical_warning') params.status = 'critical,warning'
      else if (statusFilter === 'out_of_stock') params.status = 'out_of_stock'
      else if (statusFilter === 'dead_stock') params.dead_stock = 'true'
      else if (statusFilter === 'hazardous') params.hazardous = 'true'
      else if (statusFilter === 'must_stock') params.reorder_intent = 'must_stock'
      else if (statusFilter === 'do_not_reorder') params.reorder_intent = 'do_not_reorder'
      if (search) params.search = search
      if (analysisRange) {
        if (analysisRange.from) params.from_date = analysisRange.from
        if (analysisRange.to) params.to_date = analysisRange.to
      }
      return fetchSkus(decodedName, params)
    },
    enabled: !!decodedName,
  })

  const counts = useMemo(() => {
    const c = { critical: 0, warning: 0, ok: 0, out_of_stock: 0, dead_stock: 0 }
    for (const s of skus || []) {
      const st = s.effective_status ?? s.reorder_status
      if (st in c) c[st as keyof typeof c]++
      if (s.is_dead_stock) c.dead_stock++
    }
    return c
  }, [skus])

  const daysDisplay = (d: number | null) => {
    if (d === null) return <span className="text-gray-400">N/A</span>
    if (d === 0) return <span className="text-red-600 font-bold">OUT</span>
    if (d < 30) return <span className="text-red-600 font-medium">{d}d</span>
    if (d < 90) return <span className="text-amber-600">{d}d</span>
    return <span className="text-green-600">{d}d</span>
  }

  const vel = (v: number) => (v * 30).toFixed(1)

  const poSearchParams = analysisRange
    ? `?from_date=${encodeURIComponent(analysisRange.from)}&to_date=${encodeURIComponent(analysisRange.to)}`
    : ''

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
              <ArrowLeft className="h-4 w-4 mr-1" /> Back
            </Button>
            <h2 className="text-xl font-semibold">{decodedName}</h2>
            <span className="text-muted-foreground">{skus?.length ?? '...'} SKUs</span>
          </div>
          <div className="flex items-center gap-3">
            {/* Date Range Selector */}
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <Select value={rangePreset} onValueChange={v => { if (v) setRangePreset(v) }}>
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
                    onChange={e => setCustomFrom(e.target.value)}
                    className="border rounded px-2 py-1 text-sm h-9"
                  />
                  <span className="text-muted-foreground text-sm">to</span>
                  <input
                    type="date"
                    value={customTo}
                    onChange={e => setCustomTo(e.target.value)}
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

        {/* Filters */}
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search SKUs..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={statusFilter} onValueChange={v => { if (v) setStatusFilter(v) }}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="critical">Critical Only</SelectItem>
              <SelectItem value="critical_warning">Critical & Warning</SelectItem>
              <SelectItem value="out_of_stock">Out of Stock</SelectItem>
              <SelectItem value="dead_stock">Dead Stock</SelectItem>
              <SelectItem value="hazardous">Hazardous</SelectItem>
              <SelectItem value="must_stock">Must Stock</SelectItem>
              <SelectItem value="do_not_reorder">Do Not Reorder</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="text-center py-12 text-muted-foreground">Loading SKUs...</div>
        ) : (
          <div className="border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8"></TableHead>
                  <TableHead className="w-[80px]">Status</TableHead>
                  <TableHead>Part No</TableHead>
                  <TableHead className="w-10">Haz</TableHead>
                  <TableHead>SKU Name</TableHead>
                  <TableHead>Intent</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="text-right">Wholesale /mo</TableHead>
                  <TableHead className="text-right">Online /mo</TableHead>
                  <TableHead className="text-right">Total /mo</TableHead>
                  <TableHead className="text-right">Days Left</TableHead>
                  <TableHead>Last Import</TableHead>
                  <TableHead className="text-right">Suggested</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(skus || []).map((s: SkuMetrics) => {
                  return (
                    <Fragment key={s.stock_item_name}>
                      <TableRow
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => setExpandedRow(expandedRow === s.stock_item_name ? null : s.stock_item_name)}
                      >
                        <TableCell>
                          {expandedRow === s.stock_item_name
                            ? <ChevronDown className="h-4 w-4" />
                            : <ChevronRight className="h-4 w-4" />}
                        </TableCell>
                        <TableCell><StatusBadge status={s.effective_status ?? s.reorder_status} /></TableCell>
                        <TableCell className="text-xs text-muted-foreground">{s.part_no || '-'}</TableCell>
                        <TableCell className="text-center">
                          <Flame
                            className={`h-4 w-4 cursor-pointer transition-colors inline-block ${s.is_hazardous ? 'text-amber-500 fill-amber-500' : 'text-gray-300 hover:text-amber-400'}`}
                            onClick={e => {
                              e.stopPropagation()
                              hazardousMutation.mutate({ name: s.stock_item_name, value: !s.is_hazardous })
                            }}
                          />
                        </TableCell>
                        <TableCell className="max-w-[250px] truncate" title={s.stock_item_name}>
                          <span className="inline-flex items-center gap-1">
                            {s.stock_item_name}
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
                                <TooltipContent>Dead stock — no sales for {s.days_since_last_sale ?? '∞'} days</TooltipContent>
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
                        <TableCell onClick={e => e.stopPropagation()}>
                          <ReorderIntentSelector
                            stockItemName={s.stock_item_name}
                            currentIntent={s.reorder_intent || 'normal'}
                          />
                        </TableCell>
                        <TableCell className={`text-right ${(s.effective_stock ?? s.current_stock) <= 0 ? 'text-red-600 font-medium' : ''}`}>
                          <span className="inline-flex items-center gap-1 justify-end">
                            {s.effective_stock ?? s.current_stock}
                            {s.has_stock_override && (
                              <Tooltip>
                                <TooltipTrigger>
                                  {s.stock_override_stale
                                    ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                                    : <Pencil className="h-3.5 w-3.5 text-blue-500 shrink-0" />}
                                </TooltipTrigger>
                                <TooltipContent>
                                  Stock override active (computed: {s.current_stock})
                                  {s.stock_override_stale && ' — STALE: Tally data changed'}
                                </TooltipContent>
                              </Tooltip>
                            )}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">{vel(s.effective_wholesale_velocity ?? s.wholesale_velocity)}</TableCell>
                        <TableCell className="text-right">{vel(s.effective_online_velocity ?? s.online_velocity)}</TableCell>
                        <TableCell className="text-right font-medium">
                          <span className="inline-flex items-center gap-1 justify-end">
                            {vel(s.effective_velocity ?? s.total_velocity)}
                            {s.has_velocity_override && (
                              <Tooltip>
                                <TooltipTrigger>
                                  {s.velocity_override_stale
                                    ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                                    : <Pencil className="h-3.5 w-3.5 text-blue-500 shrink-0" />}
                                </TooltipTrigger>
                                <TooltipContent>
                                  Velocity override active (computed: {vel(s.total_velocity)}/mo)
                                  {s.velocity_override_stale && ' — STALE'}
                                </TooltipContent>
                              </Tooltip>
                            )}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">{daysDisplay(s.effective_days_to_stockout ?? s.days_to_stockout)}</TableCell>
                        <TableCell className="text-xs">
                          {s.last_import_date
                            ? new Date(s.last_import_date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: '2-digit' })
                            : '-'}
                          {s.last_import_qty ? ` (${s.last_import_qty})` : ''}
                        </TableCell>
                        <TableCell className="text-right">{s.effective_suggested_qty ?? s.reorder_qty_suggested ?? '-'}</TableCell>
                      </TableRow>
                      {expandedRow === s.stock_item_name && (
                        <TableRow key={`${s.stock_item_name}-detail`}>
                          <TableCell colSpan={13} className="bg-muted/30 p-4">
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
                })}
                {(skus || []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={13} className="text-center py-8 text-muted-foreground">
                      No SKUs found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </TooltipProvider>
  )
}
