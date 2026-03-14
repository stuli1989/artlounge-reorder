import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useState, useRef, useEffect } from 'react'
import { fetchDashboardSummary, fetchBrands } from '@/lib/api'
// types inferred from API functions
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Search, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import HelpTip from '@/components/HelpTip'

export default function Home() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)

  const { data: s, isLoading } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: fetchDashboardSummary,
  })

  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: () => fetchBrands(),
  })

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const filteredBrands = (brands ?? []).filter(b =>
    b.category_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (isLoading || !s) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-full bg-muted animate-pulse rounded" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <div key={i} className="h-28 bg-muted animate-pulse rounded-lg" />)}
        </div>
        <div className="h-64 bg-muted animate-pulse rounded-lg" />
      </div>
    )
  }

  const totalCritical = s.a_critical + s.b_critical + s.c_critical

  return (
    <div className="space-y-8">
      {/* Section 1: Brand Search */}
      <section>
        <div ref={searchRef} className="relative" data-tour="brand-search">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Jump to brand... (type to search)"
            className="pl-10 h-11 text-base"
            value={searchQuery}
            onChange={e => {
              setSearchQuery(e.target.value)
              setShowDropdown(e.target.value.length > 0)
            }}
            onFocus={() => {
              if (searchQuery.length > 0) setShowDropdown(true)
            }}
          />
          {showDropdown && searchQuery.length > 0 && (
            <div className="absolute z-50 top-full mt-1 w-full bg-popover border rounded-md shadow-lg max-h-64 overflow-y-auto">
              {filteredBrands.length === 0 ? (
                <div className="px-4 py-3 text-sm text-muted-foreground">No brands found</div>
              ) : (
                filteredBrands.slice(0, 20).map(b => (
                  <button
                    key={b.category_name}
                    className="w-full text-left px-4 py-2 text-sm hover:bg-muted cursor-pointer flex items-center justify-between"
                    onClick={() => {
                      navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)
                      setShowDropdown(false)
                      setSearchQuery('')
                    }}
                  >
                    <span>{b.category_name}</span>
                    <span className="text-xs text-muted-foreground">{b.total_skus} SKUs</span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </section>

      {/* Section 2: Action Cards */}
      <section>
        <div className="grid grid-cols-3 gap-4" data-tour="summary-cards">
          {/* Critical SKUs */}
          <Card
            className="cursor-pointer hover:shadow-md transition-shadow bg-red-50 border-red-200"
            onClick={() => navigate('/critical')}
          >
            <CardContent className="pt-6">
              <div className="text-4xl font-bold text-red-600">{totalCritical}</div>
              <div className="text-sm font-medium mt-1">Critical SKUs <HelpTip tip="SKUs with less than lead time + buffer days of stock at current sell-through rate." helpAnchor="stockout-projection" /></div>
              <div className="text-xs text-muted-foreground mt-0.5">
                across {s.brands_with_critical} brands
              </div>
            </CardContent>
          </Card>

          {/* Brands Needing POs */}
          <Card
            className="cursor-pointer hover:shadow-md transition-shadow bg-amber-50 border-amber-200"
            onClick={() => navigate('/brands')}
          >
            <CardContent className="pt-6">
              <div className="text-4xl font-bold text-amber-600">{s.brands_with_critical}</div>
              <div className="text-sm font-medium mt-1">Brands Needing POs</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                have critical SKUs
              </div>
            </CardContent>
          </Card>

          {/* Total Brands */}
          <Card className="bg-muted/40">
            <CardContent className="pt-6">
              <div className="text-4xl font-bold">{s.total_brands}</div>
              <div className="text-sm font-medium mt-1">Total Brands</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                in portfolio
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Section 3: Priority Brands Table */}
      <section data-tour="priority-table">
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Priority Brands</h3>
        <Card>
          <div className="border rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Brand</TableHead>
                  <TableHead className="text-right">Critical</TableHead>
                  <TableHead className="text-right">Warning</TableHead>
                  <TableHead className="text-right">Out of Stock</TableHead>
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
                      <span className={brand.critical_skus > 0 ? 'text-red-600 font-medium' : ''}>
                        {brand.critical_skus || '-'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <span className={brand.warning_skus > 0 ? 'text-amber-600' : ''}>
                        {brand.warning_skus || '-'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">&mdash;</TableCell>
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
      </section>
    </div>
  )
}
