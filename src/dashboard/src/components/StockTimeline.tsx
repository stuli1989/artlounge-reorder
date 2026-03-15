import { useState, useMemo, useCallback, memo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea, CartesianGrid } from 'recharts'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { fetchPositions, fetchTransactions } from '@/lib/api'
import type { Transaction } from '@/lib/types'
import { X } from 'lucide-react'
import { useIsMobile } from '@/hooks/useIsMobile'

interface Props {
  categoryName: string
  stockItemName: string
}

const channelColors: Record<string, string> = {
  wholesale: 'bg-blue-100 text-blue-700',
  online: 'bg-purple-100 text-purple-700',
  store: 'bg-green-100 text-green-700',
  supplier: 'bg-orange-100 text-orange-700',
  internal: 'bg-gray-100 text-gray-500',
  ignore: 'bg-gray-50 text-gray-400',
}

const fmtDate = (v: string) =>
  new Date(v).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })

const fmtDateFull = (v: string) =>
  new Date(v).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })

export default memo(function StockTimeline({ categoryName, stockItemName }: Props) {
  const isMobile = useIsMobile()
  const [selStart, setSelStart] = useState<string | null>(null)
  const [selEnd, setSelEnd] = useState<string | null>(null)
  const [dragging, setDragging] = useState<string | null>(null)
  const [datePreset, setDatePreset] = useState<'7d' | '30d' | '90d' | 'all'>('all')

  const { data: positions, isLoading: posLoading } = useQuery({
    queryKey: ['positions', categoryName, stockItemName],
    queryFn: () => fetchPositions(categoryName, stockItemName),
  })

  const { data: transactions, isLoading: txnLoading } = useQuery({
    queryKey: ['transactions', categoryName, stockItemName],
    queryFn: () => fetchTransactions(categoryName, stockItemName, 500),
  })

  // Merge position data with in/out for the chart
  const chartData = useMemo(() => {
    if (!positions?.length) return []
    let filtered = positions
    if (isMobile && datePreset !== 'all') {
      const now = new Date()
      const daysMap = { '7d': 7, '30d': 30, '90d': 90 } as const
      const days = daysMap[datePreset as keyof typeof daysMap]
      if (days) {
        const cutoff = new Date(now)
        cutoff.setDate(cutoff.getDate() - days)
        const cutoffStr = cutoff.toISOString().slice(0, 10)
        filtered = positions.filter(p => p.position_date >= cutoffStr)
      }
    }
    return filtered.map(p => ({
      ...p,
      date: p.position_date,
    }))
  }, [positions, isMobile, datePreset])

  // Filter transactions by selected date range
  const filteredTxns = useMemo(() => {
    if (!transactions?.length) return []
    if (!selStart || !selEnd) return transactions
    const from = selStart <= selEnd ? selStart : selEnd
    const to = selStart <= selEnd ? selEnd : selStart
    return transactions.filter(t => t.txn_date >= from && t.txn_date <= to)
  }, [transactions, selStart, selEnd])

  const handleMouseDown = useCallback((e: { activeLabel?: string }) => {
    if (e?.activeLabel) {
      setDragging(e.activeLabel)
      setSelStart(e.activeLabel)
      setSelEnd(null)
    }
  }, [])

  const handleMouseMove = useCallback((e: { activeLabel?: string }) => {
    if (dragging && e?.activeLabel) {
      setSelEnd(e.activeLabel)
    }
  }, [dragging])

  const handleMouseUp = useCallback(() => {
    if (dragging) {
      setDragging(null)
      // If only clicked (no drag), clear selection
      if (!selEnd || selEnd === selStart) {
        setSelStart(null)
        setSelEnd(null)
      }
    }
  }, [dragging, selEnd, selStart])

  const clearSelection = useCallback(() => {
    setSelStart(null)
    setSelEnd(null)
    setDragging(null)
  }, [])

  const hasSelection = selStart !== null && selEnd !== null && selEnd !== selStart
  const selFrom = hasSelection ? (selStart! <= selEnd! ? selStart! : selEnd!) : null
  const selTo = hasSelection ? (selStart! <= selEnd! ? selEnd! : selStart!) : null

  const isLoading = posLoading || txnLoading

  if (isLoading) return <div className="h-[300px] flex items-center justify-center text-muted-foreground">Loading timeline...</div>
  if (!chartData.length) return <div className="h-[200px] flex items-center justify-center text-muted-foreground">No position data</div>

  return (
    <div className="space-y-4">
      {/* Chart */}
      <div>
        {!isMobile && (
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-muted-foreground">
              {hasSelection
                ? <>Showing <strong className="text-foreground">{fmtDateFull(selFrom!)}</strong> — <strong className="text-foreground">{fmtDateFull(selTo!)}</strong> · {filteredTxns.length} transactions</>
                : 'Drag on chart to filter transactions by date range'}
            </p>
            {hasSelection && (
              <Button variant="ghost" size="sm" className="h-6 px-2 text-xs gap-1" onClick={clearSelection}>
                <X className="h-3 w-3" /> Clear
              </Button>
            )}
          </div>
        )}
        <ResponsiveContainer width="100%" height={isMobile ? 180 : 200} style={{ userSelect: 'none' }}>
          <AreaChart
            data={chartData}
            margin={{ top: 5, right: 10, bottom: 5, left: 0 }}
            {...(!isMobile ? {
              onMouseDown: handleMouseDown as any,
              onMouseMove: handleMouseMove as any,
              onMouseUp: handleMouseUp,
              onMouseLeave: handleMouseUp,
            } : {})}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="position_date"
              tickFormatter={fmtDate}
              fontSize={11}
              tick={{ fill: '#888' }}
              interval="preserveStartEnd"
            />
            <YAxis fontSize={11} tick={{ fill: '#888' }} />
            <Tooltip
              labelFormatter={(v) => fmtDateFull(String(v))}
              formatter={(value, name) => {
                const labels: Record<string, string> = {
                  closing_qty: 'Stock',
                  inward_qty: 'In',
                  outward_qty: 'Out',
                }
                return [value, labels[String(name)] || String(name)]
              }}
            />
            <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="3 3" />
            {!isMobile && hasSelection && (
              <ReferenceArea
                x1={selFrom!}
                x2={selTo!}
                fill="#3b82f6"
                fillOpacity={0.1}
                stroke="#3b82f6"
                strokeOpacity={0.3}
              />
            )}
            {!isMobile && dragging && selEnd && (
              <ReferenceArea
                x1={dragging}
                x2={selEnd}
                fill="#3b82f6"
                fillOpacity={0.15}
              />
            )}
            <Area
              type="monotone"
              dataKey="closing_qty"
              stroke="#3b82f6"
              fill="#93c5fd"
              fillOpacity={0.3}
            />
          </AreaChart>
        </ResponsiveContainer>
        {/* Date preset buttons for mobile */}
        {isMobile && (
          <div className="flex gap-2 mt-2">
            {(['7d', '30d', '90d', 'all'] as const).map(preset => (
              <button
                key={preset}
                onClick={() => setDatePreset(preset)}
                className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  datePreset === preset
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {preset === 'all' ? 'All' : preset.toUpperCase()}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Transactions table */}
      <div className="border rounded-lg overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[90px]">Date</TableHead>
              <TableHead>Party</TableHead>
              {!isMobile && <TableHead>Type</TableHead>}
              {!isMobile && <TableHead className="w-[80px]">Voucher #</TableHead>}
              <TableHead className="w-[70px] text-right">Qty In</TableHead>
              <TableHead className="w-[70px] text-right">Qty Out</TableHead>
              <TableHead className="w-[80px]">Channel</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTxns.length === 0 ? (
              <TableRow>
                <TableCell colSpan={isMobile ? 5 : 7} className="text-center py-6 text-muted-foreground">
                  {hasSelection ? 'No transactions in selected period' : 'No transactions found'}
                </TableCell>
              </TableRow>
            ) : (
              filteredTxns.map((t: Transaction, i: number) => (
                <TableRow key={`${t.txn_date}-${t.voucher_number}-${i}`}>
                  <TableCell className="text-xs">{fmtDate(t.txn_date)}</TableCell>
                  <TableCell className="text-xs max-w-[200px] truncate">{t.party_name}</TableCell>
                  {!isMobile && <TableCell className="text-xs">{t.voucher_type}</TableCell>}
                  {!isMobile && <TableCell className="text-xs">{t.voucher_number}</TableCell>}
                  <TableCell className="text-xs text-right text-green-600">{t.is_inward ? t.quantity : ''}</TableCell>
                  <TableCell className="text-xs text-right text-red-600">{!t.is_inward ? t.quantity : ''}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`text-xs ${channelColors[t.channel] || ''}`}>
                      {t.channel}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
})
