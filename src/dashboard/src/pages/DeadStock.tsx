import { useState, useMemo, useEffect, useRef, Fragment } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchSkus, fetchSettings, updateSetting } from '@/lib/api'
import type { SkuMetrics } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import StatusBadge from '@/components/StatusBadge'
import ReorderIntentSelector from '@/components/ReorderIntentSelector'
import UniversalSearch from '@/components/UniversalSearch'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import StockTimeline from '@/components/StockTimeline'
import CalculationBreakdown from '@/components/CalculationBreakdown'
import AbcBadge from '@/components/AbcBadge'
import { ArrowLeft, Snowflake, ChevronDown, ChevronRight, ClipboardList } from 'lucide-react'
import { vel } from '@/lib/formatters'
import { useIsMobile } from '@/hooks/useIsMobile'
import { MobileListRow, MobileListRowSkeleton } from '@/components/mobile/MobileListRow'

export default function DeadStock() {
  const { categoryName } = useParams<{ categoryName: string }>()
  const navigate = useNavigate()
  const decodedName = decodeURIComponent(categoryName || '')
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()

  const [activeTab, setActiveTab] = useState<'dead' | 'slow'>('dead')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [thresholdInput, setThresholdInput] = useState('')
  const [slowThresholdInput, setSlowThresholdInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [thresholdExpanded, setThresholdExpanded] = useState(!isMobile)

  const hasInitialized = useRef(false)

  // Load settings
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
  })

  useEffect(() => {
    if (!hasInitialized.current && settings) {
      if (settings.dead_stock_threshold_days) {
        setThresholdInput(settings.dead_stock_threshold_days)
      }
      if (settings.slow_mover_velocity_threshold) {
        // Convert daily to monthly for display
        setSlowThresholdInput(String((parseFloat(settings.slow_mover_velocity_threshold) * 30).toFixed(1)))
      }
      hasInitialized.current = true
    }
  }, [settings])

  const deadThreshold = settings?.dead_stock_threshold_days || '30'
  const slowThresholdDaily = settings?.slow_mover_velocity_threshold || '0.1'

  // Load SKUs based on active tab
  const { data: skus, isLoading } = useQuery({
    queryKey: ['skus', decodedName, activeTab, deadThreshold, slowThresholdDaily],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (activeTab === 'dead') params.dead_stock = 'true'
      else params.slow_mover = 'true'
      return fetchSkus(decodedName, params)
    },
    enabled: !!decodedName,
  })

  // Sort: dead by days_since_last_sale DESC, slow by total_velocity ASC
  const sorted = useMemo(() =>
    [...(skus || [])].sort((a, b) => {
      if (activeTab === 'dead') {
        const aD = a.days_since_last_sale ?? Infinity
        const bD = b.days_since_last_sale ?? Infinity
        return bD - aD
      }
      // Slow movers: slowest first
      const aV = (a.effective_velocity ?? a.total_velocity) || 0
      const bV = (b.effective_velocity ?? b.total_velocity) || 0
      return aV - bV
    }),
    [skus, activeTab]
  )

  const needsClassification = useMemo(
    () => sorted.filter(s => (s.reorder_intent || 'normal') === 'normal').length,
    [sorted]
  )

  const thresholdMutation = useMutation({
    mutationFn: (val: { key: string; value: string }) => updateSetting(val.key, val.value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skus'] })
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setSaving(false)
    },
  })

  const handleSaveDeadThreshold = () => {
    const num = parseInt(thresholdInput, 10)
    if (isNaN(num) || num < 1) return
    setSaving(true)
    thresholdMutation.mutate({ key: 'dead_stock_threshold_days', value: String(num) })
  }

  const handleSaveSlowThreshold = () => {
    const monthly = parseFloat(slowThresholdInput)
    if (isNaN(monthly) || monthly <= 0) return
    const daily = (monthly / 30).toFixed(6)
    setSaving(true)
    thresholdMutation.mutate({ key: 'slow_mover_velocity_threshold', value: daily })
  }

  const renderExpandedDetail = (stockItemName: string) => (
    <Tabs defaultValue="timeline">
      <TabsList>
        <TabsTrigger value="timeline">Timeline & Transactions</TabsTrigger>
        <TabsTrigger value="calculation">Calculation</TabsTrigger>
      </TabsList>
      <TabsContent value="timeline" className="pt-4">
        <StockTimeline categoryName={decodedName} stockItemName={stockItemName} />
      </TabsContent>
      <TabsContent value="calculation" className="pt-4">
        <CalculationBreakdown categoryName={decodedName} stockItemName={stockItemName} />
      </TabsContent>
    </Tabs>
  )

  if (isMobile) {
    const formatLastSale = (date: string | null) =>
      date ? new Date(date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: '2-digit' }) : 'Never'

    return (
      <TooltipProvider>
        <div className="px-4 py-4 space-y-4">
          {/* Header */}
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigate('/brands')}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <ClipboardList className="h-4 w-4 text-purple-500" />
            <h2 className="text-lg font-semibold truncate">Review — {decodedName}</h2>
            <span className="text-xs text-muted-foreground">{sorted.length}</span>
          </div>

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={v => { setActiveTab(v as 'dead' | 'slow'); setExpandedRow(null) }}>
            <TabsList className="w-full">
              <TabsTrigger value="dead" className="flex-1">
                <Snowflake className="h-3.5 w-3.5 mr-1" /> Dead
              </TabsTrigger>
              <TabsTrigger value="slow" className="flex-1">Slow</TabsTrigger>
            </TabsList>

            {/* Collapsible threshold config */}
            <button
              className="w-full flex items-center justify-between mt-3 px-3 py-2 bg-muted/50 rounded-lg text-sm"
              onClick={() => setThresholdExpanded(v => !v)}
            >
              <span className="text-muted-foreground">
                {activeTab === 'dead'
                  ? `Dead after ${thresholdInput || deadThreshold} days`
                  : `Below ${slowThresholdInput || (parseFloat(slowThresholdDaily) * 30).toFixed(1)} /mo`}
              </span>
              {thresholdExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>

            {thresholdExpanded && (
              <div className="mt-2">
                {activeTab === 'dead' ? (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Dead after</span>
                    <Input
                      type="number"
                      inputMode="numeric"
                      min={1}
                      value={thresholdInput}
                      onChange={e => setThresholdInput(e.target.value)}
                      className="w-20 h-8"
                    />
                    <span className="text-sm text-muted-foreground">days</span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={saving || thresholdInput === deadThreshold}
                      onClick={handleSaveDeadThreshold}
                    >
                      {saving ? '...' : 'Save'}
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Below</span>
                    <Input
                      type="number"
                      inputMode="decimal"
                      min={0.1}
                      step={0.1}
                      value={slowThresholdInput}
                      onChange={e => setSlowThresholdInput(e.target.value)}
                      className="w-20 h-8"
                    />
                    <span className="text-sm text-muted-foreground">/mo</span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={saving || slowThresholdInput === String((parseFloat(slowThresholdDaily) * 30).toFixed(1))}
                      onClick={handleSaveSlowThreshold}
                    >
                      {saving ? '...' : 'Save'}
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Summary Cards — horizontal scroll */}
            <div className="flex gap-2 overflow-x-auto pb-1 -mx-4 px-4 mt-3">
              <Card className="min-w-[110px] flex-shrink-0">
                <CardContent className="pt-3 pb-2 px-3">
                  <div className="text-lg font-bold text-blue-600">{sorted.length}</div>
                  <div className="text-[10px] text-muted-foreground">{activeTab === 'dead' ? 'Dead' : 'Slow'}</div>
                </CardContent>
              </Card>
              <Card className="min-w-[110px] flex-shrink-0">
                <CardContent className="pt-3 pb-2 px-3">
                  <div className="text-lg font-bold text-purple-600">{needsClassification}</div>
                  <div className="text-[10px] text-muted-foreground">Unclassified</div>
                </CardContent>
              </Card>
              <Card className="min-w-[110px] flex-shrink-0">
                <CardContent className="pt-3 pb-2 px-3">
                  <div className="text-lg font-bold text-blue-600">
                    {activeTab === 'dead'
                      ? sorted.length > 0
                        ? sorted[0].days_since_last_sale !== null
                          ? `${sorted[0].days_since_last_sale}d`
                          : 'Never'
                        : '-'
                      : `${(parseFloat(slowThresholdDaily) * 30).toFixed(1)}`}
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    {activeTab === 'dead' ? 'Longest Idle' : 'Threshold'}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Search */}
            <div className="mt-3">
              <UniversalSearch scope={decodedName} />
            </div>

            {/* Dead Stock Tab Content */}
            <TabsContent value="dead" className="mt-3">
              {isLoading ? (
                <div className="space-y-0 -mx-4">
                  {Array.from({ length: 5 }).map((_, i) => <MobileListRowSkeleton key={i} />)}
                </div>
              ) : sorted.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No dead stock found</div>
              ) : (
                <div className="-mx-4">
                  {sorted.map((s: SkuMetrics) => (
                    <MobileListRow
                      key={s.stock_item_name}
                      title={s.part_no || s.stock_item_name}
                      subtitle={`Part No: ${s.stock_item_name}`}
                      status="out_of_stock"
                      statusLabel={s.days_since_last_sale !== null ? `${s.days_since_last_sale}d idle` : 'Never sold'}
                      metrics={[
                        { label: 'Stock', value: String(s.effective_stock ?? s.current_stock) },
                        { label: 'Last Sale', value: formatLastSale(s.last_sale_date) },
                        { label: 'Days', value: `${s.total_zero_activity_days}d` },
                      ]}
                      onClick={() => navigate(`/brands/${encodeURIComponent(decodedName)}/skus`)}
                    >
                      <div className="mt-1.5" onClick={e => e.stopPropagation()}>
                        <ReorderIntentSelector
                          stockItemName={s.stock_item_name}
                          currentIntent={s.reorder_intent || 'normal'}
                        />
                      </div>
                    </MobileListRow>
                  ))}
                </div>
              )}
            </TabsContent>

            {/* Slow Movers Tab Content */}
            <TabsContent value="slow" className="mt-3">
              {isLoading ? (
                <div className="space-y-0 -mx-4">
                  {Array.from({ length: 5 }).map((_, i) => <MobileListRowSkeleton key={i} />)}
                </div>
              ) : sorted.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No slow movers found</div>
              ) : (
                <div className="-mx-4">
                  {sorted.map((s: SkuMetrics) => (
                    <MobileListRow
                      key={s.stock_item_name}
                      title={s.part_no || s.stock_item_name}
                      subtitle={`Part No: ${s.stock_item_name}`}
                      status="reorder"
                      statusLabel={`${vel(s.effective_velocity ?? s.total_velocity)}/mo`}
                      metrics={[
                        { label: 'Stock', value: String(s.effective_stock ?? s.current_stock) },
                        { label: 'Last Sale', value: formatLastSale(s.last_sale_date) },
                        { label: 'Days Left', value: (s.effective_days_to_stockout ?? s.days_to_stockout) ? `${s.effective_days_to_stockout ?? s.days_to_stockout}d` : 'N/A' },
                      ]}
                      onClick={() => navigate(`/brands/${encodeURIComponent(decodedName)}/skus`)}
                    >
                      <div className="mt-1.5" onClick={e => e.stopPropagation()}>
                        <ReorderIntentSelector
                          stockItemName={s.stock_item_name}
                          currentIntent={s.reorder_intent || 'normal'}
                        />
                      </div>
                    </MobileListRow>
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </TooltipProvider>
    )
  }

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate('/brands')}>
              <ArrowLeft className="h-4 w-4 mr-1" /> Back
            </Button>
            <ClipboardList className="h-5 w-5 text-purple-500" />
            <h2 className="text-xl font-semibold">Stock Review — {decodedName}</h2>
            <span className="text-muted-foreground">{sorted.length} items</span>
          </div>
        </div>

        {/* Top-level tabs */}
        <Tabs value={activeTab} onValueChange={v => { setActiveTab(v as 'dead' | 'slow'); setExpandedRow(null) }}>
          <div className="flex items-center justify-between">
            <TabsList>
              <TabsTrigger value="dead">
                <Snowflake className="h-3.5 w-3.5 mr-1" /> Dead Stock
              </TabsTrigger>
              <TabsTrigger value="slow">Slow Movers</TabsTrigger>
            </TabsList>

            {/* Threshold editor (tab-specific) */}
            {activeTab === 'dead' ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Dead after</span>
                <Input
                  type="number"
                  min={1}
                  value={thresholdInput}
                  onChange={e => setThresholdInput(e.target.value)}
                  className="w-20 h-8"
                />
                <span className="text-sm text-muted-foreground">days</span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={saving || thresholdInput === deadThreshold}
                  onClick={handleSaveDeadThreshold}
                >
                  {saving ? 'Saving...' : 'Save'}
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Below</span>
                <Input
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={slowThresholdInput}
                  onChange={e => setSlowThresholdInput(e.target.value)}
                  className="w-20 h-8"
                />
                <span className="text-sm text-muted-foreground">units/month</span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={saving || slowThresholdInput === String((parseFloat(slowThresholdDaily) * 30).toFixed(1))}
                  onClick={handleSaveSlowThreshold}
                >
                  {saving ? 'Saving...' : 'Save'}
                </Button>
              </div>
            )}
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-3 gap-4 mt-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {activeTab === 'dead' ? 'Dead Stock Items' : 'Slow Mover Items'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600">{sorted.length}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Needs Classification</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-purple-600">{needsClassification}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {activeTab === 'dead' ? 'Longest Idle' : 'Velocity Threshold'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600">
                  {activeTab === 'dead'
                    ? sorted.length > 0
                      ? sorted[0].days_since_last_sale !== null
                        ? `${sorted[0].days_since_last_sale} days`
                        : 'Never sold'
                      : '-'
                    : `${(parseFloat(slowThresholdDaily) * 30).toFixed(1)} /mo`}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Search */}
          <div className="max-w-sm mt-4">
            <UniversalSearch scope={decodedName} />
          </div>

          {/* Dead Stock Tab Content */}
          <TabsContent value="dead" className="mt-4">
            {isLoading ? (
              <div className="text-center py-12 text-muted-foreground">Loading dead stock...</div>
            ) : sorted.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground border rounded-lg">
                No dead stock items found — all inventory is moving
              </div>
            ) : (
              <div className="border rounded-lg">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8"></TableHead>
                      <TableHead className="w-[80px]">Status</TableHead>
                      <TableHead className="w-10">ABC</TableHead>
                      <TableHead>Part No</TableHead>
                      <TableHead>Product Name</TableHead>
                      <TableHead className="text-right">Stock</TableHead>
                      <TableHead>Last Sale</TableHead>
                      <TableHead className="text-right">Days Idle</TableHead>
                      <TableHead>Intent</TableHead>
                      <TableHead className="text-right">Zero Activity Days</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sorted.map((s: SkuMetrics) => (
                      <Fragment key={s.stock_item_name}>
                        <TableRow
                          className="cursor-pointer hover:bg-muted/50"
                          tabIndex={0}
                          onClick={() => setExpandedRow(expandedRow === s.stock_item_name ? null : s.stock_item_name)}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedRow(expandedRow === s.stock_item_name ? null : s.stock_item_name) } }}
                        >
                          <TableCell>
                            {expandedRow === s.stock_item_name
                              ? <ChevronDown className="h-4 w-4" />
                              : <ChevronRight className="h-4 w-4" />}
                          </TableCell>
                          <TableCell><StatusBadge status={s.effective_status ?? s.reorder_status} /></TableCell>
                          <TableCell><AbcBadge value={s.abc_class} /></TableCell>
                          <TableCell className="text-xs text-muted-foreground">{s.stock_item_name}</TableCell>
                          <TableCell className="max-w-[250px] truncate" title={s.part_no || s.stock_item_name}>
                            <span className="inline-flex items-center gap-1">
                              {s.part_no || s.stock_item_name}
                              <Tooltip>
                                <TooltipTrigger>
                                  <Snowflake className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                                </TooltipTrigger>
                                <TooltipContent>Dead stock — no sales for {s.days_since_last_sale ?? '∞'} days</TooltipContent>
                              </Tooltip>
                            </span>
                          </TableCell>
                          <TableCell className="text-right">{s.effective_stock ?? s.current_stock}</TableCell>
                          <TableCell className="text-xs">
                            {s.last_sale_date
                              ? new Date(s.last_sale_date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: '2-digit' })
                              : 'Never'}
                          </TableCell>
                          <TableCell className="text-right font-medium text-blue-600">
                            {s.days_since_last_sale !== null ? `${s.days_since_last_sale}d` : '∞'}
                          </TableCell>
                          <TableCell onClick={e => e.stopPropagation()}>
                            <ReorderIntentSelector
                              stockItemName={s.stock_item_name}
                              currentIntent={s.reorder_intent || 'normal'}
                            />
                          </TableCell>
                          <TableCell className="text-right">{s.total_zero_activity_days}d</TableCell>
                        </TableRow>
                        {expandedRow === s.stock_item_name && (
                          <TableRow key={`${s.stock_item_name}-detail`}>
                            <TableCell colSpan={10} className="bg-muted/30 p-4">
                              {renderExpandedDetail(s.stock_item_name)}
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>

          {/* Slow Movers Tab Content */}
          <TabsContent value="slow" className="mt-4">
            {isLoading ? (
              <div className="text-center py-12 text-muted-foreground">Loading slow movers...</div>
            ) : sorted.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground border rounded-lg">
                No slow mover items found
              </div>
            ) : (
              <div className="border rounded-lg">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8"></TableHead>
                      <TableHead className="w-[80px]">Status</TableHead>
                      <TableHead>Part No</TableHead>
                      <TableHead>Product Name</TableHead>
                      <TableHead className="text-right">Stock</TableHead>
                      <TableHead className="text-right">Velocity /mo</TableHead>
                      <TableHead className="text-right">Days Left</TableHead>
                      <TableHead>Intent</TableHead>
                      <TableHead>Last Sale</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sorted.map((s: SkuMetrics) => (
                      <Fragment key={s.stock_item_name}>
                        <TableRow
                          className="cursor-pointer hover:bg-muted/50"
                          tabIndex={0}
                          onClick={() => setExpandedRow(expandedRow === s.stock_item_name ? null : s.stock_item_name)}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedRow(expandedRow === s.stock_item_name ? null : s.stock_item_name) } }}
                        >
                          <TableCell>
                            {expandedRow === s.stock_item_name
                              ? <ChevronDown className="h-4 w-4" />
                              : <ChevronRight className="h-4 w-4" />}
                          </TableCell>
                          <TableCell><StatusBadge status={s.effective_status ?? s.reorder_status} /></TableCell>
                          <TableCell className="text-xs text-muted-foreground">{s.stock_item_name}</TableCell>
                          <TableCell className="max-w-[250px] truncate" title={s.part_no || s.stock_item_name}>
                            {s.part_no || s.stock_item_name}
                          </TableCell>
                          <TableCell className="text-right">{s.effective_stock ?? s.current_stock}</TableCell>
                          <TableCell className="text-right font-medium text-amber-600">
                            {vel(s.effective_velocity ?? s.total_velocity)}
                          </TableCell>
                          <TableCell className="text-right">
                            {s.effective_days_to_stockout ?? s.days_to_stockout
                              ? `${s.effective_days_to_stockout ?? s.days_to_stockout}d`
                              : 'N/A'}
                          </TableCell>
                          <TableCell onClick={e => e.stopPropagation()}>
                            <ReorderIntentSelector
                              stockItemName={s.stock_item_name}
                              currentIntent={s.reorder_intent || 'normal'}
                            />
                          </TableCell>
                          <TableCell className="text-xs">
                            {s.last_sale_date
                              ? new Date(s.last_sale_date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: '2-digit' })
                              : 'Never'}
                          </TableCell>
                        </TableRow>
                        {expandedRow === s.stock_item_name && (
                          <TableRow key={`${s.stock_item_name}-detail`}>
                            <TableCell colSpan={10} className="bg-muted/30 p-4">
                              {renderExpandedDetail(s.stock_item_name)}
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  )
}
