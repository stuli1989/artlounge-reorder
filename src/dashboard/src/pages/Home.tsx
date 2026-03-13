import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchDashboardSummary } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import ClassificationExplainer from '@/components/ClassificationExplainer'
import { TrendingUp, TrendingDown, Minus, ArrowRight } from 'lucide-react'

export default function Home() {
  const navigate = useNavigate()
  const { data: s, isLoading } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: fetchDashboardSummary,
  })

  if (isLoading || !s) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-muted animate-pulse rounded" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <div key={i} className="h-28 bg-muted animate-pulse rounded-lg" />)}
        </div>
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-muted animate-pulse rounded-lg" />)}
        </div>
      </div>
    )
  }

  const actionCards = [
    {
      title: 'A-Class Critical',
      count: s.a_critical,
      color: 'text-red-600',
      bg: 'bg-red-50 border-red-200',
      description: 'Top revenue drivers running out.',
      link: '/critical?abc_class=A&status=critical',
    },
    {
      title: 'All Warnings',
      count: s.total_warning,
      color: 'text-amber-600',
      bg: 'bg-amber-50 border-amber-200',
      description: 'Items approaching reorder threshold.',
      link: '/critical?status=warning',
    },
    {
      title: 'Brands Needing POs',
      count: s.brands_with_critical,
      color: 'text-blue-600',
      bg: 'bg-blue-50 border-blue-200',
      description: 'Brands with critical SKUs.',
      link: '/brands',
    },
  ]

  const totalStatusItems = s.total_critical + s.total_warning + s.total_ok + s.total_out_of_stock || 1
  const statusSegments = [
    { label: 'Critical', count: s.total_critical, color: 'bg-red-500', pct: (s.total_critical / totalStatusItems) * 100 },
    { label: 'Warning', count: s.total_warning, color: 'bg-amber-400', pct: (s.total_warning / totalStatusItems) * 100 },
    { label: 'OK', count: s.total_ok, color: 'bg-green-500', pct: (s.total_ok / totalStatusItems) * 100 },
    { label: 'Out of Stock', count: s.total_out_of_stock, color: 'bg-gray-400', pct: (s.total_out_of_stock / totalStatusItems) * 100 },
  ]

  const totalAbc = s.total_a_class_skus + s.total_b_class_skus + s.total_c_class_skus || 1
  const abcSegments = [
    { label: 'A', count: s.total_a_class_skus, color: 'bg-red-500', pct: (s.total_a_class_skus / totalAbc) * 100, rev: '80% rev' },
    { label: 'B', count: s.total_b_class_skus, color: 'bg-amber-400', pct: (s.total_b_class_skus / totalAbc) * 100, rev: '15% rev' },
    { label: 'C', count: s.total_c_class_skus, color: 'bg-gray-400', pct: (s.total_c_class_skus / totalAbc) * 100, rev: '5% rev' },
  ]

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Command Center</h2>
          <p className="text-sm text-muted-foreground mt-0.5">{s.total_active_skus.toLocaleString()} active SKUs across {s.total_brands} brands</p>
        </div>
        <ClassificationExplainer />
      </div>

      {/* Section 1 — Needs Action */}
      <section>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Needs Action</h3>
        <div className="grid grid-cols-3 gap-4">
          {actionCards.map(card => (
            <Card
              key={card.title}
              className={`cursor-pointer hover:shadow-md transition-shadow border ${card.bg}`}
              onClick={() => navigate(card.link)}
            >
              <CardHeader className="pb-1">
                <CardTitle className="text-sm font-medium">{card.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className={`text-3xl font-bold ${card.color}`}>{card.count}</div>
                <p className="text-xs text-muted-foreground mt-1">{card.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          A-class = items generating the top 80% of revenue. Prioritize these for reordering.
        </p>
      </section>

      {/* Section 2 — Portfolio Health */}
      <section>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Portfolio Health</h3>
        <div className="grid grid-cols-2 gap-4">
          {/* Stock Status Bar */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Stock Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex h-4 rounded-full overflow-hidden mb-2">
                {statusSegments.map(seg => (
                  seg.pct > 0 && <div key={seg.label} className={`${seg.color}`} style={{ width: `${seg.pct}%` }} />
                ))}
              </div>
              <div className="flex gap-3 text-xs text-muted-foreground flex-wrap">
                {statusSegments.map(seg => (
                  <span key={seg.label} className="flex items-center gap-1">
                    <span className={`w-2 h-2 rounded-full ${seg.color}`} />
                    {seg.label}: {seg.count.toLocaleString()}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Revenue Distribution */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Revenue Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex h-4 rounded-full overflow-hidden mb-2">
                {abcSegments.map(seg => (
                  seg.pct > 0 && <div key={seg.label} className={`${seg.color}`} style={{ width: `${seg.pct}%` }} />
                ))}
              </div>
              <div className="flex gap-3 text-xs text-muted-foreground">
                {abcSegments.map(seg => (
                  <span key={seg.label}>
                    {seg.label}: {seg.count.toLocaleString()} ({seg.rev})
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Demand Trends */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Demand Trends</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-6">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-green-600" />
                  <span className="text-lg font-semibold">{s.trending_up}</span>
                  <span className="text-xs text-muted-foreground">rising</span>
                </div>
                <div className="flex items-center gap-2">
                  <Minus className="h-4 w-4 text-gray-400" />
                  <span className="text-lg font-semibold">{s.trending_flat}</span>
                  <span className="text-xs text-muted-foreground">flat</span>
                </div>
                <div className="flex items-center gap-2">
                  <TrendingDown className="h-4 w-4 text-red-600" />
                  <span className="text-lg font-semibold">{s.trending_down}</span>
                  <span className="text-xs text-muted-foreground">falling</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Inventory Quality */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Inventory Quality</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-6">
                <div>
                  <div className="text-lg font-semibold text-blue-600">{s.total_dead_stock_skus.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Dead stock</div>
                </div>
                <div>
                  <div className="text-lg font-semibold text-amber-600">{s.total_slow_mover_skus.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Slow movers</div>
                </div>
                <div>
                  <div className="text-lg font-semibold text-gray-500">{s.total_inactive_skus.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Inactive</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Section 3 — Top Priority Brands */}
      <section>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Top Priority Brands</h3>
        <Card>
          <div className="border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Brand</TableHead>
                  <TableHead className="text-right">Critical (A)</TableHead>
                  <TableHead className="text-right">Critical (B+C)</TableHead>
                  <TableHead className="text-right">Warning</TableHead>
                  <TableHead className="text-right">Avg Days</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {s.top_brands.map(brand => {
                  const aCritical = brand.a_critical_skus
                  const bcCritical = brand.critical_skus - aCritical
                  return (
                    <TableRow
                      key={brand.category_name}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/brands/${encodeURIComponent(brand.category_name)}/skus`)}
                    >
                      <TableCell className="font-medium">{brand.category_name}</TableCell>
                      <TableCell className="text-right text-red-600 font-medium">{aCritical || '-'}</TableCell>
                      <TableCell className="text-right">{bcCritical || '-'}</TableCell>
                      <TableCell className="text-right text-amber-600">{brand.warning_skus || '-'}</TableCell>
                      <TableCell className="text-right">
                        {brand.avg_days_to_stockout !== null ? `${brand.avg_days_to_stockout}d` : 'N/A'}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          <div className="px-4 py-3 border-t">
            <Button variant="ghost" size="sm" onClick={() => navigate('/brands')} className="text-muted-foreground">
              View all {s.total_brands} brands <ArrowRight className="h-3.5 w-3.5 ml-1" />
            </Button>
          </div>
        </Card>
      </section>
    </div>
  )
}
