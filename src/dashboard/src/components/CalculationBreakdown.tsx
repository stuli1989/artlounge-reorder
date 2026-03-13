import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchBreakdown, createOverride, deleteOverride } from '@/lib/api'
import type { BreakdownResponse, BreakdownTransactionRow, OverrideInfo } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { CheckCircle2, XCircle, ArrowRight, Info, Pencil, AlertTriangle, X } from 'lucide-react'

// Toggle to show/hide the assumptions summary strip in Stockout & Reorder
const SHOW_ASSUMPTIONS_STRIP = true

const confidenceColors = {
  high: 'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-red-100 text-red-700',
}

const statusColors: Record<string, string> = {
  ok: 'bg-green-100 text-green-700 border-green-200',
  warning: 'bg-amber-100 text-amber-700 border-amber-200',
  critical: 'bg-red-100 text-red-700 border-red-200',
  out_of_stock: 'bg-red-50 text-red-600 border-red-200',
  no_data: 'bg-gray-100 text-gray-500 border-gray-200',
}

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

function DemandIcon({ included }: { included: boolean }) {
  return included
    ? <CheckCircle2 className="h-4 w-4 text-green-600 inline" />
    : <XCircle className="h-4 w-4 text-gray-400 inline" />
}

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
}: {
  fieldName: string
  label: string
  currentOverride?: OverrideInfo
  stockItemName: string
}) {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState(currentOverride?.value?.toString() || '')
  const [reason, setReason] = useState('')
  const [holdFromPo, setHoldFromPo] = useState(false)
  const queryClient = useQueryClient()

  const createMut = useMutation({
    mutationFn: createOverride,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['breakdown'] })
      queryClient.invalidateQueries({ queryKey: ['skus'] })
      queryClient.invalidateQueries({ queryKey: ['poData'] })
      queryClient.invalidateQueries({ queryKey: ['overrides'] })
      setOpen(false)
    },
  })

  const removeMut = useMutation({
    mutationFn: () => deleteOverride(currentOverride!.id, 'Removed by user'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['breakdown'] })
      queryClient.invalidateQueries({ queryKey: ['skus'] })
      queryClient.invalidateQueries({ queryKey: ['poData'] })
      queryClient.invalidateQueries({ queryKey: ['overrides'] })
      setOpen(false)
    },
  })

  if (!open) {
    return (
      <div className="flex items-center gap-2">
        {currentOverride && <OverrideBadge ovr={currentOverride} />}
        <Button variant="outline" size="sm" onClick={() => {
          setValue(currentOverride?.value?.toString() || '')
          setReason('')
          setOpen(true)
        }}>
          <Pencil className="h-3 w-3 mr-1" />
          {currentOverride ? 'Edit' : `Adjust ${label}`}
        </Button>
        {currentOverride && (
          <Button variant="ghost" size="sm" className="text-red-600" onClick={() => removeMut.mutate()}>
            <X className="h-3 w-3 mr-1" /> Remove
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="border rounded-lg p-3 bg-muted/30 space-y-2">
      <div className="text-sm font-medium">Override {label}</div>
      {fieldName !== 'note' && (
        <Input
          type="number"
          step="any"
          placeholder="Value"
          value={value}
          onChange={e => setValue(e.target.value)}
          className="w-40"
        />
      )}
      <textarea
        placeholder="Reason (required)"
        value={reason}
        onChange={e => setReason(e.target.value)}
        className="w-full border rounded p-2 text-sm min-h-[60px] resize-y"
      />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={holdFromPo} onChange={e => setHoldFromPo(e.target.checked)} />
        Hold from PO suggestions
      </label>
      <div className="flex gap-2">
        <Button
          size="sm"
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
        <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
      {createMut.isError && (
        <div className="text-sm text-red-600">Failed to save override</div>
      )}
    </div>
  )
}

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

  const { data_source, position_reconstruction, transaction_summary, date_range, velocity, stockout, reorder, effective_values } = data
  const overrides = data_source.overrides || {}

  const stockOvr = overrides.current_stock

  return (
    <div className="space-y-4">
      {/* Section 1: Data Source */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Data Source</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div>
            <span className="text-muted-foreground">Current stock: </span>
            <span className="font-medium">{data_source.closing_balance_from_tally ?? 'N/A'} units</span>
            <span className="text-muted-foreground"> (from Tally closing balance)</span>
          </div>
          {stockOvr && (
            <div className="flex items-start gap-1.5 text-xs bg-blue-50 border border-blue-200 rounded p-2">
              <Pencil className="h-3.5 w-3.5 mt-0.5 shrink-0 text-blue-600" />
              <span>Stock overridden to <strong>{stockOvr.value}</strong> units. Reason: {stockOvr.note}</span>
            </div>
          )}
          {data_source.data_as_of && (
            <div>
              <span className="text-muted-foreground">Data as of: </span>
              <span className="font-medium">{new Date(data_source.data_as_of).toLocaleDateString('en-IN', { dateStyle: 'medium' })}</span>
            </div>
          )}
          {data_source.last_computed && (
            <div>
              <span className="text-muted-foreground">Last computed: </span>
              <span className="font-medium">{new Date(data_source.last_computed).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</span>
            </div>
          )}
          <div>
            <span className="text-muted-foreground">Financial year: </span>
            <span className="font-medium">{data_source.fy_period}</span>
          </div>
          <OverrideForm
            fieldName="current_stock"
            label="Stock"
            currentOverride={stockOvr}
            stockItemName={stockItemName}

          />
        </CardContent>
      </Card>

      {/* Section 2: Position Reconstruction */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Stock Position Reconstruction</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <FlowBox label="Implied Opening" value={String(position_reconstruction.implied_opening)} className="bg-blue-50 border-blue-200" />
            <FlowArrow />
            <FlowBox label="+ Inward" value={String(position_reconstruction.total_inward)} className="bg-green-50 border-green-200" />
            <FlowArrow />
            <FlowBox label="- Outward" value={String(position_reconstruction.total_outward)} className="bg-red-50 border-red-200" />
            <FlowArrow />
            <FlowBox label="= Closing" value={String(position_reconstruction.closing_balance ?? 'N/A')} className="bg-purple-50 border-purple-200" />
          </div>
          <div className="font-mono text-xs text-muted-foreground bg-muted/50 rounded p-2">
            {position_reconstruction.formula}
          </div>
          <div className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            Positions are reconstructed backwards from Tally's closing balance (authoritative source)
          </div>
        </CardContent>
      </Card>

      {/* Section 3: Transaction Breakdown */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Transaction Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          {transaction_summary.length === 0 ? (
            <div className="text-sm text-muted-foreground py-4 text-center">No transactions in this period</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Channel</TableHead>
                  <TableHead>Direction</TableHead>
                  <TableHead className="text-right">Transactions</TableHead>
                  <TableHead className="text-right">Total Qty</TableHead>
                  <TableHead>Demand?</TableHead>
                  <TableHead>Why</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transaction_summary.map((t: BreakdownTransactionRow) => (
                  <TableRow key={`${t.channel}-${t.direction}`}>
                    <TableCell className="capitalize font-medium">{t.channel}</TableCell>
                    <TableCell className="capitalize text-muted-foreground">{t.direction}</TableCell>
                    <TableCell className="text-right">{t.count}</TableCell>
                    <TableCell className="text-right font-medium">{t.total_qty}</TableCell>
                    <TableCell><DemandIcon included={t.included_in_demand} /></TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[200px]">{t.explanation}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Section 4: Velocity Calculation */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            Velocity Calculation
            <Badge variant="outline" className={confidenceColors[velocity.confidence]}>
              {velocity.confidence} confidence
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <InStockBar data={data} />

          <div className="flex flex-wrap gap-4 text-sm">
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
            <div className="flex items-start gap-1.5 text-xs text-muted-foreground bg-amber-50 border border-amber-200 rounded p-2">
              <Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-600" />
              {velocity.out_of_stock_exclusion_reason}
            </div>
          )}

          <div className="text-sm font-medium">Velocity by channel (active days only)</div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Channel</TableHead>
                <TableHead className="text-right">Units Sold</TableHead>
                <TableHead className="text-right">/ Active Days</TableHead>
                <TableHead className="text-right">= Daily Rate</TableHead>
                <TableHead className="text-right">x30 = Monthly</TableHead>
                <TableHead className="w-8"></TableHead>
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
                      {ovr && <OverrideBadge ovr={ovr} />}
                    </TableCell>
                    <TableCell className="text-right">{c.total_units}</TableCell>
                    <TableCell className="text-right text-muted-foreground">/ {velocity.in_stock_days}</TableCell>
                    <TableCell className="text-right">{c.daily_velocity}</TableCell>
                    <TableCell className="text-right font-semibold">{c.monthly_velocity}</TableCell>
                    <TableCell>
                      <OverrideForm
                        fieldName={fieldName}
                        label={`${ch} velocity`}
                        currentOverride={ovr}
                        stockItemName={stockItemName}
            
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
              <TableRow className="border-t-2 font-semibold">
                <TableCell>
                  Total
                  {overrides.total_velocity && <OverrideBadge ovr={overrides.total_velocity} />}
                </TableCell>
                <TableCell className="text-right">{velocity.total.total_units}</TableCell>
                <TableCell className="text-right text-muted-foreground">/ {velocity.in_stock_days}</TableCell>
                <TableCell className="text-right">{velocity.total.daily_velocity}</TableCell>
                <TableCell className="text-right">{velocity.total.monthly_velocity}</TableCell>
                <TableCell>
                  <OverrideForm
                    fieldName="total_velocity"
                    label="total velocity"
                    currentOverride={overrides.total_velocity}
                    stockItemName={stockItemName}
        
                  />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>

          <div className="font-mono text-xs text-muted-foreground bg-muted/50 rounded p-2">
            {velocity.formula}
          </div>
          <div className="text-xs text-muted-foreground">{velocity.confidence_reason}</div>
        </CardContent>
      </Card>

      {/* Section 5: Stockout & Reorder (uses effective values) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Stockout & Reorder</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Assumptions strip */}
          {SHOW_ASSUMPTIONS_STRIP && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground bg-muted/30 rounded px-3 py-2 border">
              <span>Lead time: <strong className="text-foreground">{reorder.supplier_lead_time}d</strong></span>
              <span>Buffer: <strong className="text-foreground">{reorder.buffer_multiplier}x</strong></span>
              <span>Analysis window: <strong className="text-foreground">{date_range.from_date} — {date_range.to_date} ({date_range.total_days_in_range}d)</strong></span>
              {data_source.data_as_of && (
                <span>Data as of: <strong className="text-foreground">{new Date(data_source.data_as_of).toLocaleDateString('en-IN', { dateStyle: 'medium' })}</strong></span>
              )}
            </div>
          )}

          {/* Override callout */}
          {(effective_values.stock_source === 'override' || effective_values.velocity_source === 'override') && (
            <div className="flex items-start gap-1.5 text-xs bg-blue-50 border border-blue-200 rounded p-2">
              <Pencil className="h-3.5 w-3.5 mt-0.5 shrink-0 text-blue-600" />
              <span>
                {effective_values.stock_source === 'override' &&
                  `Using overridden stock (${effective_values.current_stock}) instead of computed (${data_source.closing_balance_from_tally}). `}
                {effective_values.velocity_source === 'override' &&
                  `Using overridden velocity (${effective_values.total_velocity}/day) instead of computed (${velocity.total.daily_velocity}/day).`}
              </span>
            </div>
          )}

          {/* Stockout projection */}
          <div className="space-y-2">
            <div className="text-sm font-medium">Stockout projection</div>
            <div className="flex items-center gap-2 flex-wrap">
              <FlowBox
                label={effective_values.stock_source === 'override' ? 'Stock (override)' : 'Stock'}
                value={`${stockout.current_stock}`}
                className={effective_values.stock_source === 'override' ? 'bg-blue-100 border-blue-300' : 'bg-blue-50 border-blue-200'}
              />
              <FlowArrow />
              <FlowBox
                label={effective_values.velocity_source === 'override' ? '/ Burn rate (override)' : '/ Burn rate'}
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
              <div className="text-sm text-muted-foreground">
                Estimated stockout: <span className="font-medium">{new Date(stockout.estimated_stockout_date).toLocaleDateString('en-IN', { dateStyle: 'medium' })}</span>
              </div>
            )}
            <div className="font-mono text-xs text-muted-foreground bg-muted/50 rounded p-2">
              {stockout.formula}
            </div>
          </div>

          {/* Reorder calculation */}
          <div className="space-y-2 pt-2 border-t">
            <div className="text-sm font-medium">Reorder calculation</div>
            <div className="font-mono text-xs text-muted-foreground bg-muted/50 rounded p-2">
              {reorder.formula}
            </div>
            {reorder.supplier_name && (
              <div className="text-sm text-muted-foreground">
                Supplier: <span className="font-medium">{reorder.supplier_name}</span>
                {' '}({reorder.supplier_lead_time} day lead time)
              </div>
            )}
            {reorder.suggested_qty !== null && (
              <div className="text-sm">
                Suggested order: <span className="font-semibold">{reorder.suggested_qty} units</span>
              </div>
            )}
          </div>

          {/* Note override */}
          <div className="pt-2 border-t">
            <OverrideForm
              fieldName="note"
              label="Note"
              currentOverride={overrides.note}
              stockItemName={stockItemName}
  
            />
          </div>

          {/* Status */}
          <div className={`rounded-lg border p-3 ${statusColors[reorder.status] || statusColors.no_data}`}>
            <div className="font-medium capitalize">{reorder.status.replace('_', ' ')}</div>
            <div className="text-sm mt-1">{reorder.status_reason}</div>
            <div className="text-xs mt-1 opacity-75">Thresholds: {reorder.status_thresholds}</div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
