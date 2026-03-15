import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchBrands, fetchBrandSummary, fetchSkusPage } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import AbcBadge from '@/components/AbcBadge'
import ClassificationExplainer from '@/components/ClassificationExplainer'
import { Search, ArrowUpDown, LayoutGrid, TableProperties } from 'lucide-react'
import { daysColor } from '@/lib/formatters'
import HelpTip from '@/components/HelpTip'
import { useIsMobile } from '@/hooks/useIsMobile'
import { FilterButton, FilterChips, FilterDrawer } from '@/components/mobile/FilterDrawer'
import type { FilterChip } from '@/components/mobile/FilterDrawer'
import type { SortOption } from '@/components/mobile/MobileSortSheet'

const BRAND_SORT_OPTIONS: SortOption[] = [
  { value: 'critical_skus', label: 'Critical SKUs' },
  { value: 'total_skus', label: 'Total SKUs' },
  { value: 'dead_stock_skus', label: 'Dead Stock' },
  { value: 'avg_days_to_stockout', label: 'Avg Days to Stockout' },
  { value: 'a_class_skus', label: 'A-Class SKUs' },
]

export default function BrandOverview() {
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [criticalOnly, setCriticalOnly] = useState(false)
  const [sortCol, setSortCol] = useState<string>('critical_skus')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [viewMode, setViewMode] = useState<'compact' | 'detailed'>('compact')
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handleBrandHover = useCallback((categoryName: string) => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
    hoverTimer.current = setTimeout(() => {
      queryClient.prefetchQuery({
        queryKey: ['skus', categoryName, 'all', '', undefined, undefined, 0, 100],
        queryFn: () => fetchSkusPage(categoryName, {}, { limit: 100, offset: 0 }),
        staleTime: 5 * 60 * 1000,
      })
    }, 200)
  }, [queryClient])

  useEffect(() => {
    return () => {
      if (hoverTimer.current) clearTimeout(hoverTimer.current)
    }
  }, [])

  const { data: summary } = useQuery({
    queryKey: ['brandSummary'],
    queryFn: fetchBrandSummary,
  })

  const { data: brands, isLoading, isError, refetch } = useQuery({
    queryKey: ['brands', debouncedSearch],
    queryFn: () => fetchBrands(debouncedSearch || undefined),
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

  const summaryCards = [
    { label: 'Total Brands', value: summary?.total_brands, color: '' },
    { label: 'Brands with Critical', value: summary?.brands_with_critical, color: 'text-red-600' },
    { label: 'Brands with Warning', value: summary?.brands_with_warning, color: 'text-amber-600' },
    { label: 'SKUs Out of Stock', value: summary?.total_skus_out_of_stock, color: 'text-red-600' },
    { label: 'Dead Stock SKUs', value: summary?.total_dead_stock_skus, color: 'text-blue-600' },
    { label: 'Slow Mover SKUs', value: summary?.total_slow_mover_skus, color: 'text-amber-600' },
  ]

  // Mobile filter chips
  const mobileFilterChips: FilterChip[] = []
  if (criticalOnly) mobileFilterChips.push({ key: 'critical', label: 'Critical/Warning only', onRemove: () => setCriticalOnly(false) })
  const mobileFilterCount = mobileFilterChips.length + (sortCol !== 'critical_skus' ? 1 : 0)

  if (isError) return <div className="p-8 text-center text-muted-foreground">Failed to load brands. <button onClick={() => refetch()} className="text-primary hover:underline">Retry</button></div>

  if (isMobile) {
    return (
      <div className="px-4 py-4 space-y-4">
        {/* Summary Cards — horizontal scroll */}
        <div className="flex gap-2 overflow-x-auto pb-2 -mx-4 px-4" data-tour="brand-cards">
          {summaryCards.map(c => (
            <Card key={c.label} className="min-w-[110px] flex-shrink-0">
              <CardContent className="pt-3 pb-2 px-3">
                <div className={`text-lg font-bold ${c.color}`}>{c.value ?? '...'}</div>
                <div className="text-[10px] text-muted-foreground leading-tight mt-0.5">{c.label}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Search + Filter button */}
        <div className="flex items-center gap-2" data-tour="brand-filters">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search brands..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 h-10"
            />
          </div>
          <FilterButton activeCount={mobileFilterCount} onClick={() => setFilterDrawerOpen(true)} />
        </div>

        {/* Filter chips */}
        <FilterChips chips={mobileFilterChips} />

        {/* Brand cards — always card view on mobile */}
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-28 bg-muted animate-pulse rounded-lg" />
            ))}
          </div>
        ) : filteredBrands.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">No brands found</div>
        ) : (
          <div className="space-y-3 -mx-4">
            {filteredBrands.map(b => {
              const worstStatus = b.critical_skus > 0 ? 'critical' : b.warning_skus > 0 ? 'warning' : 'ok'
              const borderColor = worstStatus === 'critical' ? 'border-l-red-500' : worstStatus === 'warning' ? 'border-l-amber-500' : 'border-l-green-500'
              const healthPct = b.total_skus > 0 ? Math.round((b.ok_skus / b.total_skus) * 100) : 0
              const healthColor = healthPct >= 70 ? 'text-green-600' : healthPct >= 40 ? 'text-amber-600' : 'text-red-600'
              return (
                <div
                  key={b.category_name}
                  className={`border-l-[3px] ${borderColor} px-4 py-3 border-b border-border/50 active:bg-muted/50 transition-colors cursor-pointer`}
                  onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <span className="font-semibold text-sm">{b.category_name}</span>
                      <div className="text-xs text-muted-foreground">{b.total_skus.toLocaleString()} SKUs</div>
                    </div>
                    <span className={`text-xs font-medium ${healthColor}`}>Health: {healthPct}%</span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div>
                      <div className="text-sm font-bold text-red-600">{b.critical_skus}</div>
                      <div className="text-[10px] text-muted-foreground">Crit</div>
                    </div>
                    <div>
                      <div className="text-sm font-bold text-amber-600">{b.warning_skus}</div>
                      <div className="text-[10px] text-muted-foreground">Warn</div>
                    </div>
                    <div>
                      <div className="text-sm font-bold text-green-600">{b.ok_skus}</div>
                      <div className="text-[10px] text-muted-foreground">OK</div>
                    </div>
                    <div>
                      <div className="text-sm font-bold text-blue-600">{b.dead_stock_skus}</div>
                      <div className="text-[10px] text-muted-foreground">Dead</div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Filter Drawer */}
        <FilterDrawer open={filterDrawerOpen} onOpenChange={setFilterDrawerOpen}>
          <div className="space-y-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <Checkbox
                checked={criticalOnly}
                onCheckedChange={(v) => setCriticalOnly(!!v)}
              />
              <span className="text-sm">Show critical/warning only</span>
            </label>
            <div>
              <div className="text-sm font-medium mb-2">Sort by</div>
              {BRAND_SORT_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => {
                    if (sortCol === opt.value) {
                      setSortDir(d => d === 'desc' ? 'asc' : 'desc')
                    } else {
                      setSortCol(opt.value)
                      setSortDir('desc')
                    }
                  }}
                  className={`w-full text-left px-3 py-2 rounded text-sm ${sortCol === opt.value ? 'bg-primary/10 text-primary font-medium' : 'text-foreground'}`}
                >
                  {opt.label} {sortCol === opt.value && (sortDir === 'desc' ? '\u2193' : '\u2191')}
                </button>
              ))}
            </div>
          </div>
        </FilterDrawer>

      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4" data-tour="brand-cards">
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
      <div className="flex items-center gap-4" data-tour="brand-filters">
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
        <div className="ml-auto flex items-center gap-2">
          <ClassificationExplainer />
          <div className="inline-flex rounded-md border bg-muted p-0.5">
            <button
              className={`p-1.5 rounded-sm transition-colors ${viewMode === 'compact' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
              onClick={() => setViewMode('compact')}
              title="Table view"
            >
              <TableProperties className="h-4 w-4" />
            </button>
            <button
              className={`p-1.5 rounded-sm transition-colors ${viewMode === 'detailed' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
              onClick={() => setViewMode('detailed')}
              title="Card view"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                {Array.from({ length: 6 }).map((_, i) => (
                  <TableHead key={i}><div className="h-4 w-full bg-muted animate-pulse rounded" /></TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from({ length: 8 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <TableCell key={j}><div className="h-4 w-full bg-muted animate-pulse rounded" /></TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : viewMode === 'compact' ? (
        /* Compact Table View — 6 columns */
        <div className="border rounded-lg" data-tour="brand-table">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Brand</TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('critical_skus')}>
                  <span className="flex items-center gap-1">Health <HelpTip tip="Combined health indicator: count of critical, warning, and ok SKUs for this brand." helpAnchor="stockout-projection" /> <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('a_class_skus')}>
                  <span className="flex items-center gap-1">ABC Split <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('dead_stock_skus')}>
                  <span className="flex items-center gap-1">Dead / Slow <HelpTip tip="Dead stock (zero sales beyond threshold) and slow movers (very low velocity)." helpAnchor="page-dead-stock" /> <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead className="cursor-pointer" onClick={() => toggleSort('avg_days_to_stockout')}>
                  <span className="flex items-center gap-1">Avg Days <ArrowUpDown className="h-3 w-3" /></span>
                </TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredBrands.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    No brands found
                  </TableCell>
                </TableRow>
              ) : (
                filteredBrands.map(b => (
                  <TableRow key={b.category_name} className="cursor-pointer hover:bg-muted/50"
                    tabIndex={0}
                    onMouseEnter={() => handleBrandHover(b.category_name)}
                    onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`) } }}>
                    <TableCell className="font-medium">{b.category_name}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 flex-wrap">
                        {b.critical_skus > 0 && (
                          <Badge className="bg-red-100 text-red-700 hover:bg-red-100 text-xs">{b.critical_skus} crit</Badge>
                        )}
                        {b.warning_skus > 0 && (
                          <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100 text-xs">{b.warning_skus} warn</Badge>
                        )}
                        {b.ok_skus > 0 && (
                          <span className="text-xs text-green-600">{b.ok_skus} ok</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        {(b.a_class_skus || 0) > 0 && (
                          <span className="inline-flex items-center gap-0.5 text-xs">
                            <AbcBadge value="A" /> {b.a_class_skus}
                          </span>
                        )}
                        {(b.b_class_skus || 0) > 0 && (
                          <span className="inline-flex items-center gap-0.5 text-xs">
                            <AbcBadge value="B" /> {b.b_class_skus}
                          </span>
                        )}
                        {(b.c_class_skus || 0) > 0 && (
                          <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                            <AbcBadge value="C" /> {b.c_class_skus}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 text-xs">
                        {b.dead_stock_skus > 0 ? (
                          <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100">{b.dead_stock_skus}</Badge>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                        <span className="text-muted-foreground">/</span>
                        {(b.slow_mover_skus || 0) > 0 ? (
                          <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">{b.slow_mover_skus}</Badge>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className={daysColor(b.avg_days_to_stockout)}>
                      {b.avg_days_to_stockout !== null ? `${b.avg_days_to_stockout}d` : 'N/A'}
                    </TableCell>
                    <TableCell onClick={e => e.stopPropagation()}>
                      <div className="flex gap-1">
                        <Button variant="outline" size="sm"
                          onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)}>
                          SKUs
                        </Button>
                        <Button variant="outline" size="sm"
                          onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/po`)}>
                          PO
                        </Button>
                        <Button variant="outline" size="sm"
                          onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/dead-stock`)}>
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
      ) : (
        /* Detailed Card Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredBrands.length === 0 ? (
            <div className="col-span-3 text-center py-8 text-muted-foreground">No brands found</div>
          ) : (
            filteredBrands.map(b => (
              <Card key={b.category_name} className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)}
                onMouseEnter={() => handleBrandHover(b.category_name)}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-semibold">{b.category_name}</CardTitle>
                    <span className={`text-xs font-medium ${daysColor(b.avg_days_to_stockout)}`}>
                      {b.avg_days_to_stockout !== null ? `${b.avg_days_to_stockout}d avg` : 'N/A'}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Status */}
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Status</div>
                    <div className="flex gap-2 flex-wrap text-xs">
                      {b.critical_skus > 0 && <Badge className="bg-red-100 text-red-700 hover:bg-red-100">{b.critical_skus} critical</Badge>}
                      {b.warning_skus > 0 && <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">{b.warning_skus} warning</Badge>}
                      <span className="text-green-600">{b.ok_skus} ok</span>
                      {b.out_of_stock_skus > 0 && <span className="text-red-500">{b.out_of_stock_skus} OOS</span>}
                    </div>
                  </div>
                  {/* Classification */}
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Classification</div>
                    <div className="flex gap-2 text-xs">
                      <span className="inline-flex items-center gap-0.5"><AbcBadge value="A" /> {b.a_class_skus || 0}</span>
                      <span className="inline-flex items-center gap-0.5"><AbcBadge value="B" /> {b.b_class_skus || 0}</span>
                      <span className="inline-flex items-center gap-0.5"><AbcBadge value="C" /> {b.c_class_skus || 0}</span>
                    </div>
                  </div>
                  {/* Quality */}
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Inventory Quality</div>
                    <div className="flex gap-3 text-xs">
                      <span>{b.dead_stock_skus} dead</span>
                      <span>{b.slow_mover_skus || 0} slow</span>
                      <span>{b.total_skus} total</span>
                    </div>
                  </div>
                  {/* Actions */}
                  <div className="flex gap-1 pt-1" onClick={e => e.stopPropagation()}>
                    <Button variant="outline" size="sm" className="flex-1"
                      onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)}>
                      SKUs
                    </Button>
                    <Button variant="outline" size="sm" className="flex-1"
                      onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/po`)}>
                      PO
                    </Button>
                    <Button variant="outline" size="sm" className="flex-1"
                      onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/dead-stock`)}>
                      Review
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  )
}
