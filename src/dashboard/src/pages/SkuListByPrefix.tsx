import { useState, useMemo } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSkusByPrefix } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import StatusBadge from '@/components/StatusBadge'
import { ArrowLeft, ShoppingCart, Search } from 'lucide-react'
import type { SkuMetrics } from '@/lib/types'

export default function SkuListByPrefix() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const prefix = searchParams.get('prefix') || ''
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const limit = 100

  const { data, isLoading, isError } = useQuery({
    queryKey: ['skus-by-prefix', prefix, search, page],
    queryFn: () => fetchSkusByPrefix(prefix, {
      limit,
      offset: page * limit,
      ...(search ? { search } : {}),
    }),
    enabled: prefix.length >= 2,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0

  const brandCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const item of items) {
      counts[item.category_name] = (counts[item.category_name] || 0) + 1
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1])
  }, [items])

  if (!prefix) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-8 text-center">
        <p className="text-muted-foreground mb-4">No prefix specified</p>
        <Button variant="outline" onClick={() => navigate('/brands')}>Go to Brands</Button>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="text-xl font-semibold">
              SKUs matching prefix &ldquo;{prefix}&rdquo;
            </h2>
            <p className="text-sm text-muted-foreground">{total} SKU{total !== 1 ? 's' : ''} found</p>
          </div>
        </div>
        <Button size="sm" onClick={() => navigate(`/po?prefix=${encodeURIComponent(prefix)}`)}>
          <ShoppingCart className="h-4 w-4 mr-1.5" /> Build PO
        </Button>
      </div>

      {brandCounts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {brandCounts.map(([brand, count]) => (
            <Badge key={brand} variant="secondary" className="text-xs">
              {brand} ({count})
            </Badge>
          ))}
        </div>
      )}

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search within prefix results..."
          className="pl-10"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(0) }}
        />
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Loading...</div>
      ) : isError ? (
        <div className="text-center py-12 text-destructive">Failed to load SKUs</div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">No SKUs found</div>
      ) : (
        <>
          <div className="border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[80px]">Status</TableHead>
                  <TableHead className="w-[110px]">Part No</TableHead>
                  <TableHead>SKU Name</TableHead>
                  <TableHead>Brand</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="text-right">Vel /mo</TableHead>
                  <TableHead className="text-right">Days Left</TableHead>
                  <TableHead className="w-[60px]">ABC</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item: SkuMetrics) => (
                  <TableRow
                    key={item.stock_item_name}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/brands/${encodeURIComponent(item.category_name)}/skus?highlight=${encodeURIComponent(item.stock_item_name)}`)}
                  >
                    <TableCell>
                      <StatusBadge status={item.effective_status ?? item.reorder_status} />
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {item.part_no || '—'}
                    </TableCell>
                    <TableCell className="max-w-[300px] truncate" title={item.stock_item_name}>
                      {item.stock_item_name}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {item.category_name}
                    </TableCell>
                    <TableCell className="text-right">{item.effective_stock ?? item.current_stock}</TableCell>
                    <TableCell className="text-right">
                      {((item.effective_velocity ?? item.total_velocity) * 30).toFixed(1)}
                    </TableCell>
                    <TableCell className="text-right">
                      {item.days_to_stockout === null ? 'N/A' : item.days_to_stockout === 0 ? 'OUT' : `${item.days_to_stockout}d`}
                    </TableCell>
                    <TableCell>{item.abc_class || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {total > limit && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                  Previous
                </Button>
                <Button variant="outline" size="sm" disabled={(page + 1) * limit >= total} onClick={() => setPage(p => p + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
