import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchBrands, fetchBrandSummary } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Search, ArrowUpDown } from 'lucide-react'

export default function BrandOverview() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [criticalOnly, setCriticalOnly] = useState(false)
  const [sortCol, setSortCol] = useState<string>('critical_skus')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const { data: summary } = useQuery({
    queryKey: ['brandSummary'],
    queryFn: fetchBrandSummary,
  })

  const { data: brands, isLoading } = useQuery({
    queryKey: ['brands', search],
    queryFn: () => fetchBrands(search || undefined),
  })

  const filteredBrands = useMemo(() =>
    (brands || [])
      .filter(b => !criticalOnly || b.critical_skus > 0 || b.warning_skus > 0)
      .sort((a, b) => {
        const aVal = ((a as unknown as Record<string, unknown>)[sortCol] as number) ?? -Infinity
        const bVal = ((b as unknown as Record<string, unknown>)[sortCol] as number) ?? -Infinity
        return sortDir === 'desc' ? bVal - aVal : aVal - bVal
      }),
    [brands, criticalOnly, sortCol, sortDir]
  )

  const toggleSort = (col: string) => {
    if (sortCol === col) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    } else {
      setSortCol(col)
      setSortDir('desc')
    }
  }

  const daysColor = (days: number | null) => {
    if (days === null) return 'text-gray-400'
    if (days < 30) return 'text-red-600 font-medium'
    if (days < 90) return 'text-amber-600'
    return 'text-green-600'
  }

  const summaryCards = [
    { label: 'Total Brands', value: summary?.total_brands, color: '' },
    { label: 'Brands with Critical', value: summary?.brands_with_critical, color: 'text-red-600' },
    { label: 'Brands with Warning', value: summary?.brands_with_warning, color: 'text-amber-600' },
    { label: 'SKUs Out of Stock', value: summary?.total_skus_out_of_stock, color: 'text-red-600' },
    { label: 'Dead Stock SKUs', value: summary?.total_dead_stock_skus, color: 'text-blue-600' },
    { label: 'Slow Mover SKUs', value: summary?.total_slow_mover_skus, color: 'text-amber-600' },
  ]

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-6 gap-4">
        {summaryCards.map(c => (
          <Card key={c.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{c.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${c.color}`}>{c.value ?? '...'}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search brands..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="critical-only"
            checked={criticalOnly}
            onCheckedChange={(v) => setCriticalOnly(!!v)}
          />
          <Label htmlFor="critical-only" className="text-sm">Show critical/warning only</Label>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Loading brands...</div>
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Brand</TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('total_skus')}>
                  <span className="flex items-center gap-1">Total <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead>In Stock</TableHead>
                <TableHead>Out of Stock</TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('critical_skus')}>
                  <span className="flex items-center gap-1">Critical <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('warning_skus')}>
                  <span className="flex items-center gap-1">Warning <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead>OK</TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('dead_stock_skus')}>
                  <span className="flex items-center gap-1">Dead <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('slow_mover_skus')}>
                  <span className="flex items-center gap-1">Slow <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('avg_days_to_stockout')}>
                  <span className="flex items-center gap-1">Avg Days Left <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredBrands.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={11} className="text-center py-8 text-muted-foreground">
                    No brands found
                  </TableCell>
                </TableRow>
              ) : (
                filteredBrands.map(b => (
                  <TableRow key={b.category_name} className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)}>
                    <TableCell className="font-medium">{b.category_name}</TableCell>
                    <TableCell>{b.total_skus}</TableCell>
                    <TableCell className="text-green-600">{b.in_stock_skus}</TableCell>
                    <TableCell className={b.out_of_stock_skus > 0 ? 'text-red-600' : ''}>{b.out_of_stock_skus}</TableCell>
                    <TableCell>
                      {b.critical_skus > 0 ? (
                        <Badge className="bg-red-100 text-red-700 hover:bg-red-100">{b.critical_skus}</Badge>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {b.warning_skus > 0 ? (
                        <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">{b.warning_skus}</Badge>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </TableCell>
                    <TableCell>{b.ok_skus}</TableCell>
                    <TableCell>
                      {b.dead_stock_skus > 0
                        ? <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100">{b.dead_stock_skus}</Badge>
                        : <span className="text-muted-foreground">0</span>}
                    </TableCell>
                    <TableCell>
                      {(b.slow_mover_skus || 0) > 0
                        ? <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">{b.slow_mover_skus}</Badge>
                        : <span className="text-muted-foreground">0</span>}
                    </TableCell>
                    <TableCell className={daysColor(b.avg_days_to_stockout)}>
                      {b.avg_days_to_stockout !== null ? `${b.avg_days_to_stockout} days` : 'N/A'}
                    </TableCell>
                    <TableCell onClick={e => e.stopPropagation()}>
                      <div className="flex gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)}
                        >
                          SKUs
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/po`)}
                        >
                          PO
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/dead-stock`)}
                        >
                          Review
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
