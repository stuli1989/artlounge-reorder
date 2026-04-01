import { useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchPrefixSearch } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ArrowLeft, ShoppingCart, ArrowRight } from 'lucide-react'

/**
 * Cross-brand prefix SKU list page.
 *
 * - Single brand: auto-redirects to that brand's full SKU detail page
 *   with the prefix as search term (reuses all existing features).
 * - Multiple brands: shows brand picker so the user chooses which brand to view.
 */
export default function SkuListByPrefix() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const prefix = searchParams.get('prefix') || ''

  const { data, isLoading } = useQuery({
    queryKey: ['prefix-search', prefix],
    queryFn: () => fetchPrefixSearch(prefix),
    enabled: prefix.length >= 2,
  })

  // Auto-redirect when single brand
  useEffect(() => {
    if (data && data.brands.length === 1) {
      navigate(
        `/brands/${encodeURIComponent(data.brands[0])}/skus?search=${encodeURIComponent(prefix)}`,
        { replace: true },
      )
    }
  }, [data, prefix, navigate])

  if (!prefix) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-8 text-center">
        <p className="text-muted-foreground mb-4">No prefix specified</p>
        <Button variant="outline" onClick={() => navigate('/brands')}>Go to Brands</Button>
      </div>
    )
  }

  // Loading or single-brand (will redirect)
  if (isLoading || !data || data.brands.length <= 1) {
    return (
      <div className="text-center py-12 text-muted-foreground">Loading...</div>
    )
  }

  // Multiple brands — show brand picker
  return (
    <div className="p-6 space-y-4 max-w-2xl mx-auto">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-xl font-semibold">
            Prefix &ldquo;{prefix}&rdquo; spans {data.brands.length} brands
          </h2>
          <p className="text-sm text-muted-foreground">{data.total} SKUs found — choose a brand to view</p>
        </div>
      </div>

      <div className="flex justify-end">
        <Button size="sm" onClick={() => navigate(`/po?prefix=${encodeURIComponent(prefix)}`)}>
          <ShoppingCart className="h-4 w-4 mr-1.5" /> Build PO (all brands)
        </Button>
      </div>

      <div className="border rounded-lg divide-y">
        {data.brands.map(brand => {
          const count = data.skus.filter(s => s.category_name === brand).length
          return (
            <button
              key={brand}
              className="w-full text-left px-4 py-3 hover:bg-muted/50 flex items-center justify-between"
              onClick={() => navigate(`/brands/${encodeURIComponent(brand)}/skus?search=${encodeURIComponent(prefix)}`)}
            >
              <div className="flex items-center gap-3">
                <span className="font-medium">{brand}</span>
                <Badge variant="secondary" className="text-xs">{count} SKUs</Badge>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </button>
          )
        })}
      </div>
    </div>
  )
}
