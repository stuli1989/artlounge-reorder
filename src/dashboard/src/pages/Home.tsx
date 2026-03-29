import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchDashboardSummary } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import HelpTip from '@/components/HelpTip'
import { useIsMobile } from '@/hooks/useIsMobile'
import { MobileListRow, MobileListRowSkeleton } from '@/components/mobile/MobileListRow'
import UniversalSearch from '@/components/UniversalSearch'

export default function Home() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()

  const { data: s, isLoading, isError } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: fetchDashboardSummary,
  })

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center">
        <p className="text-muted-foreground mb-4">Failed to load dashboard data</p>
        <button onClick={() => queryClient.invalidateQueries({ queryKey: ['dashboardSummary'] })} className="text-primary hover:underline">
          Retry
        </button>
      </div>
    )
  }

  if (isLoading || !s) {
    return (
      <div className={isMobile ? 'px-4 py-4 space-y-4' : 'space-y-6'}>
        <div className="h-10 w-full bg-muted animate-pulse rounded" />
        {isMobile ? (
          <div className="flex gap-2.5 overflow-x-auto pb-2 -mx-4 px-4">
            {[1, 2, 3].map(i => <div key={i} className="min-w-[130px] flex-shrink-0 h-24 bg-muted animate-pulse rounded-lg" />)}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map(i => <div key={i} className="h-28 bg-muted animate-pulse rounded-lg" />)}
          </div>
        )}
        {isMobile ? (
          <div className="space-y-0">
            {[1, 2, 3, 4, 5].map(i => <MobileListRowSkeleton key={i} />)}
          </div>
        ) : (
          <div className="h-64 bg-muted animate-pulse rounded-lg" />
        )}
      </div>
    )
  }

  const totalCritical = s.a_urgent + s.b_urgent + s.c_urgent

  return (
    <div className={isMobile ? 'px-4 py-4 space-y-5' : 'space-y-8'}>
      {/* Section 1: Universal Search */}
      <section data-tour="brand-search">
        <UniversalSearch />
      </section>

      {/* Section 2: Action Cards */}
      <section>
        <div
          className={isMobile
            ? 'flex gap-2.5 overflow-x-auto pb-2 -mx-4 px-4'
            : 'grid grid-cols-3 gap-4'}
          data-tour="summary-cards"
        >
          {/* Urgent SKUs */}
          <Card
            className={`cursor-pointer hover:shadow-md transition-shadow bg-red-50 border-red-200 ${isMobile ? 'min-w-[130px] flex-shrink-0' : ''}`}
            onClick={() => navigate('/critical')}
          >
            <CardContent className={isMobile ? 'pt-4 pb-3 px-3' : 'pt-6'}>
              <div className={`font-bold text-red-600 ${isMobile ? 'text-2xl' : 'text-4xl'}`}>{totalCritical}</div>
              <div className={`font-medium mt-1 ${isMobile ? 'text-xs' : 'text-sm'}`}>
                Urgent SKUs
                {!isMobile && <> <HelpTip tip="SKUs with less than lead time + buffer days of stock at current sell-through rate." helpAnchor="stockout-projection" /></>}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                across {s.brands_with_urgent} brands
              </div>
            </CardContent>
          </Card>

          {/* Brands Needing POs */}
          <Card
            className={`cursor-pointer hover:shadow-md transition-shadow bg-amber-50 border-amber-200 ${isMobile ? 'min-w-[130px] flex-shrink-0' : ''}`}
            onClick={() => navigate('/brands')}
          >
            <CardContent className={isMobile ? 'pt-4 pb-3 px-3' : 'pt-6'}>
              <div className={`font-bold text-amber-600 ${isMobile ? 'text-2xl' : 'text-4xl'}`}>{s.brands_with_urgent}</div>
              <div className={`font-medium mt-1 ${isMobile ? 'text-xs' : 'text-sm'}`}>Brands Needing POs</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                have urgent SKUs
              </div>
            </CardContent>
          </Card>

          {/* Total Brands */}
          <Card className={`bg-muted/40 ${isMobile ? 'min-w-[130px] flex-shrink-0' : ''}`}>
            <CardContent className={isMobile ? 'pt-4 pb-3 px-3' : 'pt-6'}>
              <div className={`font-bold ${isMobile ? 'text-2xl' : 'text-4xl'}`}>{s.total_brands}</div>
              <div className={`font-medium mt-1 ${isMobile ? 'text-xs' : 'text-sm'}`}>Total Brands</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                in portfolio
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Section 3: Priority Brands */}
      <section data-tour="priority-table">
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Priority Brands</h3>
        {isMobile ? (
          /* Mobile: MobileListRow cards */
          <div className="border rounded-lg overflow-hidden -mx-4">
            {s.top_brands.slice(0, 10).map(brand => {
              const status = brand.urgent_skus > 0 ? 'urgent' : brand.reorder_skus > 0 ? 'reorder' : 'healthy'
              const statusLabel = brand.urgent_skus > 0
                ? `${brand.urgent_skus} urgent`
                : brand.reorder_skus > 0
                  ? `${brand.reorder_skus} reorder`
                  : 'Healthy'
              return (
                <MobileListRow
                  key={brand.category_name}
                  title={brand.category_name}
                  status={status}
                  statusLabel={statusLabel}
                  metrics={[
                    { label: 'Urgent', value: String(brand.urgent_skus || 0), color: brand.urgent_skus > 0 ? 'text-red-500' : undefined },
                    { label: 'Reorder', value: String(brand.reorder_skus || 0), color: brand.reorder_skus > 0 ? 'text-amber-500' : undefined },
                  ]}
                  onClick={() => navigate(`/brands/${encodeURIComponent(brand.category_name)}/skus`)}
                />
              )
            })}
            <div className="px-4 py-3 border-t">
              <Button variant="ghost" size="sm" onClick={() => navigate('/brands')} className="text-muted-foreground w-full justify-center">
                View all {s.total_brands} brands <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>
          </div>
        ) : (
          /* Desktop: Table */
          <Card>
            <div className="border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Brand</TableHead>
                    <TableHead className="text-right">Urgent</TableHead>
                    <TableHead className="text-right">Reorder</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {s.top_brands.slice(0, 10).map(brand => (
                    <TableRow
                      key={brand.category_name}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/brands/${encodeURIComponent(brand.category_name)}/skus`)}
                    >
                      <TableCell className="font-medium">{brand.category_name}</TableCell>
                      <TableCell className="text-right">
                        <span className={brand.urgent_skus > 0 ? 'text-red-600 font-medium' : ''}>
                          {brand.urgent_skus || '-'}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span className={brand.reorder_skus > 0 ? 'text-amber-600' : ''}>
                          {brand.reorder_skus || '-'}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="px-4 py-3 border-t">
              <Button variant="ghost" size="sm" onClick={() => navigate('/brands')} className="text-muted-foreground">
                View all {s.total_brands} brands <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>
          </Card>
        )}
      </section>
    </div>
  )
}
