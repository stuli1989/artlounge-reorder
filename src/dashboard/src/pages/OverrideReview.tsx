import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchOverrides, reviewOverride } from '@/lib/api'
import type { Override } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { AlertTriangle, CheckCircle2, Trash2 } from 'lucide-react'
import { useIsMobile } from '@/hooks/useIsMobile'
import { MobileListRow, MobileListRowSkeleton } from '@/components/mobile/MobileListRow'

const fieldLabels: Record<string, string> = {
  current_stock: 'Stock',
  total_velocity: 'Total Velocity',
  wholesale_velocity: 'Wholesale Vel.',
  online_velocity: 'Online Vel.',
  store_velocity: 'Store Vel.',
  note: 'Note',
}

export default function OverrideReview() {
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()
  const [staleOnly, setStaleOnly] = useState(false)

  const { data: overrides, isLoading } = useQuery({
    queryKey: ['overrides', staleOnly],
    queryFn: () => fetchOverrides(staleOnly ? { is_stale: true } : {}),
  })

  const reviewMut = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'keep' | 'remove' }) =>
      action === 'keep'
        ? reviewOverride(id, { action: 'keep', reason: 'Reviewed and kept' })
        : reviewOverride(id, { action: 'remove', reason: 'Removed during review' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['overrides'] })
      queryClient.invalidateQueries({ queryKey: ['skus'] })
      queryClient.invalidateQueries({ queryKey: ['breakdown'] })
      queryClient.invalidateQueries({ queryKey: ['poData'] })
    },
  })

  const staleCount = overrides?.filter(o => o.is_stale).length ?? 0
  const totalActive = overrides?.length ?? 0

  if (isMobile) {
    return (
      <div className="px-4 py-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Overrides</h2>
          <div className="flex items-center gap-2">
            <Switch id="stale-toggle-m" checked={staleOnly} onCheckedChange={setStaleOnly} />
            <Label htmlFor="stale-toggle-m" className="text-xs">Stale only</Label>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="flex gap-2">
          <Card className="flex-1">
            <CardContent className="pt-3 pb-2 px-3">
              <div className="text-lg font-bold">{totalActive}</div>
              <div className="text-[10px] text-muted-foreground">Active</div>
            </CardContent>
          </Card>
          <Card className="flex-1">
            <CardContent className="pt-3 pb-2 px-3">
              <div className={`text-lg font-bold ${staleCount > 0 ? 'text-amber-600' : 'text-green-600'}`}>
                {staleCount}
              </div>
              <div className="text-[10px] text-muted-foreground">Stale</div>
            </CardContent>
          </Card>
        </div>

        {/* Override list */}
        {isLoading ? (
          <div className="space-y-0 -mx-4">
            {Array.from({ length: 4 }).map((_, i) => <MobileListRowSkeleton key={i} />)}
          </div>
        ) : !overrides?.length ? (
          <div className="text-center py-8 text-muted-foreground">
            {staleOnly ? 'No stale overrides' : 'No active overrides'}
          </div>
        ) : (
          <div className="-mx-4">
            {overrides.map((o: Override) => {
              const ageStr = o.created_at
                ? new Date(o.created_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })
                : '-'
              return (
                <MobileListRow
                  key={o.id}
                  title={o.stock_item_name}
                  subtitle={`${fieldLabels[o.field_name] || o.field_name}: ${o.override_value !== null ? o.override_value : '-'}`}
                  status={o.is_stale ? 'warning' : 'ok'}
                  statusLabel={o.is_stale ? 'Stale' : 'Active'}
                  metrics={[
                    { label: 'Age', value: ageStr },
                    ...(o.drift_pct !== null ? [{ label: 'Drift', value: `${o.drift_pct.toFixed(0)}%`, color: o.drift_pct > 20 ? 'text-amber-600' : undefined }] : []),
                  ]}
                >
                  <div className="flex gap-2 mt-2">
                    {o.is_stale && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 text-xs"
                        disabled={reviewMut.isPending}
                        onClick={() => reviewMut.mutate({ id: o.id, action: 'keep' })}
                      >
                        <CheckCircle2 className="h-3 w-3 mr-1" /> Keep
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 text-xs text-red-600"
                      disabled={reviewMut.isPending}
                      onClick={() => reviewMut.mutate({ id: o.id, action: 'remove' })}
                    >
                      <Trash2 className="h-3 w-3 mr-1" /> Remove
                    </Button>
                  </div>
                </MobileListRow>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Override Review</h2>
        <div className="flex items-center gap-2">
          <Switch id="stale-toggle" checked={staleOnly} onCheckedChange={setStaleOnly} />
          <Label htmlFor="stale-toggle" className="text-sm">Stale only</Label>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 max-w-md">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Active Overrides</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalActive}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Stale (Need Review)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${staleCount > 0 ? 'text-amber-600' : 'text-green-600'}`}>
              {staleCount}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Loading overrides...</div>
      ) : !overrides?.length ? (
        <div className="text-center py-12 text-muted-foreground">
          {staleOnly ? 'No stale overrides' : 'No active overrides'}
        </div>
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Field</TableHead>
                <TableHead className="text-right">Override Value</TableHead>
                <TableHead className="text-right">Computed (at creation)</TableHead>
                <TableHead className="text-right">Computed (now)</TableHead>
                <TableHead className="text-right">Drift</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {overrides.map((o: Override) => (
                <TableRow key={o.id} className={o.is_stale ? 'bg-amber-50' : ''}>
                  <TableCell className="max-w-[200px] truncate" title={o.stock_item_name}>
                    {o.stock_item_name}
                  </TableCell>
                  <TableCell>{fieldLabels[o.field_name] || o.field_name}</TableCell>
                  <TableCell className="text-right font-medium">
                    {o.override_value !== null ? o.override_value : '-'}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {o.computed_value_at_creation !== null ? o.computed_value_at_creation : '-'}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {o.computed_value_latest !== null ? o.computed_value_latest : '-'}
                  </TableCell>
                  <TableCell className="text-right">
                    {o.drift_pct !== null ? (
                      <span className={o.drift_pct > 20 ? 'text-amber-600 font-medium' : ''}>
                        {o.drift_pct.toFixed(0)}%
                      </span>
                    ) : '-'}
                  </TableCell>
                  <TableCell className="max-w-[150px] truncate text-xs" title={o.note}>
                    {o.note}
                  </TableCell>
                  <TableCell className="text-xs whitespace-nowrap">
                    {o.created_at ? new Date(o.created_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }) : '-'}
                  </TableCell>
                  <TableCell>
                    {o.is_stale ? (
                      <Badge variant="outline" className="bg-amber-100 text-amber-700 border-amber-200 gap-1">
                        <AlertTriangle className="h-3 w-3" /> Stale
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="bg-green-100 text-green-700 border-green-200 gap-1">
                        <CheckCircle2 className="h-3 w-3" /> Active
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {o.is_stale && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={reviewMut.isPending}
                          onClick={() => reviewMut.mutate({ id: o.id, action: 'keep' })}
                        >
                          Keep
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600"
                        disabled={reviewMut.isPending}
                        onClick={() => reviewMut.mutate({ id: o.id, action: 'remove' })}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
