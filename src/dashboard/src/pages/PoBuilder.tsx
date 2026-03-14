import { useState, useMemo, Fragment, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { fetchPoData, exportPo, matchSkusForPo } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import StatusBadge from '@/components/StatusBadge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import SkuSecondaryLine from '@/components/SkuSecondaryLine'
import TrendIndicator from '@/components/TrendIndicator'
import ClassificationExplainer from '@/components/ClassificationExplainer'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ArrowLeft, Download, Calendar, Flame, AlertTriangle, ClipboardList } from 'lucide-react'
import type { ReorderStatus, ReorderIntent, AbcClass, TrendDirection, SkuMatchResult, SkuMatchSummary, PoDataItem } from '@/lib/types'
import SkuInputDialog from '@/components/SkuInputDialog'
import SkuMatchReview from '@/components/SkuMatchReview'
import HelpTip from '@/components/HelpTip'

interface PoRow {
  stock_item_name: string
  part_no: string | null
  is_hazardous: boolean
  current_stock: number
  total_velocity: number
  days_to_stockout: number | null
  reorder_status: ReorderStatus
  suggested_qty: number | null
  reorder_intent: ReorderIntent
  abc_class: AbcClass | null
  trend_direction: TrendDirection | null
  sku_buffer: number
  included: boolean
  order_qty: number
  notes: string
}

interface RowOverride {
  included?: boolean
  order_qty?: number
  notes?: string
}

export default function PoBuilder() {
  const { categoryName } = useParams<{ categoryName: string }>()
  const navigate = useNavigate()
  const decodedName = decodeURIComponent(categoryName || '')

  const [searchParams] = useSearchParams()
  const fromDate = searchParams.get('from_date')
  const toDate = searchParams.get('to_date')

  const [leadTimeType, setLeadTimeType] = useState('default')
  const [customLeadTime, setCustomLeadTime] = useState(180)
  const [bufferOverride, setBufferOverride] = useState(false)
  const [bufferValue, setBufferValue] = useState(1.3)
  const [includeWarning, setIncludeWarning] = useState(true)
  const [includeOk, setIncludeOk] = useState(false)

  // Subset PO state
  const [showSkuInput, setShowSkuInput] = useState(false)
  const [subsetMode, setSubsetMode] = useState(false)
  const [subsetRawData, setSubsetRawData] = useState<PoDataItem[] | null>(null)
  const [matchResults, setMatchResults] = useState<{ matches: SkuMatchResult[]; summary: SkuMatchSummary } | null>(null)
  const [showMatchReview, setShowMatchReview] = useState(false)

  // Auto-open dialog when accessing /po directly (no brand)
  useEffect(() => {
    if (!decodedName && !subsetMode) setShowSkuInput(true)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const matchMutation = useMutation({
    mutationFn: matchSkusForPo,
    onSuccess: (data) => {
      setMatchResults({ matches: data.matches, summary: data.summary })
      if (data.summary.fuzzy === 0 && data.summary.unmatched === 0) {
        // All exact — skip review, go straight to PO table
        setSubsetMode(true)
        setSubsetRawData(data.po_data)
        setShowSkuInput(false)
      } else {
        setShowMatchReview(true)
        setShowSkuInput(false)
      }
    },
  })

  const handleSkuSubmit = (skuNames: string[]) => {
    matchMutation.mutate({
      sku_names: skuNames.slice(0, 500),
      lead_time: leadTime,
      buffer: bufferOverride ? bufferValue : undefined,
      from_date: fromDate ?? undefined,
      to_date: toDate ?? undefined,
    })
  }

  const activateSubsetFromReview = (acceptedNames: string[]) => {
    const accepted = new Set(acceptedNames)
    const filtered = (matchMutation.data?.po_data ?? []).filter(
      item => accepted.has(item.stock_item_name)
    )
    setSubsetMode(true)
    setSubsetRawData(filtered)
    setShowMatchReview(false)
  }

  const clearSubsetMode = () => {
    setSubsetMode(false)
    setSubsetRawData(null)
    setMatchResults(null)
    setShowMatchReview(false)
    setOverrides({})
  }

  const leadTime = leadTimeType === 'sea' ? 180 : leadTimeType === 'air' ? 30 : customLeadTime

  const { data: poData, isLoading } = useQuery({
    queryKey: ['poData', decodedName, leadTime, bufferOverride, bufferValue, includeWarning, includeOk, fromDate, toDate],
    queryFn: () => {
      const params: Record<string, string | number | boolean> = {
        lead_time: leadTime,
        include_warning: includeWarning,
        include_ok: includeOk,
      }
      if (bufferOverride) params.buffer = bufferValue
      if (fromDate) params.from_date = fromDate
      if (toDate) params.to_date = toDate
      return fetchPoData(decodedName, params)
    },
    enabled: !!decodedName,
  })

  const [overrides, setOverrides] = useState<Record<string, RowOverride>>({})

  const rows: PoRow[] = useMemo(() => {
    const source = subsetMode && subsetRawData ? subsetRawData : (poData || [])
    return source.map(item => {
      const o = overrides[item.stock_item_name] || {}
      return {
        ...item,
        sku_buffer: item.sku_buffer ?? 1.3,
        included: o.included ?? true,
        order_qty: o.order_qty ?? (item.suggested_qty || 0),
        notes: o.notes ?? '',
      }
    })
  }, [poData, overrides, subsetMode, subsetRawData])

  const toggleRow = (name: string) => {
    setOverrides(prev => {
      const cur = prev[name] || {}
      return { ...prev, [name]: { ...cur, included: !(cur.included ?? true) } }
    })
  }

  const updateQty = (name: string, qty: number) => {
    setOverrides(prev => {
      const cur = prev[name] || {}
      return { ...prev, [name]: { ...cur, order_qty: qty } }
    })
  }

  const updateNotes = (name: string, notes: string) => {
    setOverrides(prev => {
      const cur = prev[name] || {}
      return { ...prev, [name]: { ...cur, notes } }
    })
  }

  const includedRows = rows.filter(r => r.included)
  const totalItems = includedRows.length
  const totalQty = includedRows.reduce((sum, r) => sum + r.order_qty, 0)

  const hazardousIncluded = useMemo(() => rows.filter(r => r.included && r.is_hazardous), [rows])
  const hasHazardousConflict = leadTimeType === 'air' && hazardousIncluded.length > 0

  const handleExport = async () => {
    const payload = {
      category_name: subsetMode ? 'CUSTOM' : decodedName,
      supplier_name: '',
      lead_time: leadTime,
      buffer: bufferOverride ? bufferValue : (includedRows.length > 0 ? includedRows.reduce((s, r) => s + r.sku_buffer, 0) / includedRows.length : 1.3),
      items: includedRows.map(r => ({
        stock_item_name: r.stock_item_name,
        part_no: r.part_no || '',
        order_qty: r.order_qty,
        current_stock: r.current_stock,
        velocity_per_month: r.total_velocity * 30,
        days_to_stockout: r.days_to_stockout,
        notes: r.notes,
      })),
    }

    const blob = await exportPo(payload)
    const url = window.URL.createObjectURL(new Blob([blob]))
    const link = document.createElement('a')
    link.href = url
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    link.setAttribute('download', `PO-${decodedName.slice(0, 3).toUpperCase()}-${today}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  return (
    <TooltipProvider>
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate(`/brands/${categoryName}/skus`)}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to SKUs
        </Button>
        <h2 className="text-xl font-semibold">
          Purchase Order{subsetMode ? ' — Custom List' : decodedName ? ` — ${decodedName}` : ''}
        </h2>
        <div className="ml-auto">
          <ClassificationExplainer />
        </div>
      </div>

      {/* Active analysis period indicator */}
      {(fromDate || toDate) && (
        <div className="text-xs text-muted-foreground bg-muted/50 rounded px-3 py-1.5 border flex items-center gap-1.5">
          <Calendar className="h-3.5 w-3.5" />
          Analysis period: <strong className="text-foreground">{fromDate || 'FY start'} — {toDate || 'today'}</strong>
          <span>(velocities recalculated for this range)</span>
        </div>
      )}

      {/* Settings */}
      <Card data-tour="po-config">
        <CardHeader>
          <CardTitle className="text-sm">Order Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-6">
            <div className="space-y-2">
              <Label>Lead Time</Label>
              <Select value={leadTimeType} onValueChange={v => { if (v) { setLeadTimeType(v); if (v === 'sea') setCustomLeadTime(180); if (v === 'air') setCustomLeadTime(30); } }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sea">Sea Freight (180d)</SelectItem>
                  <SelectItem value="air">Air Freight (30d)</SelectItem>
                  <SelectItem value="custom">Custom</SelectItem>
                </SelectContent>
              </Select>
              {leadTimeType === 'custom' && (
                <Input
                  type="number"
                  value={customLeadTime}
                  onChange={e => setCustomLeadTime(Number(e.target.value))}
                  className="mt-1"
                />
              )}
            </div>

            <div className="space-y-2">
              {bufferOverride ? (
                <>
                  <Label>Safety Buffer Override: {bufferValue.toFixed(1)}x</Label>
                  <Slider
                    value={[bufferValue]}
                    onValueChange={v => setBufferValue(Array.isArray(v) ? v[0] : v)}
                    min={1.0}
                    max={2.0}
                    step={0.1}
                    className="mt-2"
                  />
                  <button
                    className="text-xs text-blue-600 hover:underline"
                    onClick={() => setBufferOverride(false)}
                  >
                    Reset to per-SKU buffers
                  </button>
                </>
              ) : (
                <>
                  <Label className="text-muted-foreground">Safety Buffer: per-SKU</Label>
                  <Slider
                    value={[1.3]}
                    min={1.0}
                    max={2.0}
                    step={0.1}
                    className="mt-2 opacity-40"
                    disabled
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Each SKU has a computed buffer based on its ABC classification.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setBufferOverride(true)}
                  >
                    Override all
                  </Button>
                </>
              )}
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Switch checked={includeWarning} onCheckedChange={setIncludeWarning} />
                <Label>Include Warning items</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={includeOk} onCheckedChange={setIncludeOk} />
                <Label>Include OK items</Label>
              </div>
            </div>

            <div className="flex items-end gap-2">
              <Button variant="outline" onClick={() => setShowSkuInput(true)}>
                <ClipboardList className="h-4 w-4 mr-1" /> Import SKU List
              </Button>
              <Button onClick={handleExport} disabled={totalItems === 0} data-tour="po-export">
                <Download className="h-4 w-4 mr-1" /> Export Excel
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Hazardous warning */}
      {hasHazardousConflict && (
        <Alert className="border-amber-300 bg-amber-50">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="flex items-center justify-between">
            <span className="text-amber-800">
              <strong>{hazardousIncluded.length}</strong> hazardous item(s) cannot ship by air. Switch to Sea Freight or uncheck them.
            </span>
            <Button
              variant="outline"
              size="sm"
              className="border-amber-400 text-amber-700 hover:bg-amber-100 ml-4"
              onClick={() => setLeadTimeType('sea')}
            >
              Switch to Sea Freight
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Subset mode banner */}
      {subsetMode && (
        <div className="text-sm bg-blue-50 border border-blue-200 rounded-lg px-4 py-2.5 flex items-center justify-between">
          <span className="text-blue-800">
            <strong>Subset mode:</strong> Showing {rows.length} imported SKU{rows.length !== 1 ? 's' : ''} (may span multiple brands)
          </span>
          <Button variant="ghost" size="sm" className="text-blue-700 hover:text-blue-900" onClick={clearSubsetMode}>
            Clear & return to full brand
          </Button>
        </div>
      )}

      {/* Match review (shown after fuzzy/unmatched results) */}
      {showMatchReview && matchResults && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Review SKU Matches</CardTitle>
          </CardHeader>
          <CardContent>
            <SkuMatchReview
              matches={matchResults.matches}
              summary={matchResults.summary}
              onConfirm={activateSubsetFromReview}
              onBack={() => {
                setShowMatchReview(false)
                setShowSkuInput(true)
              }}
            />
          </CardContent>
        </Card>
      )}

      {/* Table — two-line rows */}
      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Loading PO data...</div>
      ) : (
        <div className="border rounded-lg" data-tour="po-table">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10"></TableHead>
                <TableHead className="w-[80px]">Status</TableHead>
                <TableHead>SKU Name</TableHead>
                <TableHead className="text-right">Stock</TableHead>
                <TableHead className="text-right">Velocity /mo</TableHead>
                <TableHead className="text-right">Days Left</TableHead>
                <TableHead className="text-right">Suggested <HelpTip tip="Recommended order: enough to cover lead time + buffer at current velocity, minus current stock." helpAnchor="reorder-quantity" /></TableHead>
                <TableHead className="text-right w-[100px]">Order Qty</TableHead>
                <TableHead className="w-[150px]">Notes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(r => (
                <Fragment key={r.stock_item_name}>
                  <TableRow className={cn(!r.included && 'opacity-40', hasHazardousConflict && r.is_hazardous && r.included && 'bg-amber-50', r.reorder_intent === 'must_stock' && 'border-l-2 border-l-purple-400')}>
                    <TableCell>
                      <Checkbox checked={r.included} onCheckedChange={() => toggleRow(r.stock_item_name)} />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={r.reorder_status as 'critical' | 'warning' | 'ok' | 'out_of_stock' | 'no_data'} />
                    </TableCell>
                    <TableCell className="max-w-[250px] truncate" title={r.stock_item_name}>
                      <span className="inline-flex items-center gap-1">
                        {r.is_hazardous && <Flame className="h-3.5 w-3.5 text-amber-500 fill-amber-500 shrink-0" />}
                        {r.stock_item_name}
                        {r.reorder_intent === 'must_stock' && (
                          <Badge className="bg-purple-100 text-purple-700 hover:bg-purple-100 text-[10px] px-1 py-0">Must Stock</Badge>
                        )}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">{r.current_stock}</TableCell>
                    <TableCell className="text-right">
                      <span className="inline-flex items-center gap-1 justify-end">
                        {(r.total_velocity * 30).toFixed(1)}
                        <TrendIndicator direction={r.trend_direction} ratio={null} />
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {r.days_to_stockout === null ? 'N/A' : r.days_to_stockout === 0 ? 'OUT' : `${r.days_to_stockout}d`}
                    </TableCell>
                    <TableCell className="text-right">{r.suggested_qty ?? '-'}</TableCell>
                    <TableCell className="text-right">
                      <Input
                        type="number"
                        value={r.order_qty}
                        onChange={e => updateQty(r.stock_item_name, Number(e.target.value))}
                        className="w-20 text-right"
                        disabled={!r.included}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={r.notes}
                        onChange={e => updateNotes(r.stock_item_name, e.target.value)}
                        placeholder="Notes"
                        className="text-xs"
                        disabled={!r.included}
                      />
                    </TableCell>
                  </TableRow>
                  {/* Secondary metadata line */}
                  <TableRow className="border-0">
                    <TableCell colSpan={9} className="pt-0 pb-2 pl-12">
                      <span className="inline-flex items-center gap-3">
                        <SkuSecondaryLine
                          abc_class={r.abc_class}
                          xyz_class={null}
                          part_no={r.part_no}
                          is_hazardous={r.is_hazardous}
                        />
                        {!bufferOverride && (
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                            Buffer: {r.sku_buffer.toFixed(1)}x
                          </Badge>
                        )}
                      </span>
                    </TableCell>
                  </TableRow>
                </Fragment>
              ))}
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-8 text-muted-foreground">
                    No items need reordering
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Footer Totals */}
      <div className="flex justify-between items-center px-4 py-3 bg-muted rounded-lg">
        <span className="text-sm font-medium">Total Items: {totalItems}</span>
        <span className="text-sm font-medium">Total Order Quantity: {totalQty.toLocaleString()}</span>
      </div>
    </div>
      <SkuInputDialog
        open={showSkuInput}
        onOpenChange={setShowSkuInput}
        onSubmit={handleSkuSubmit}
        isLoading={matchMutation.isPending}
      />
    </TooltipProvider>
  )
}
