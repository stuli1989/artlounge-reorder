import { useState, useMemo, useEffect, Fragment } from 'react'
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import StockTimelineChart from '@/components/StockTimelineChart'
import TransactionHistory from '@/components/TransactionHistory'
import CalculationBreakdown from '@/components/CalculationBreakdown'
import { ArrowLeft, Snowflake, ChevronDown, ChevronRight, Search } from 'lucide-react'

export default function DeadStock() {
  const { categoryName } = useParams<{ categoryName: string }>()
  const navigate = useNavigate()
  const decodedName = decodeURIComponent(categoryName || '')
  const queryClient = useQueryClient()

  const [search, setSearch] = useState('')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [thresholdInput, setThresholdInput] = useState('')
  const [saving, setSaving] = useState(false)

  // Load settings to get threshold
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
  })

  useEffect(() => {
    if (settings?.dead_stock_threshold_days && thresholdInput === '') {
      setThresholdInput(settings.dead_stock_threshold_days)
    }
  }, [settings, thresholdInput])

  const threshold = settings?.dead_stock_threshold_days || '30'

  // Load dead stock SKUs
  const { data: skus, isLoading } = useQuery({
    queryKey: ['skus', decodedName, 'dead_stock', threshold, search],
    queryFn: () => {
      const params: Record<string, string> = { dead_stock: 'true' }
      if (search) params.search = search
      return fetchSkus(decodedName, params)
    },
    enabled: !!decodedName,
  })

  // Sort by days_since_last_sale DESC (longest dead first)
  const sorted = useMemo(() =>
    [...(skus || [])].sort((a, b) => {
      const aD = a.days_since_last_sale ?? Infinity
      const bD = b.days_since_last_sale ?? Infinity
      return bD - aD
    }),
    [skus]
  )

  const thresholdMutation = useMutation({
    mutationFn: (val: string) => updateSetting('dead_stock_threshold_days', val),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skus'] })
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setSaving(false)
    },
  })

  const handleSaveThreshold = () => {
    const num = parseInt(thresholdInput, 10)
    if (isNaN(num) || num < 1) return
    setSaving(true)
    thresholdMutation.mutate(String(num))
  }

  const vel = (v: number) => (v * 30).toFixed(1)

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
              <ArrowLeft className="h-4 w-4 mr-1" /> Back
            </Button>
            <Snowflake className="h-5 w-5 text-blue-500" />
            <h2 className="text-xl font-semibold">Dead Stock — {decodedName}</h2>
            <span className="text-muted-foreground">{sorted.length} items</span>
          </div>
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
              disabled={saving || thresholdInput === threshold}
              onClick={handleSaveThreshold}
            >
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>

        {/* Summary */}
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Dead Stock Items</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">{sorted.length}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Threshold</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{threshold} days</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Longest Idle</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {sorted.length > 0
                  ? sorted[0].days_since_last_sale !== null
                    ? `${sorted[0].days_since_last_sale} days`
                    : 'Never sold'
                  : '-'}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Search */}
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search SKUs..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Table */}
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
                  <TableHead>Part No</TableHead>
                  <TableHead>SKU Name</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead>Last Sale</TableHead>
                  <TableHead className="text-right">Days Idle</TableHead>
                  <TableHead className="text-right">Zero Activity Days</TableHead>
                  <TableHead className="text-right">Total Vel /mo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((s: SkuMetrics) => (
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
                      <TableCell className="max-w-[250px] truncate" title={s.stock_item_name}>
                        <span className="inline-flex items-center gap-1">
                          {s.stock_item_name}
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
                      <TableCell className="text-right">{s.total_zero_activity_days}d</TableCell>
                      <TableCell className="text-right">{vel(s.effective_velocity ?? s.total_velocity)}</TableCell>
                    </TableRow>
                    {expandedRow === s.stock_item_name && (
                      <TableRow key={`${s.stock_item_name}-detail`}>
                        <TableCell colSpan={9} className="bg-muted/30 p-4">
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
                              <CalculationBreakdown categoryName={decodedName} stockItemName={s.stock_item_name} />
                            </TabsContent>
                          </Tabs>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </TooltipProvider>
  )
}
