import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchBreakdown, createOverride, deleteOverride, updateXyzBuffer } from '@/lib/api'
import type { BreakdownResponse, OverrideInfo } from '@/lib/types'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { ArrowRight, Info, Pencil, AlertTriangle, X, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'
import StatusBadge from '@/components/StatusBadge'
import HelpTip from '@/components/HelpTip'
import { useIsMobile } from '@/hooks/useIsMobile'
import { BottomSheet } from '@/components/mobile/BottomSheet'
import type { ReorderStatus } from '@/lib/types'

// ─── Constants ───────────────────────────────────────────────────────────────

const confidenceColors = {
  high: 'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-red-100 text-red-700',
}

const statusColors: Record<string, string> = {
  healthy: 'bg-green-100 text-green-700 border-green-200',
  reorder: 'bg-amber-100 text-amber-700 border-amber-200',
  urgent: 'bg-red-100 text-red-700 border-red-200',
  lost_sales: 'bg-red-200 text-red-800 border-red-300',
  dead_stock: 'bg-gray-100 text-gray-500 border-gray-200',
  out_of_stock: 'bg-gray-50 text-gray-400 border-gray-200',
  no_data: 'bg-gray-100 text-gray-500 border-gray-200',
}

const verdictBgColors: Record<string, string> = {
  healthy: 'bg-green-50 border-green-300',
  reorder: 'bg-amber-50 border-amber-300',
  urgent: 'bg-red-50 border-red-300',
  lost_sales: 'bg-red-100 border-red-400',
  dead_stock: 'bg-gray-50 border-gray-300',
  out_of_stock: 'bg-gray-50 border-gray-300',
  no_data: 'bg-gray-50 border-gray-300',
}

// ─── Shared helper components ────────────────────────────────────────────────

function FlowBox({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={`rounded-lg border px-4 py-3 text-center ${className || ''}`}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  )
}

function FlowArrow() {
  return <ArrowRight className="h-5 w-5 text-muted-foreground shrink-0 mt-3" />
}

function InStockBar({ data }: { data: BreakdownResponse }) {
  const { velocity, date_range } = data
  if (!velocity.in_stock_periods.length) return null

  const rangeStart = new Date(date_range.from_date).getTime()
  const rangeEnd = new Date(date_range.to_date).getTime()
  const totalRange = rangeEnd - rangeStart
  if (totalRange <= 0) return null
  const msPerDay = 86400000

  return (
    <div className="space-y-1">
      <div className="text-xs text-muted-foreground">Active periods (green) vs inactive (red)</div>
      <div className="relative h-6 rounded bg-red-200 overflow-hidden" title={`${velocity.out_of_stock_days} inactive days`}>
        {velocity.in_stock_periods.map((p, i) => {
          const start = new Date(p.from).getTime()
          const end = new Date(p.to).getTime()
          const left = ((start - rangeStart) / totalRange) * 100
          const width = ((end - start + msPerDay) / (totalRange + msPerDay)) * 100
          return (
            <div
              key={i}
              className="absolute top-0 bottom-0 bg-green-400 rounded-sm"
              style={{ left: `${left}%`, width: `${width}%` }}
              title={`${p.from} to ${p.to} (${p.days} days)`}
            />
          )
        })}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{date_range.from_date}</span>
        <span>{date_range.to_date}</span>
      </div>
    </div>
  )
}

// ─── Override components (kept unchanged) ────────────────────────────────────

function OverrideBadge({ ovr }: { ovr: OverrideInfo }) {
  if (ovr.is_stale) {
    return (
      <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 gap-1">
        <AlertTriangle className="h-3 w-3" />
        Override stale — drift {ovr.drift_pct?.toFixed(0)}%
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 gap-1">
      <Pencil className="h-3 w-3" />
      Override: {ovr.value} units
    </Badge>
  )
}

function OverrideForm({
  fieldName,
  label,
  currentOverride,
  stockItemName,
  categoryName,
}: {
  fieldName: string
  label: string
  currentOverride?: OverrideInfo
  stockItemName: string
  categoryName?: string
}) {
  const isMobile = useIsMobile()
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState(currentOverride?.value?.toString() || '')
  const [reason, setReason] = useState('')
  const [holdFromPo, setHoldFromPo] = useState(false)
  const queryClient = useQueryClient()

  const invalidateRelated = () => {
    queryClient.invalidateQueries({ queryKey: ['breakdown', categoryName, stockItemName] })
    queryClient.invalidateQueries({ queryKey: ['skus', categoryName] })
    queryClient.invalidateQueries({ queryKey: ['poData', categoryName] })
    queryClient.invalidateQueries({ queryKey: ['overrides'] })
  }

  const createMut = useMutation({
    mutationFn: createOverride,
    onSuccess: () => {
      invalidateRelated()
      setOpen(false)
    },
  })

  const removeMut = useMutation({
    mutationFn: () => deleteOverride(currentOverride!.id, 'Removed by user'),
    onSuccess: () => {
      invalidateRelated()
      setOpen(false)
    },
  })

  const handleOpen = () => {
    setValue(currentOverride?.value?.toString() || '')
    setReason('')
    setHoldFromPo(currentOverride?.hold_from_po || false)
    setOpen(true)
  }

  const formContent = (
    <div className="space-y-4 py-2">
      {fieldName !== 'note' && (
        <div className="space-y-2">
          <Label htmlFor="override-value">Value</Label>
          <Input
            id="override-value"
            type="number"
            inputMode={isMobile ? 'decimal' : undefined}
            step="any"
            placeholder="Enter value"
            value={value}
            onChange={e => setValue(e.target.value)}
          />
        </div>
      )}
      <div className="space-y-2">
        <Label htmlFor="override-reason">Reason</Label>
        <textarea
          id="override-reason"
          placeholder="Why are you making this change?"
          value={reason}
          onChange={e => setReason(e.target.value)}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[80px] resize-y"
        />
      </div>
      <div className="flex items-center gap-2">
        <Checkbox
          id="hold-po"
          checked={holdFromPo}
          onCheckedChange={(checked) => setHoldFromPo(checked === true)}
        />
        <Label htmlFor="hold-po" className="text-sm font-normal cursor-pointer">
          Hold from PO suggestions
        </Label>
      </div>
      {createMut.isError && (
        <div className="text-sm text-red-600">Failed to save override</div>
      )}
      <div className={`flex ${isMobile ? 'flex-col' : ''} gap-2 pt-2`}>
        <Button variant="outline" onClick={() => setOpen(false)} className={isMobile ? 'w-full' : ''}>Cancel</Button>
        <Button
          className={isMobile ? 'w-full' : ''}
          disabled={(!value && fieldName !== 'note') || !reason || createMut.isPending}
          onClick={() => createMut.mutate({
            stock_item_name: stockItemName,
            field_name: fieldName,
            override_value: fieldName !== 'note' ? parseFloat(value) : undefined,
            note: reason,
            hold_from_po: holdFromPo,
          })}
        >
          {createMut.isPending ? 'Saving...' : 'Save'}
        </Button>
      </div>
    </div>
  )

  return (
    <>
      <div className="flex items-center gap-2 flex-wrap">
        {currentOverride && <OverrideBadge ovr={currentOverride} />}
        <Button variant="outline" size="sm" onClick={handleOpen}>
          <Pencil className="h-3 w-3 mr-1" />
          {currentOverride ? 'Edit' : `Adjust ${label}`}
        </Button>
        {currentOverride && (
          <Button variant="ghost" size="sm" className="text-red-600" onClick={() => removeMut.mutate()}>
            <X className="h-3 w-3 mr-1" /> Remove
          </Button>
        )}
      </div>

      {isMobile ? (
        <BottomSheet open={open} onOpenChange={setOpen} title={`Override ${label}`}>
          {formContent}
        </BottomSheet>
      ) : (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Override {label}</DialogTitle>
            </DialogHeader>
            {formContent}
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}

function BufferModeSelector({
  stockItemName,
  categoryName,
  currentValue,
  bufferMode,
}: {
  stockItemName: string
  categoryName: string
  currentValue: boolean | null
  bufferMode: 'abc_only' | 'abc_xyz'
}) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (val: boolean | null) => updateXyzBuffer(stockItemName, val),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['breakdown', categoryName, stockItemName] })
      queryClient.invalidateQueries({ queryKey: ['skus', categoryName] })
    },
  })

  const selectValue = currentValue === null ? 'global' : currentValue ? 'xyz' : 'abc'
  const globalLabel = `Follow global (${bufferMode === 'abc_xyz' && currentValue === null ? 'ABC×XYZ' : 'ABC only'})`

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">Buffer mode: <HelpTip tip="Safety stock multiplier. Global uses ABC-class defaults. Per-SKU lets you set a custom buffer." helpAnchor="lead-time-buffer" /></span>
      <Select
        value={selectValue}
        onValueChange={(v) => {
          if (!v) return
          const val = v === 'global' ? null : v === 'xyz' ? true : false
          mutation.mutate(val)
        }}
      >
        <SelectTrigger className="w-[220px] h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="global">{globalLabel}</SelectItem>
          <SelectItem value="xyz">Use XYZ buffer</SelectItem>
          <SelectItem value="abc">ABC only</SelectItem>
        </SelectContent>
      </Select>
      {mutation.isPending && <span className="text-xs text-muted-foreground">Saving...</span>}
    </div>
  )
}

// ─── New helper components ───────────────────────────────────────────────────

function CollapsibleSection({
  title,
  subtitle,
  defaultOpen,
  children,
}: {
  title: string
  subtitle?: React.ReactNode
  defaultOpen: boolean
  children: React.ReactNode
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        type="button"
        className="flex items-center justify-between w-full px-4 py-3 text-left hover:bg-muted/30 transition-colors rounded-lg"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div>
          <span className="text-sm font-semibold">{title}</span>
          {subtitle && <span className="text-xs text-muted-foreground ml-2">{subtitle}</span>}
        </div>
        {isOpen ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        )}
      </button>
      {isOpen && <div className="px-4 pb-4 pt-0">{children}</div>}
    </div>
  )
}

function MethodologySection({
  number,
  title,
  children,
}: {
  number: number
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="border border-gray-200 rounded-lg bg-gray-50/50">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200">
        <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold shrink-0">
          {number}
        </span>
        <span className="text-sm font-medium">{title}</span>
      </div>
      <div className="px-3 py-3 space-y-3 overflow-x-auto">{children}</div>
    </div>
  )
}

function generateVerdict(data: BreakdownResponse): { text: string; status: ReorderStatus } {
  const { velocity, stockout, reorder } = data
  const status = reorder.status as ReorderStatus

  const qty = reorder.suggested_qty
  const days = stockout.days_to_stockout
  const leadTime = reorder.supplier_lead_time

  // Determine dominant channel
  const channels = [
    { name: 'Wholesale', vel: velocity.wholesale.monthly_velocity },
    { name: 'Online', vel: velocity.online.monthly_velocity },
    { name: 'Store', vel: velocity.store.monthly_velocity },
  ]
  const dominant = channels.reduce((a, b) => (b.vel > a.vel ? b : a))
  const dominantChannel = dominant.vel > 0 ? dominant.name : null
  const monthlyVel = velocity.total.monthly_velocity

  switch (status) {
    case 'urgent':
      return {
        text: `Order ${qty ?? '?'} units now. ${dominantChannel ? `${dominantChannel} is driving demand at ${monthlyVel}/mo.` : `Demand is ${monthlyVel}/mo.`} At current velocity you have ~${days ?? 0} days of stock, but with ${leadTime}-day lead time you need to act today.`,
        status,
      }
    case 'reorder':
      return {
        text: `Time to order ${qty ?? '?'} units. You have ~${days ?? 0} days of stock — include this in your next PO.`,
        status,
      }
    case 'healthy':
      return {
        text: `Pipeline is flowing. You have ~${days ?? '?'} days of stock, well above the ${leadTime}-day lead time. Keep ordering on your normal cycle.`,
        status,
      }
    case 'out_of_stock':
      return {
        text: `Out of stock with no measured demand. Investigate whether to restock — demand may exist but can't be measured without inventory.`,
        status,
      }
    case 'lost_sales':
      return {
        text: `You're losing sales — proven demand at ${monthlyVel}/mo but zero stock. Order ${qty ?? '?'} units immediately.`,
        status,
      }
    case 'dead_stock':
      return {
        text: `Stock on hand but no recent demand detected. Monitor or mark as do-not-reorder if intentional.`,
        status,
      }
    case 'no_data':
    default:
      return {
        text: 'Insufficient data to make a recommendation. No velocity data available.',
        status: 'no_data',
      }
  }
}

// ─── Main component ──────────────────────────────────────────────────────────

export default function CalculationBreakdown({
  categoryName,
  stockItemName,
  fromDate,
  toDate,
}: {
  categoryName: string
  stockItemName: string
  fromDate?: string
  toDate?: string
}) {
  const isMobile = useIsMobile()
  const { data, isLoading, error } = useQuery({
    queryKey: ['breakdown', categoryName, stockItemName, fromDate, toDate],
    queryFn: () => fetchBreakdown(categoryName, stockItemName, {
      from_date: fromDate,
      to_date: toDate,
    }),
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading) return <div className="text-center py-8 text-muted-foreground">Loading breakdown...</div>
  if (error) return <div className="text-center py-8 text-red-500">Failed to load breakdown</div>
  if (!data) return null

  const { data_source, velocity, stockout, reorder, effective_values, date_range } = data
  const overrides = data_source.overrides || {}
  const verdict = generateVerdict(data)

  const inStockPct = velocity.in_stock_days + velocity.out_of_stock_days > 0
    ? Math.round((velocity.in_stock_days / (velocity.in_stock_days + velocity.out_of_stock_days)) * 100)
    : 0

  return (
    <div className="space-y-4">

      {/* ── Layer 1: Verdict (always visible) ─────────────────────────────── */}
      <div className={`rounded-lg border-2 p-4 ${verdictBgColors[verdict.status] || verdictBgColors.no_data}`}>
        <div className="flex items-start gap-3">
          <StatusBadge status={verdict.status} />
          <div className="flex-1 min-w-0">
            <p className="text-sm leading-relaxed">{verdict.text}</p>
          </div>
        </div>
        <div className="flex gap-4 mt-3 text-xs text-muted-foreground">
          {data_source.data_as_of && (
            <span>Data as of: {new Date(data_source.data_as_of).toLocaleDateString('en-IN', { dateStyle: 'medium' })}</span>
          )}
          <span>Analysis: {date_range.from_date} to {date_range.to_date} ({date_range.total_days_in_range}d)</span>
        </div>
      </div>

      {/* ── Layer 2: Key Assumptions (collapsible, expanded by default) ──── */}
      <CollapsibleSection title="Key Assumptions" subtitle="inputs driving this recommendation" defaultOpen={true}>
        <div className="space-y-4">
          {/* Assumptions table */}
          <div className="border rounded-lg overflow-hidden overflow-x-auto">
            <table className="w-full text-sm">
              <tbody>
                {/* Lead Time */}
                <tr className="border-b">
                  <td className="px-3 py-2 text-muted-foreground font-medium w-[140px]">Lead Time</td>
                  <td className="px-3 py-2">
                    {reorder.supplier_lead_time}d
                    {reorder.supplier_name && (
                      <span className="text-muted-foreground"> ({reorder.supplier_name})</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Link to="/suppliers" className="text-xs text-blue-600 hover:underline inline-flex items-center gap-1">
                      Suppliers <ExternalLink className="h-3 w-3" />
                    </Link>
                  </td>
                </tr>
                {/* Safety Buffer */}
                <tr className="border-b">
                  <td className="px-3 py-2 text-muted-foreground font-medium">Safety Buffer</td>
                  <td className="px-3 py-2">
                    {reorder.buffer_multiplier}x
                    <span className="text-muted-foreground"> ({reorder.buffer_mode === 'abc_xyz' ? 'ABC×XYZ' : 'ABC only'})</span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    {/* BufferModeSelector is below the table */}
                  </td>
                </tr>
                {/* Total Velocity */}
                <tr className="border-b">
                  <td className="px-3 py-2 text-muted-foreground font-medium">Total Velocity</td>
                  <td className="px-3 py-2">
                    <span className="font-semibold">{velocity.total.monthly_velocity}/mo</span>
                    <span className="text-muted-foreground text-xs ml-1">
                      (W: {velocity.wholesale.monthly_velocity} + O: {velocity.online.monthly_velocity} + S: {velocity.store.monthly_velocity})
                    </span>
                    {effective_values.velocity_source === 'override' && (
                      <Badge variant="outline" className="ml-2 bg-blue-50 text-blue-700 border-blue-200 text-xs">overridden</Badge>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {/* Override form is below the table */}
                  </td>
                </tr>
                {/* Current Stock */}
                <tr className="border-b">
                  <td className="px-3 py-2 text-muted-foreground font-medium">Current Stock</td>
                  <td className="px-3 py-2">
                    <span className="font-semibold">{effective_values.current_stock} units</span>
                    {effective_values.stock_source === 'override' && (
                      <>
                        <span className="text-muted-foreground text-xs ml-1">
                          (Ledger balance: {data_source.closing_balance_from_ledger ?? 'N/A'})
                        </span>
                        <Badge variant="outline" className="ml-2 bg-blue-50 text-blue-700 border-blue-200 text-xs">overridden</Badge>
                      </>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {/* Override form is below the table */}
                  </td>
                </tr>
                {/* In-Stock Days */}
                <tr>
                  <td className="px-3 py-2 text-muted-foreground font-medium">In-Stock Days</td>
                  <td className="px-3 py-2">
                    <span className={`font-medium ${inStockPct >= 70 ? 'text-green-600' : inStockPct >= 40 ? 'text-amber-600' : 'text-red-600'}`}>
                      {velocity.in_stock_days}
                    </span>
                    <span className="text-muted-foreground"> of {velocity.in_stock_days + velocity.out_of_stock_days} ({inStockPct}%)</span>
                    <span className="text-xs text-muted-foreground ml-2">
                      {inStockPct >= 70 ? '— good data coverage' : inStockPct >= 40 ? '— moderate coverage' : '— limited coverage'}
                    </span>
                  </td>
                  <td className="px-3 py-2"></td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Buffer mode selector */}
          <BufferModeSelector
            stockItemName={stockItemName}
            categoryName={categoryName}
            currentValue={reorder.use_xyz_buffer}
            bufferMode={reorder.buffer_mode}
          />

          {/* Override forms for velocity and stock */}
          <div className="space-y-2" data-tour="override-buttons">
            <OverrideForm
              fieldName="total_velocity"
              label="total velocity"
              currentOverride={overrides.total_velocity}
              stockItemName={stockItemName}
              categoryName={categoryName}
            />
            <OverrideForm
              fieldName="current_stock"
              label="Stock"
              currentOverride={overrides.current_stock}
              stockItemName={stockItemName}
              categoryName={categoryName}
            />
          </div>

          {/* Note override */}
          <div className="pt-2 border-t">
            <OverrideForm
              fieldName="note"
              label="Note"
              currentOverride={overrides.note}
              stockItemName={stockItemName}
              categoryName={categoryName}
            />
          </div>
        </div>
      </CollapsibleSection>

      {/* ── Layer 3: Methodology & Formulas (collapsible, collapsed) ─────── */}
      <CollapsibleSection title="Methodology & Formulas" subtitle={<>how we arrived at this recommendation <HelpTip tip="Expand to see exactly how each number was calculated, with formulas and source data." helpAnchor="velocity" /></>} defaultOpen={false}>
        <div className="space-y-3">

          {/* 1. Velocity */}
          <MethodologySection number={1} title="Velocity">
            <div className="text-xs text-muted-foreground mb-2">
              Units sold ÷ in-stock days × 30 = monthly velocity
            </div>

            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Channel</TableHead>
                    <TableHead className="text-right">Units Sold</TableHead>
                    <TableHead className="text-right">/ Active Days</TableHead>
                    <TableHead className="text-right">= Daily Rate</TableHead>
                    <TableHead className="text-right">×30 = Monthly</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(['wholesale', 'online', 'store'] as const).map(ch => {
                    const c = velocity[ch]
                    const fieldName = `${ch}_velocity` as const
                    const ovr = overrides[fieldName]
                    return (
                      <TableRow key={ch}>
                        <TableCell className="capitalize">
                          {ch}
                          {ovr && <span className="ml-1"><OverrideBadge ovr={ovr} /></span>}
                        </TableCell>
                        <TableCell className="text-right">{c.total_units}</TableCell>
                        <TableCell className="text-right text-muted-foreground">/ {velocity.in_stock_days}</TableCell>
                        <TableCell className="text-right">{c.daily_velocity}</TableCell>
                        <TableCell className="text-right font-semibold">{c.monthly_velocity}</TableCell>
                      </TableRow>
                    )
                  })}
                  <TableRow className="border-t-2 font-semibold">
                    <TableCell>Total</TableCell>
                    <TableCell className="text-right">{velocity.total.total_units}</TableCell>
                    <TableCell className="text-right text-muted-foreground">/ {velocity.in_stock_days}</TableCell>
                    <TableCell className="text-right">{velocity.total.daily_velocity}</TableCell>
                    <TableCell className="text-right">{velocity.total.monthly_velocity}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>

            <div className="flex items-center gap-2 mt-2">
              <Badge variant="outline" className={confidenceColors[velocity.confidence]}>
                {velocity.confidence} confidence
              </Badge>
              <span className="text-xs text-muted-foreground">{velocity.confidence_reason}</span>
            </div>

            <div className="font-mono text-xs text-muted-foreground bg-white/60 rounded p-2 mt-2 overflow-x-auto break-all">
              {velocity.formula}
            </div>

            {/* Per-channel override forms */}
            <div className="space-y-1 mt-2">
              {(['wholesale', 'online', 'store'] as const).map(ch => {
                const fieldName = `${ch}_velocity` as const
                const ovr = overrides[fieldName]
                return (
                  <OverrideForm
                    key={ch}
                    fieldName={fieldName}
                    label={`${ch} velocity`}
                    currentOverride={ovr}
                    stockItemName={stockItemName}
                    categoryName={categoryName}
                  />
                )
              })}
            </div>
          </MethodologySection>

          {/* 2. In-Stock Days */}
          <MethodologySection number={2} title="In-Stock Days">
            <InStockBar data={data} />
            <div className="flex flex-wrap gap-4 text-sm mt-2">
              <div>
                <span className="text-muted-foreground">Active: </span>
                <span className="font-medium text-green-600">{velocity.in_stock_days} days ({velocity.in_stock_pct}%)</span>
              </div>
              <div>
                <span className="text-muted-foreground">Inactive: </span>
                <span className="font-medium text-red-600">{velocity.out_of_stock_days} days</span>
              </div>
            </div>
            {velocity.out_of_stock_days > 0 && (
              <div className="flex items-start gap-1.5 text-xs text-muted-foreground bg-amber-50 border border-amber-200 rounded p-2 mt-2">
                <Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-600" />
                {velocity.out_of_stock_exclusion_reason}
              </div>
            )}
          </MethodologySection>

          {/* 3. Stockout Projection */}
          <MethodologySection number={3} title="Stockout Projection">
            <div className={`flex ${isMobile ? 'flex-col' : 'items-center'} gap-2 flex-wrap`}>
              <FlowBox
                label={effective_values.stock_source === 'override' ? 'Stock (override)' : 'Stock'}
                value={`${stockout.current_stock}`}
                className={effective_values.stock_source === 'override' ? 'bg-blue-100 border-blue-300' : 'bg-blue-50 border-blue-200'}
              />
              <FlowArrow />
              <FlowBox
                label={effective_values.velocity_source === 'override' ? '÷ Burn rate (override)' : '÷ Burn rate'}
                value={`${stockout.daily_burn_rate}/day`}
                className={effective_values.velocity_source === 'override' ? 'bg-blue-100 border-blue-300' : 'bg-orange-50 border-orange-200'}
              />
              <FlowArrow />
              <FlowBox
                label="= Days left"
                value={stockout.days_to_stockout !== null ? `${stockout.days_to_stockout}` : 'N/A'}
                className="bg-purple-50 border-purple-200"
              />
            </div>
            {stockout.estimated_stockout_date && (
              <div className="text-sm text-muted-foreground mt-2">
                Estimated stockout: <span className="font-medium">{new Date(stockout.estimated_stockout_date).toLocaleDateString('en-IN', { dateStyle: 'medium' })}</span>
              </div>
            )}
            <div className="font-mono text-xs text-muted-foreground bg-white/60 rounded p-2 mt-2 overflow-x-auto break-all">
              {stockout.formula}
            </div>
          </MethodologySection>

          {/* 4. Reorder Quantity */}
          <MethodologySection number={4} title="Reorder Quantity">
            <div className="font-mono text-xs text-muted-foreground bg-white/60 rounded p-2 overflow-x-auto whitespace-pre-wrap">
              {reorder.formula}
            </div>
            {reorder.supplier_name && (
              <div className="text-sm text-muted-foreground mt-2">
                Supplier: <span className="font-medium">{reorder.supplier_name}</span>
                {' '}({reorder.supplier_lead_time} day lead time)
              </div>
            )}
            {reorder.suggested_qty !== null && (
              <div className="text-sm mt-1">
                Suggested order: <span className="font-semibold">{reorder.suggested_qty} units</span>
              </div>
            )}
          </MethodologySection>

          {/* 5. Status Determination */}
          <MethodologySection number={5} title="Status Determination">
            <div className="text-xs text-muted-foreground mb-2">
              Thresholds: {reorder.status_thresholds}
            </div>
            <div className={`rounded-lg border p-3 ${statusColors[reorder.status] || statusColors.no_data}`}>
              <div className="flex items-center gap-2">
                <span className="font-medium">This SKU:</span>
                <StatusBadge status={reorder.status as ReorderStatus} />
              </div>
              <div className="text-sm mt-1">{reorder.status_reason}</div>
            </div>
          </MethodologySection>

        </div>
      </CollapsibleSection>

    </div>
  )
}
