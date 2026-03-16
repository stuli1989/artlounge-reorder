# Universal Search Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all distributed search inputs with a single universal search component + backend endpoint.

**Architecture:** New `/api/search` endpoint queries `brand_metrics` and `sku_metrics JOIN stock_items` with ILIKE, returns grouped/ranked results. New `<UniversalSearch />` React component with desktop dropdown and mobile BottomSheet replaces search on 5 pages.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/shadcn-ui (frontend), PostgreSQL ILIKE queries

**Spec:** `docs/superpowers/specs/2026-03-16-universal-search-design.md`

---

## File Structure

### Backend (new)
- `src/api/routes/search.py` — Search endpoint with ranked ILIKE queries
- `src/tests/test_search.py` — API endpoint tests

### Frontend (new)
- `src/dashboard/src/components/UniversalSearch.tsx` — Universal search component (desktop + mobile)

### Frontend (modify)
- `src/dashboard/src/lib/api.ts` — Add `fetchSearch()` function
- `src/dashboard/src/lib/types.ts` — Add `SearchResults` type
- `src/dashboard/src/pages/Home.tsx` — Replace brand search with `<UniversalSearch />`
- `src/dashboard/src/pages/BrandOverview.tsx` — Replace brand filter with `<UniversalSearch />`
- `src/dashboard/src/pages/SkuDetail.tsx` — Replace item search with `<UniversalSearch scope={brand} />`
- `src/dashboard/src/pages/CriticalSkus.tsx` — Replace search with `<UniversalSearch />`
- `src/dashboard/src/pages/DeadStock.tsx` — Replace search with `<UniversalSearch scope={brand} />`

### Backend (modify)
- `src/api/main.py` — Register search router

---

## Chunk 1: Backend — Search Endpoint

### Task 1: Create search route with tests

**Files:**
- Create: `src/api/routes/search.py`
- Create: `src/tests/test_search.py`
- Modify: `src/api/main.py:60-72`

- [ ] **Step 1: Write the test file**

Create `src/tests/test_search.py`:

```python
"""Tests for /api/search endpoint — uses live database.

Run: cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_search.py -v
Requires: local PostgreSQL with artlounge_reorder database populated.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.auth import get_current_user

# Override auth for all tests
app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "test", "role": "viewer"}
client = TestClient(app)


class TestSearchValidation:
    def test_missing_q_returns_400(self):
        resp = client.get("/api/search")
        assert resp.status_code == 400

    def test_short_q_returns_400(self):
        resp = client.get("/api/search?q=a")
        assert resp.status_code == 400

    def test_whitespace_only_returns_400(self):
        resp = client.get("/api/search?q=%20%20")
        assert resp.status_code == 400

    def test_too_long_q_returns_400(self):
        resp = client.get(f"/api/search?q={'x' * 101}")
        assert resp.status_code == 400


class TestSearchResults:
    def test_basic_search_returns_brands_and_skus(self):
        resp = client.get("/api/search?q=winsor")
        assert resp.status_code == 200
        data = resp.json()
        assert "brands" in data
        assert "skus" in data
        assert "brand_count" in data
        assert "sku_count" in data
        # WINSOR & NEWTON is a known brand in the DB
        brand_names = [b["category_name"] for b in data["brands"]]
        assert any("WINSOR" in n.upper() for n in brand_names)

    def test_scoped_search_returns_scoped_skus(self):
        resp = client.get("/api/search?q=blue&scope=WINSOR%20%26%20NEWTON")
        assert resp.status_code == 200
        data = resp.json()
        assert "scoped_skus" in data
        assert "scoped_sku_count" in data
        # All scoped results should be from the scoped brand
        for s in data["scoped_skus"]:
            assert s["category_name"] == "WINSOR & NEWTON"

    def test_no_scope_omits_scoped_fields(self):
        resp = client.get("/api/search?q=blue")
        assert resp.status_code == 200
        data = resp.json()
        assert "scoped_skus" not in data
        assert "scoped_sku_count" not in data

    def test_sku_results_include_part_no(self):
        resp = client.get("/api/search?q=winsor")
        assert resp.status_code == 200
        data = resp.json()
        for s in data["skus"]:
            assert "part_no" in s
            assert "stock_item_name" in s
            assert "category_name" in s
            assert "reorder_status" in s
            assert "current_stock" in s

    def test_brand_results_limited_to_5(self):
        # Search for something broad
        resp = client.get("/api/search?q=ar")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["brands"]) <= 5

    def test_sku_results_limited_to_10(self):
        resp = client.get("/api/search?q=blue")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["skus"]) <= 10


class TestSearchEscaping:
    def test_special_chars_dont_break_query(self):
        """Searching for '100%' should not break SQL."""
        resp = client.get("/api/search?q=100%25")
        assert resp.status_code == 200

    def test_underscore_escaped(self):
        resp = client.get("/api/search?q=test_item")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.routes.search'`

- [ ] **Step 3: Create the search route**

Create `src/api/routes/search.py`:

```python
"""Universal search endpoint — searches brands and SKUs in one call.

IMPORTANT: sku_metrics does NOT have part_no or is_active columns.
These live on stock_items, so all SKU queries JOIN stock_items si ON si.tally_name = sm.stock_item_name.
This matches the pattern in skus.py list_skus().
"""
from decimal import Decimal
from fastapi import APIRouter, Query, HTTPException, Depends
from api.database import get_db
from api.auth import get_current_user

router = APIRouter()


def _escape_ilike(s: str) -> str:
    """Escape PostgreSQL ILIKE special characters."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _rank_expr(field: str) -> str:
    """SQL CASE expression for ranking: exact=0, starts-with=1, contains=2."""
    return (
        f"CASE WHEN LOWER({field}) = LOWER(%(q)s) THEN 0 "
        f"WHEN LOWER({field}) LIKE LOWER(%(q_prefix)s) THEN 1 "
        f"ELSE 2 END"
    )


def _to_float(val):
    """Convert Decimal to float for JSON serialization consistency."""
    if isinstance(val, Decimal):
        return float(val)
    return val


def _clean_row(row):
    """Convert a RealDictRow to a plain dict with floats instead of Decimals."""
    return {k: _to_float(v) for k, v in dict(row).items()}


# Common SQL fragments for SKU search (JOIN stock_items for part_no and is_active)
_SKU_SELECT = (
    "SELECT sm.stock_item_name, si.part_no, sm.category_name, "
    "  sm.reorder_status, sm.current_stock "
    "FROM sku_metrics sm "
    "LEFT JOIN stock_items si ON si.tally_name = sm.stock_item_name"
)

_SKU_MATCH = (
    "(sm.stock_item_name ILIKE %(pattern)s OR COALESCE(si.part_no, '') ILIKE %(pattern)s)"
)

_SKU_ACTIVE = "COALESCE(si.is_active, TRUE) = TRUE"


@router.get("/search")
def universal_search(
    q: str = Query(None),
    scope: str = Query(None),
    user: dict = Depends(get_current_user),
):
    # --- Validate ---
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "Query must be at least 2 characters")
    q = q.strip()
    if len(q) > 100:
        raise HTTPException(400, "Query must be at most 100 characters")

    escaped = _escape_ilike(q)
    pattern = f"%{escaped}%"
    prefix_pattern = f"{escaped}%"

    with get_db() as conn:
        with conn.cursor() as cur:
            params = {"q": q, "q_prefix": prefix_pattern, "pattern": pattern}

            # --- Brands ---
            brand_rank = _rank_expr("category_name")
            cur.execute(
                f"SELECT category_name, total_skus, critical_skus "
                f"FROM brand_metrics "
                f"WHERE category_name ILIKE %(pattern)s "
                f"ORDER BY {brand_rank}, category_name "
                f"LIMIT 5",
                params,
            )
            brands = [_clean_row(r) for r in cur.fetchall()]
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM brand_metrics "
                "WHERE category_name ILIKE %(pattern)s",
                params,
            )
            brand_count = cur.fetchone()["cnt"]

            # --- Scoped SKUs (if scope provided) ---
            scoped_skus = []
            scoped_sku_count = 0
            global_limit = 10
            if scope:
                sku_rank = _rank_expr("sm.stock_item_name")
                cur.execute(
                    f"{_SKU_SELECT} "
                    f"WHERE sm.category_name = %(scope)s "
                    f"  AND {_SKU_MATCH} "
                    f"  AND {_SKU_ACTIVE} "
                    f"ORDER BY {sku_rank}, sm.stock_item_name "
                    f"LIMIT 10",
                    {**params, "scope": scope},
                )
                scoped_skus = [_clean_row(r) for r in cur.fetchall()]
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sku_metrics sm "
                    f"LEFT JOIN stock_items si ON si.tally_name = sm.stock_item_name "
                    f"WHERE sm.category_name = %(scope)s "
                    f"  AND {_SKU_MATCH} "
                    f"  AND {_SKU_ACTIVE}",
                    {**params, "scope": scope},
                )
                scoped_sku_count = cur.fetchone()["cnt"]
                global_limit = 5  # Reduce global when scoped results shown

            # --- Global SKUs ---
            sku_rank = _rank_expr("sm.stock_item_name")
            exclude_scope = ""
            if scope:
                exclude_scope = "AND sm.category_name != %(scope)s "
            cur.execute(
                f"{_SKU_SELECT} "
                f"WHERE {_SKU_MATCH} "
                f"  AND {_SKU_ACTIVE} "
                f"  {exclude_scope}"
                f"ORDER BY {sku_rank}, sm.stock_item_name "
                f"LIMIT %(glimit)s",
                {**params, "scope": scope, "glimit": global_limit},
            )
            skus = [_clean_row(r) for r in cur.fetchall()]
            cur.execute(
                f"SELECT COUNT(*) AS cnt FROM sku_metrics sm "
                f"LEFT JOIN stock_items si ON si.tally_name = sm.stock_item_name "
                f"WHERE {_SKU_MATCH} "
                f"  AND {_SKU_ACTIVE} "
                f"  {exclude_scope}",
                {**params, "scope": scope},
            )
            sku_count = cur.fetchone()["cnt"]

    result = {
        "brands": brands,
        "brand_count": brand_count,
        "skus": skus,
        "sku_count": sku_count,
    }
    if scope:
        result["scoped_skus"] = scoped_skus
        result["scoped_sku_count"] = scoped_sku_count
    return result
```

- [ ] **Step 4: Register the router in main.py**

In `src/api/main.py`, add to the imports (line ~60):

```python
from api.routes import brands, skus, po, parties, sync_status, suppliers, overrides, settings, auth_routes, users, search
```

And add after the existing `include_router` calls:

```python
app.include_router(search.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/test_search.py -v`
Expected: All tests PASS

- [ ] **Step 6: Manual smoke test against live DB**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --port 8000 &`
Then: `curl "http://localhost:8000/api/search?q=winsor" -H "Authorization: Bearer $(cd src && PYTHONPATH=. ./venv/Scripts/python -c "from api.auth import create_token; print(create_token(1,'test','admin'))")"`
Expected: JSON with brands and skus arrays

- [ ] **Step 7: Commit**

```bash
git add src/api/routes/search.py src/tests/test_search.py src/api/main.py
git commit -m "feat: add /api/search endpoint for universal search"
```

---

## Chunk 2: Frontend — Types, API Client, UniversalSearch Component

### Task 2: Add types and API client function

**Files:**
- Modify: `src/dashboard/src/lib/types.ts`
- Modify: `src/dashboard/src/lib/api.ts`

- [ ] **Step 1: Add SearchResults type to types.ts**

Append to end of `src/dashboard/src/lib/types.ts`:

```typescript
// ── Universal Search ──

export interface SearchBrandResult {
  category_name: string
  total_skus: number
  critical_skus: number
}

export interface SearchSkuResult {
  stock_item_name: string
  part_no: string | null
  category_name: string
  reorder_status: ReorderStatus
  current_stock: number
}

export interface SearchResults {
  brands: SearchBrandResult[]
  brand_count: number
  skus: SearchSkuResult[]
  sku_count: number
  scoped_skus?: SearchSkuResult[]
  scoped_sku_count?: number
}
```

- [ ] **Step 2: Add fetchSearch to api.ts**

Add to `src/dashboard/src/lib/api.ts` (after other fetch functions, before any non-fetch exports):

```typescript
export const fetchSearch = (q: string, scope?: string): Promise<SearchResults> =>
  api.get('/api/search', { params: { q, scope } }).then(r => r.data)
```

Also add `SearchResults` to the import from `types.ts` at top of file.

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/lib/types.ts src/dashboard/src/lib/api.ts
git commit -m "feat: add search types and API client for universal search"
```

### Task 3: Build UniversalSearch component

**Files:**
- Create: `src/dashboard/src/components/UniversalSearch.tsx`

- [ ] **Step 1: Create the UniversalSearch component**

Create `src/dashboard/src/components/UniversalSearch.tsx`:

```tsx
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
```

- [ ] **Step 2: Verify component compiles**

Run: `cd src/dashboard && npx tsc --noEmit`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/UniversalSearch.tsx
git commit -m "feat: add UniversalSearch component with desktop dropdown and mobile BottomSheet"
```

---

## Chunk 3: Replace Search on All Pages

### Task 4: Replace Home page brand search

**Files:**
- Modify: `src/dashboard/src/pages/Home.tsx`

- [ ] **Step 1: Replace search on Home page**

In `src/dashboard/src/pages/Home.tsx`:

1. Add import at top: `import UniversalSearch from '@/components/UniversalSearch'`
2. Remove the search-related state (`searchQuery`, `showDropdown`, `searchRef`, `filteredBrands`, the `useEffect` for click-outside, and the `brands` query if it was only used for search)
3. Replace the entire `<div ref={searchRef} className="relative">...</div>` search block with: `<UniversalSearch />`

The Home page also uses brands data for summary cards — keep that query. Only remove the search input/dropdown JSX and its state.

- [ ] **Step 2: Verify it compiles**

Run: `cd src/dashboard && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/Home.tsx
git commit -m "feat: replace Home page brand search with UniversalSearch"
```

### Task 5: Replace BrandOverview search

**Files:**
- Modify: `src/dashboard/src/pages/BrandOverview.tsx`

- [ ] **Step 1: Replace search on BrandOverview**

In `src/dashboard/src/pages/BrandOverview.tsx`:

1. Add import: `import UniversalSearch from '@/components/UniversalSearch'`
2. The existing search input is used to filter the brand list via API (`fetchBrands(debouncedSearch)`). Replace the search `<Input>` element with `<UniversalSearch />`.
3. Remove `search`, `debouncedSearch` state and the debounce `useEffect` since universal search handles its own API calls and navigation.
4. The brand list below should now show ALL brands (no search filter) — pass no `search` param to `fetchBrands()`.

- [ ] **Step 2: Verify it compiles**

Run: `cd src/dashboard && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/BrandOverview.tsx
git commit -m "feat: replace BrandOverview search with UniversalSearch"
```

### Task 6: Replace SkuDetail search

**Files:**
- Modify: `src/dashboard/src/pages/SkuDetail.tsx`

- [ ] **Step 1: Replace search on SkuDetail**

In `src/dashboard/src/pages/SkuDetail.tsx`:

1. Add import: `import UniversalSearch from '@/components/UniversalSearch'`
2. Replace the search `<Input>` element with `<UniversalSearch scope={decodedName} />`
3. Remove `search`, `debouncedSearch` state variables and their debounce `useEffect`
4. Remove the `search` parameter from the `fetchSkusPage` call (the table now shows all SKUs, filtered by status/ABC/XYZ as before)
5. Add `highlight` support: read `?highlight=` from URL params, when present pass it as the `search` param to `fetchSkusPage` so only that SKU shows, then clear the URL param after render

- [ ] **Step 2: Add highlight param handling**

At the top of the SkuDetail component, add:

```typescript
const [searchParams, setSearchParams] = useSearchParams()
const highlightName = searchParams.get('highlight')

// Clear highlight from URL after initial load
useEffect(() => {
  if (highlightName) {
    const timeout = window.setTimeout(() => {
      setSearchParams(prev => {
        prev.delete('highlight')
        return prev
      }, { replace: true })
    }, 2000)
    return () => window.clearTimeout(timeout)
  }
}, [highlightName, setSearchParams])
```

Pass `highlightName` as the `search` param to `fetchSkusPage` when present:

```typescript
const { data } = useQuery({
  queryKey: ['skus', categoryName, /* other params */, highlightName],
  queryFn: () => fetchSkusPage(decodedName, {
    search: highlightName || undefined,
    // ... other existing params
  }, pagination),
})
```

Add `useSearchParams` to the react-router-dom import.

- [ ] **Step 3: Verify it compiles**

Run: `cd src/dashboard && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/pages/SkuDetail.tsx
git commit -m "feat: replace SkuDetail search with UniversalSearch + highlight support"
```

### Task 7: Replace CriticalSkus search

**Files:**
- Modify: `src/dashboard/src/pages/CriticalSkus.tsx`

- [ ] **Step 1: Replace search on CriticalSkus**

In `src/dashboard/src/pages/CriticalSkus.tsx`:

1. Add import: `import UniversalSearch from '@/components/UniversalSearch'`
2. Replace the search `<Input>` with `<UniversalSearch />`
3. Remove the `search` state and the client-side filtering that used it
4. The CriticalSkus page shows pre-filtered critical items — the existing status filter handles that. UniversalSearch handles "jump somewhere else".

- [ ] **Step 2: Verify it compiles**

Run: `cd src/dashboard && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/CriticalSkus.tsx
git commit -m "feat: replace CriticalSkus search with UniversalSearch"
```

### Task 8: Replace DeadStock search

**Files:**
- Modify: `src/dashboard/src/pages/DeadStock.tsx`

- [ ] **Step 1: Replace search on DeadStock**

In `src/dashboard/src/pages/DeadStock.tsx`:

1. Add import: `import UniversalSearch from '@/components/UniversalSearch'`
2. Replace the search `<Input>` element with `<UniversalSearch scope={decodedName} />`
3. Remove the `search` state and any client-side filtering that used it
4. The dead stock list now shows all items (filtered by dead stock criteria already)

- [ ] **Step 2: Verify it compiles**

Run: `cd src/dashboard && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/pages/DeadStock.tsx
git commit -m "feat: replace DeadStock search with UniversalSearch"
```

---

## Chunk 4: Build, Test, Verify

### Task 9: Full build and manual verification

- [ ] **Step 1: Run full frontend build**

Run: `cd src/dashboard && npm run build`
Expected: Build succeeds, no errors

- [ ] **Step 2: Run backend tests**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest tests/ -v`
Expected: All tests pass including new search tests

- [ ] **Step 3: Start the app and test manually**

Run: `cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000`

Test in browser at `http://localhost:8000`:
1. Home page: type "winsor" — should show brand + SKU results
2. Brand overview: type a SKU name — should show it with brand
3. Click a SKU result — should navigate to the brand's SKU page with that item visible
4. On a brand's SKU page: type another brand's SKU — should show scoped results first, then global
5. Resize to mobile width (<768px) — results should appear in BottomSheet

- [ ] **Step 4: Final commit with build output**

```bash
git add src/dashboard/dist/
git commit -m "build: rebuild frontend with universal search"
```
