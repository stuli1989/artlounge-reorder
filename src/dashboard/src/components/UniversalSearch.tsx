import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSearch } from '@/lib/api'
import type { SearchBrandResult, SearchSkuResult } from '@/lib/types'
import { Input } from '@/components/ui/input'
import { Search, Loader2, Package, Tag } from 'lucide-react'
import { useIsMobile } from '@/hooks/useIsMobile'
import { BottomSheet } from '@/components/mobile/BottomSheet'
import StatusBadge from '@/components/StatusBadge'

interface Props {
  scope?: string
  placeholder?: string
}

export default function UniversalSearch({ scope, placeholder }: Props) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [highlightIdx, setHighlightIdx] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const isMobile = useIsMobile()

  // Debounce
  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQuery(query.trim()), 300)
    return () => window.clearTimeout(t)
  }, [query])

  // Fetch
  const { data, isLoading, isError } = useQuery({
    queryKey: ['universal-search', debouncedQuery, scope],
    queryFn: () => fetchSearch(debouncedQuery, scope),
    enabled: debouncedQuery.length >= 2,
    staleTime: 30_000,
  })

  // Build flat list for keyboard nav
  const items: Array<{ type: 'brand' | 'scoped_sku' | 'sku'; item: SearchBrandResult | SearchSkuResult }> = []
  if (data) {
    data.brands.forEach(b => items.push({ type: 'brand', item: b }))
    data.scoped_skus?.forEach(s => items.push({ type: 'scoped_sku', item: s }))
    data.skus.forEach(s => items.push({ type: 'sku', item: s }))
  }

  // Reset highlight when results change
  useEffect(() => { setHighlightIdx(-1) }, [data])

  // Click outside (desktop)
  useEffect(() => {
    if (isMobile) return
    function handle(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [isMobile])

  const navigateTo = useCallback((type: string, item: SearchBrandResult | SearchSkuResult) => {
    setOpen(false)
    setQuery('')
    setDebouncedQuery('')
    if (type === 'brand') {
      const b = item as SearchBrandResult
      navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)
    } else {
      const s = item as SearchSkuResult
      navigate(
        `/brands/${encodeURIComponent(s.category_name)}/skus?highlight=${encodeURIComponent(s.stock_item_name)}`
      )
    }
  }, [navigate])

  // Keyboard nav (desktop only)
  const onKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (isMobile) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightIdx(i => Math.min(i + 1, items.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightIdx(i => Math.max(i - 1, -1))
    } else if (e.key === 'Enter' && highlightIdx >= 0 && highlightIdx < items.length) {
      e.preventDefault()
      const { type, item } = items[highlightIdx]
      navigateTo(type, item)
    } else if (e.key === 'Escape') {
      setOpen(false)
      setQuery('')
    }
  }, [isMobile, highlightIdx, items, navigateTo])

  const showResults = debouncedQuery.length >= 2 && open

  // ── Shared results renderer ──
  const renderResults = () => {
    if (isLoading) {
      return (
        <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Searching...
        </div>
      )
    }
    if (isError) {
      return <div className="px-4 py-3 text-sm text-destructive">Search failed — try again</div>
    }
    if (!data || (data.brands.length === 0 && data.skus.length === 0 && (!data.scoped_skus || data.scoped_skus.length === 0))) {
      return (
        <div className="px-4 py-3 text-sm text-muted-foreground">
          No brands or SKUs match &lsquo;{debouncedQuery}&rsquo;
        </div>
      )
    }

    let flatIdx = -1
    return (
      <>
        {/* Brands */}
        {data.brands.length > 0 && (
          <>
            <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/50">
              Brands {data.brand_count > data.brands.length && `(${data.brand_count} total)`}
            </div>
            {data.brands.map(b => {
              flatIdx++
              const idx = flatIdx
              return (
                <button
                  key={`b-${b.category_name}`}
                  className={`w-full text-left px-4 py-2.5 text-sm cursor-pointer flex items-center justify-between gap-2
                    ${isMobile ? 'active:bg-muted/50 min-h-[44px]' : 'hover:bg-muted'}
                    ${!isMobile && highlightIdx === idx ? 'bg-muted' : ''}`}
                  onClick={() => navigateTo('brand', b)}
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <Package className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="truncate font-medium">{b.category_name}</span>
                  </span>
                  <span className="flex items-center gap-2 shrink-0 text-xs text-muted-foreground">
                    <span>{b.total_skus} SKUs</span>
                    {b.critical_skus > 0 && (
                      <span className="text-red-500 font-medium">{b.critical_skus} critical</span>
                    )}
                  </span>
                </button>
              )
            })}
          </>
        )}
        {/* Scoped SKUs */}
        {data.scoped_skus && data.scoped_skus.length > 0 && (
          <>
            <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/50">
              SKUs in {scope} {data.scoped_sku_count! > data.scoped_skus.length && `(${data.scoped_sku_count} total)`}
            </div>
            {data.scoped_skus.map(s => {
              flatIdx++
              const idx = flatIdx
              return (
                <button
                  key={`ss-${s.stock_item_name}`}
                  className={`w-full text-left px-4 py-2.5 text-sm cursor-pointer flex items-center justify-between gap-2
                    ${isMobile ? 'active:bg-muted/50 min-h-[44px]' : 'hover:bg-muted'}
                    ${!isMobile && highlightIdx === idx ? 'bg-muted' : ''}`}
                  onClick={() => navigateTo('scoped_sku', s)}
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <Tag className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <span className="truncate">{s.stock_item_name}</span>
                    {s.part_no && <span className="text-xs text-muted-foreground shrink-0">({s.part_no})</span>}
                  </span>
                  <StatusBadge status={s.reorder_status} />
                </button>
              )
            })}
          </>
        )}
        {/* Global SKUs */}
        {data.skus.length > 0 && (
          <>
            <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/50">
              {scope ? 'Other SKUs' : 'SKUs'} {data.sku_count > data.skus.length && `(${data.sku_count} total)`}
            </div>
            {data.skus.map(s => {
              flatIdx++
              const idx = flatIdx
              return (
                <button
                  key={`s-${s.stock_item_name}-${s.category_name}`}
                  className={`w-full text-left px-4 py-2.5 text-sm cursor-pointer flex items-center justify-between gap-2
                    ${isMobile ? 'active:bg-muted/50 min-h-[44px]' : 'hover:bg-muted'}
                    ${!isMobile && highlightIdx === idx ? 'bg-muted' : ''}`}
                  onClick={() => navigateTo('sku', s)}
                >
                  <span className="flex items-center gap-2 min-w-0">
                    <Tag className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <span className="truncate">{s.stock_item_name}</span>
                    {s.part_no && <span className="text-xs text-muted-foreground shrink-0">({s.part_no})</span>}
                  </span>
                  <span className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-muted-foreground">{s.category_name}</span>
                    <StatusBadge status={s.reorder_status} />
                  </span>
                </button>
              )
            })}
          </>
        )}
      </>
    )
  }

  // ── Desktop: inline dropdown ──
  if (!isMobile) {
    return (
      <div ref={containerRef} className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          ref={inputRef}
          placeholder={placeholder ?? 'Search brands, SKUs, part numbers...'}
          className="pl-10 h-11 text-base"
          value={query}
          onChange={e => {
            setQuery(e.target.value)
            setOpen(e.target.value.trim().length >= 2)
          }}
          onFocus={() => {
            if (query.trim().length >= 2) setOpen(true)
          }}
          onKeyDown={onKeyDown}
        />
        {showResults && (
          <div className="absolute z-50 top-full mt-1 w-full bg-popover border rounded-md shadow-lg max-h-[420px] overflow-y-auto">
            {renderResults()}
          </div>
        )}
      </div>
    )
  }

  // ── Mobile: input + BottomSheet ──
  return (
    <>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={placeholder ?? 'Search brands, SKUs...'}
          className="pl-10 h-10"
          value={query}
          onChange={e => {
            setQuery(e.target.value)
            if (e.target.value.trim().length >= 2) setOpen(true)
          }}
          onFocus={() => {
            if (query.trim().length >= 2) setOpen(true)
          }}
          readOnly={false}
        />
      </div>
      <BottomSheet
        open={showResults}
        onOpenChange={setOpen}
        title="Search Results"
      >
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={placeholder ?? 'Search brands, SKUs...'}
            className="pl-10 h-10"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
        </div>
        <div className="-mx-4">{renderResults()}</div>
      </BottomSheet>
    </>
  )
}
