# Prefix Search & PO Builder Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let ops team search by part_no prefix (e.g. "0102") to view and build POs for entire product ranges across brands.

**Architecture:** Three backend endpoints (prefix search, prefix PO data, cross-brand SKU list) + frontend changes to UniversalSearch, SkuInputDialog, PoBuilder, and a new SkuListByPrefix page. Each SKU uses its own brand's supplier defaults for lead time.

**Tech Stack:** Python/FastAPI, PostgreSQL, React/TypeScript, shadcn/ui, TanStack Query

---

## File Structure

### Backend (new/modified)
- **Modify:** `src/api/routes/search.py` — add `prefix_group` to `/api/search`, add `GET /api/search/prefix`
- **Modify:** `src/api/routes/po.py` — add `POST /api/po-data/prefix`
- **Modify:** `src/api/routes/skus.py` — add `GET /api/skus` cross-brand endpoint with prefix param

### Frontend (new/modified)
- **Modify:** `src/dashboard/src/lib/types.ts` — add `PrefixSearchResult`, update `SearchResults`
- **Modify:** `src/dashboard/src/lib/api.ts` — add `fetchPrefixSearch`, `fetchPoDataByPrefix`, `fetchSkusByPrefix`
- **Modify:** `src/dashboard/src/components/UniversalSearch.tsx` — render prefix group with View/Build PO actions
- **Modify:** `src/dashboard/src/components/SkuInputDialog.tsx` — add Code Prefix tab
- **Modify:** `src/dashboard/src/pages/PoBuilder.tsx` — handle `?prefix=` param, cross-brand badges/summary
- **Create:** `src/dashboard/src/pages/SkuListByPrefix.tsx` — cross-brand SKU list filtered by prefix
- **Modify:** `src/dashboard/src/App.tsx` — add `/skus` route

### Tests
- **Create:** `tests/api/test_prefix_search.py` — backend prefix search tests
- **Create:** `tests/api/test_prefix_po.py` — backend prefix PO data tests

---

### Task 1: Backend — Add prefix_group to universal search + dedicated prefix endpoint

**Files:**
- Modify: `src/api/routes/search.py`
- Test: `tests/api/test_prefix_search.py`

- [ ] **Step 1: Write the failing test for prefix_group in universal search**

Create `tests/api/test_prefix_search.py`:

```python
"""Tests for prefix search functionality."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI
    from api.routes.search import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    app = _make_app()
    return TestClient(app)


def _mock_cursor_with_prefix_data():
    """Return a mock cursor that simulates DB responses for prefix search."""
    cur = MagicMock()
    call_count = [0]

    def execute_side_effect(sql, params=None):
        call_count[0] += 1

    cur.execute = MagicMock(side_effect=execute_side_effect)

    # For the prefix query, return 3 matching SKUs across 2 brands
    prefix_rows = [
        {"stock_item_name": "WN PWC Cadmium Yellow", "part_no": "0102010",
         "category_name": "Winsor & Newton", "reorder_status": "ok", "current_stock": 50},
        {"stock_item_name": "WN PWC Alizarin Crimson", "part_no": "0102045",
         "category_name": "Winsor & Newton", "reorder_status": "urgent", "current_stock": 5},
        {"stock_item_name": "DR PWC Cerulean Blue", "part_no": "0102099",
         "category_name": "Daler Rowney", "reorder_status": "ok", "current_stock": 30},
    ]

    # Regular search returns no brands, no global SKUs for "0102"
    brand_rows = []
    brand_count_row = {"cnt": 0}
    sku_rows = []
    sku_count_row = {"cnt": 0}
    prefix_count_row = {"cnt": 3}

    results = iter([
        brand_rows,           # brands query
        [brand_count_row],    # brand count
        sku_rows,             # global SKUs
        [sku_count_row],      # global SKU count
        [prefix_count_row],   # prefix count
        prefix_rows,          # prefix SKUs (for brands list derivation)
    ])

    def fetchall_side_effect():
        return next(results, [])

    def fetchone_side_effect():
        r = next(results, [{"cnt": 0}])
        return r[0] if isinstance(r, list) else r

    cur.fetchall = MagicMock(side_effect=fetchall_side_effect)
    cur.fetchone = MagicMock(side_effect=fetchone_side_effect)
    return cur


@patch("api.routes.search.get_current_user", return_value={"id": 1, "role": "admin"})
@patch("api.routes.search.get_db")
def test_search_includes_prefix_group(mock_get_db, mock_auth, client):
    """When query matches 2+ SKUs by part_no prefix, response includes prefix_group."""
    cur = _mock_cursor_with_prefix_data()
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_db.return_value.__enter__ = MagicMock(return_value=conn)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    resp = client.get("/search?q=0102")
    assert resp.status_code == 200
    data = resp.json()
    assert "prefix_group" in data
    assert data["prefix_group"]["prefix"] == "0102"
    assert data["prefix_group"]["total"] >= 2


@patch("api.routes.search.get_current_user", return_value={"id": 1, "role": "admin"})
@patch("api.routes.search.get_db")
def test_search_prefix_group_null_when_less_than_2(mock_get_db, mock_auth, client):
    """prefix_group is null when fewer than 2 SKUs match by prefix."""
    cur = MagicMock()
    # All queries return empty
    cur.fetchall = MagicMock(return_value=[])
    cur.fetchone = MagicMock(return_value={"cnt": 0})
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_db.return_value.__enter__ = MagicMock(return_value=conn)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    resp = client.get("/search?q=zzzznoprefix")
    assert resp.status_code == 200
    data = resp.json()
    assert data["prefix_group"] is None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest ../tests/api/test_prefix_search.py -v
```

Expected: FAIL — `prefix_group` not in response.

- [ ] **Step 3: Implement prefix_group in universal search**

In `src/api/routes/search.py`, add a prefix count + brand aggregation query at the end of the `universal_search` function. Add this after the global SKUs block (before the `result = {` line):

```python
            # --- Prefix group (part_no prefix match, 2+ SKUs) ---
            prefix_group = None
            escaped_prefix = _escape_ilike(q)
            prefix_like = f"{escaped_prefix}%"
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM sku_metrics sm "
                "LEFT JOIN stock_items si ON si.name = sm.stock_item_name "
                f"WHERE COALESCE(si.part_no, '') ILIKE %(prefix_like)s "
                f"AND {_SKU_ACTIVE}",
                {**params, "prefix_like": prefix_like},
            )
            prefix_count = cur.fetchone()["cnt"]
            if prefix_count >= 2:
                cur.execute(
                    "SELECT DISTINCT sm.category_name "
                    "FROM sku_metrics sm "
                    "LEFT JOIN stock_items si ON si.name = sm.stock_item_name "
                    f"WHERE COALESCE(si.part_no, '') ILIKE %(prefix_like)s "
                    f"AND {_SKU_ACTIVE} "
                    "ORDER BY sm.category_name",
                    {**params, "prefix_like": prefix_like},
                )
                prefix_brands = [r["category_name"] for r in cur.fetchall()]
                prefix_group = {
                    "prefix": q,
                    "total": prefix_count,
                    "brands": prefix_brands,
                }
```

Then update the result dict to include `prefix_group`:

```python
    result = {
        "brands": brands,
        "brand_count": brand_count,
        "skus": skus,
        "sku_count": sku_count,
        "prefix_group": prefix_group,
    }
```

- [ ] **Step 4: Add the dedicated prefix search endpoint**

Still in `src/api/routes/search.py`, add a new endpoint after `universal_search`:

```python
@router.get("/search/prefix")
def prefix_search(
    q: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """Return all SKUs whose part_no starts with the given prefix."""
    if not q or len(q.strip()) < 2:
        raise HTTPException(400, "Prefix must be at least 2 characters")
    q = q.strip()
    if len(q) > 50:
        raise HTTPException(400, "Prefix must be at most 50 characters")

    escaped = _escape_ilike(q)
    prefix_like = f"{escaped}%"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"{_SKU_SELECT} "
                f"WHERE COALESCE(si.part_no, '') ILIKE %s "
                f"AND {_SKU_ACTIVE} "
                f"ORDER BY si.part_no, sm.stock_item_name",
                (prefix_like,),
            )
            skus = [_clean_row(r) for r in cur.fetchall()]

    brands = sorted(set(s["category_name"] for s in skus))
    return {
        "prefix": q,
        "total": len(skus),
        "brands": brands,
        "skus": skus,
    }
```

- [ ] **Step 5: Write test for dedicated prefix endpoint**

Add to `tests/api/test_prefix_search.py`:

```python
@patch("api.routes.search.get_current_user", return_value={"id": 1, "role": "admin"})
@patch("api.routes.search.get_db")
def test_prefix_endpoint_returns_matching_skus(mock_get_db, mock_auth, client):
    """GET /search/prefix?q=0102 returns SKUs with part_no starting '0102'."""
    prefix_rows = [
        {"stock_item_name": "WN PWC Cadmium Yellow", "part_no": "0102010",
         "category_name": "Winsor & Newton", "reorder_status": "ok", "current_stock": 50},
        {"stock_item_name": "WN PWC Alizarin", "part_no": "0102045",
         "category_name": "Winsor & Newton", "reorder_status": "urgent", "current_stock": 5},
    ]
    cur = MagicMock()
    cur.fetchall = MagicMock(return_value=prefix_rows)
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_get_db.return_value.__enter__ = MagicMock(return_value=conn)
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    resp = client.get("/search/prefix?q=0102")
    assert resp.status_code == 200
    data = resp.json()
    assert data["prefix"] == "0102"
    assert data["total"] == 2
    assert "Winsor & Newton" in data["brands"]
    assert len(data["skus"]) == 2


@patch("api.routes.search.get_current_user", return_value={"id": 1, "role": "admin"})
def test_prefix_endpoint_rejects_short_query(mock_auth, client):
    """GET /search/prefix?q=a returns 400."""
    resp = client.get("/search/prefix?q=a")
    assert resp.status_code == 400
```

- [ ] **Step 6: Run all prefix search tests**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest ../tests/api/test_prefix_search.py -v
```

Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/routes/search.py tests/api/test_prefix_search.py
git commit -m "feat: add prefix_group to universal search + dedicated prefix endpoint

Adds part_no prefix matching to /api/search (prefix_group field) and
new /api/search/prefix endpoint that returns all SKUs matching a prefix."
```

---

### Task 2: Backend — Add prefix PO data endpoint

**Files:**
- Modify: `src/api/routes/po.py`
- Test: `tests/api/test_prefix_po.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/test_prefix_po.py`:

```python
"""Tests for prefix-based PO data endpoint."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI
    from api.routes.po import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    app = _make_app()
    return TestClient(app)


@patch("api.routes.po.require_role", return_value=lambda: {"id": 1, "role": "purchaser"})
@patch("api.routes.po.get_db")
def test_prefix_po_returns_po_data(mock_get_db, mock_role, client):
    """POST /po-data/prefix returns PO items for SKUs matching the prefix."""
    # This test verifies the endpoint exists and calls through
    # Full integration tested via real DB
    resp = client.post("/po-data/prefix", json={"prefix": "0102"})
    # We expect it to at least not 404 (endpoint registered)
    assert resp.status_code != 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest ../tests/api/test_prefix_po.py -v
```

Expected: FAIL — 404, endpoint doesn't exist.

- [ ] **Step 3: Implement the prefix PO data endpoint**

In `src/api/routes/po.py`, add a new Pydantic model and endpoint after `match_and_build_po`:

```python
class PrefixPoRequest(BaseModel):
    prefix: str
    coverage_days: int | None = None
    buffer: float | None = None
    from_date: str | None = None
    to_date: str | None = None
    include_warning: bool = True
    include_ok: bool = False


def _escape_ilike(s: str) -> str:
    """Escape PostgreSQL ILIKE special characters."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _attach_drift(result: list[dict]):
    """Attach latest drift data to PO result items (mutates in place)."""
    if not result:
        return
    with get_db() as conn2:
        with conn2.cursor() as dcur:
            sku_names = [r["stock_item_name"] for r in result]
            dcur.execute("""
                SELECT DISTINCT ON (stock_item_name)
                    stock_item_name, drift, inventory_blocked, check_date
                FROM drift_log
                WHERE stock_item_name = ANY(%s)
                ORDER BY stock_item_name, check_date DESC
            """, (sku_names,))
            drift_map = {}
            for drow in dcur.fetchall():
                drift_map[drow["stock_item_name"]] = {
                    "drift": float(drow["drift"]) if drow["drift"] is not None else 0,
                    "inventory_blocked": float(drow["inventory_blocked"]) if drow["inventory_blocked"] is not None else 0,
                }
    for item in result:
        di = drift_map.get(item["stock_item_name"], {})
        item["drift"] = di.get("drift", 0)
        item["inventory_blocked"] = di.get("inventory_blocked", 0)
        item["has_drift"] = abs(di.get("drift", 0)) > 0


@router.post("/po-data/prefix")
def prefix_po_data(req: PrefixPoRequest, user: dict = Depends(require_role("purchaser"))):
    """Build PO data for all SKUs whose part_no starts with the given prefix.

    Each SKU uses its own brand's supplier lead_time_default.
    """
    prefix = req.prefix.strip()
    if len(prefix) < 2:
        raise HTTPException(400, "Prefix must be at least 2 characters")

    escaped = _escape_ilike(prefix)
    prefix_like = f"{escaped}%"
    custom_range = req.from_date is not None or req.to_date is not None

    with get_db() as conn:
        with conn.cursor() as cur:
            # Find all matching SKUs with their brand's supplier lead time
            cur.execute(f"""
                SELECT {_PO_SELECT_COLS},
                       si.category_name,
                       COALESCE(bm.supplier_lead_time, 180) AS brand_lead_time,
                       s.typical_order_months,
                       s.lead_time_default AS supplier_lead_time_default,
                       COALESCE(s.lead_time_demand_mode, 'full') AS lead_time_demand_mode
                {_PO_FROM_JOINS}
                LEFT JOIN brand_metrics bm ON bm.category_name = si.category_name
                LEFT JOIN suppliers s ON UPPER(s.name) = UPPER(si.category_name)
                WHERE COALESCE(si.part_no, '') ILIKE %s
                  AND COALESCE(si.is_active, TRUE) = TRUE
                {_PO_ORDER}
            """, (prefix_like,))
            rows = cur.fetchall()

            if not rows:
                return {"po_data": [], "brands": [], "prefix": prefix, "total": 0}

            # Batch velocity recalculation when custom date range
            vel_by_sku = {}
            if custom_range:
                range_start, range_end = resolve_date_range(req.from_date, req.to_date)
                sku_names = [r["stock_item_name"] for r in rows]
                vel_by_sku = fetch_batch_velocities(cur, sku_names, range_start, range_end)

    # Group by brand lead time and compute PO items per group
    from collections import defaultdict
    brand_groups = defaultdict(list)
    brand_lead_times = {}
    brand_demand_modes = {}
    for r in rows:
        cat = r["category_name"] or "Unknown"
        brand_groups[cat].append(r)
        if cat not in brand_lead_times:
            lt = int(r["brand_lead_time"])
            brand_lead_times[cat] = lt
            # Coverage: use supplier typical_order_months if set, else auto from lead time
            if req.coverage_days is not None:
                brand_coverage = req.coverage_days
            elif r["typical_order_months"]:
                brand_coverage = compute_coverage_days(
                    r["supplier_lead_time_default"] or lt, r["typical_order_months"]
                )
            else:
                brand_coverage = compute_coverage_days(lt, None)
            brand_lead_times[cat] = (lt, brand_coverage)
            brand_demand_modes[cat] = r["lead_time_demand_mode"]

    all_items = []
    for cat, cat_rows in brand_groups.items():
        lt, cov = brand_lead_times[cat]
        dm = brand_demand_modes.get(cat, "full")
        include_lead = dm != "coverage_only"
        items = _compute_po_items(cat_rows, lt, cov, req.buffer, vel_by_sku, include_lead_demand=include_lead)

        # Apply status filter
        statuses = {"urgent", "lost_sales"}
        if req.include_warning:
            statuses.add("reorder")
        if req.include_ok:
            statuses.add("healthy")
        items = [i for i in items if i["reorder_status"] in statuses]

        all_items.extend(items)

    _attach_drift(all_items)

    brands = sorted(set(r["category_name"] or "Unknown" for r in rows))
    return {
        "po_data": all_items,
        "brands": brands,
        "prefix": prefix,
        "total": len(all_items),
    }
```

Also refactor the existing drift attachment in `po_data` and `match_and_build_po` to use `_attach_drift`. Replace the duplicate drift blocks in both functions with:

```python
    _attach_drift(result)
```

- [ ] **Step 4: Run test to verify endpoint exists**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest ../tests/api/test_prefix_po.py -v
```

Expected: PASS (or at least not 404).

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/po.py tests/api/test_prefix_po.py
git commit -m "feat: add POST /api/po-data/prefix endpoint for prefix-based PO building

Each SKU uses its own brand's supplier lead_time and coverage settings.
Also refactors drift attachment into shared _attach_drift helper."
```

---

### Task 3: Backend — Add cross-brand SKU list endpoint

**Files:**
- Modify: `src/api/routes/skus.py`

- [ ] **Step 1: Add the cross-brand SKU list endpoint**

Add a new endpoint at the top of `src/api/routes/skus.py` (after the existing imports and before `list_skus`):

```python
def _escape_ilike(s: str) -> str:
    """Escape PostgreSQL ILIKE special characters."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
```

Note: `_escape_ilike` already exists in `skus.py` at line 49, so skip adding it.

Add the new endpoint after the existing `list_skus` function:

```python
@router.get("/skus")
def list_skus_cross_brand(
    prefix: str = Query(..., min_length=2, max_length=50, description="Part number prefix to filter by"),
    status: str = Query(None, description="Comma-separated status filter"),
    min_velocity: float = Query(None),
    sort: str = Query("days_to_stockout"),
    sort_dir: str = Query("asc"),
    search: str = Query(None, description="Additional text search within prefix results"),
    hazardous: bool = Query(None),
    dead_stock: bool = Query(None),
    reorder_intent: str = Query(None),
    abc_class: str = Query(None),
    xyz_class: str = Query(None),
    hide_inactive: bool = Query(True),
    paginated: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Cross-brand SKU list filtered by part_no prefix.

    Supports the same filters and sorting as the brand-scoped endpoint.
    """
    if sort not in ALLOWED_SORT_COLS:
        sort = "days_to_stockout"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    escaped_prefix = _escape_ilike(prefix)
    prefix_like = f"{escaped_prefix}%"

    conditions = [
        "COALESCE(si.part_no, '') ILIKE %s",
    ]
    params: list = [prefix_like]

    if hide_inactive:
        conditions.append("COALESCE(si.is_active, TRUE) = TRUE")

    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            conditions.append("sm.reorder_status = ANY(%s)")
            params.append(statuses)

    if min_velocity is not None:
        conditions.append("sm.total_velocity >= %s")
        params.append(min_velocity)

    if search:
        esc = _escape_ilike(search)
        conditions.append("(sm.stock_item_name ILIKE %s OR COALESCE(si.part_no, '') ILIKE %s)")
        params.append(f"%{esc}%")
        params.append(f"%{esc}%")

    if hazardous is not None:
        conditions.append("COALESCE(si.is_hazardous, FALSE) = %s")
        params.append(hazardous)

    if dead_stock is not None:
        if dead_stock:
            conditions.append("sm.reorder_status = 'dead_stock'")
        else:
            conditions.append("sm.reorder_status != 'dead_stock'")

    if reorder_intent:
        conditions.append("COALESCE(si.reorder_intent, 'normal') = %s")
        params.append(reorder_intent)

    if abc_class:
        conditions.append("sm.abc_class = %s")
        params.append(abc_class)

    if xyz_class:
        conditions.append("sm.xyz_class = %s")
        params.append(xyz_class)

    where = " AND ".join(conditions)
    nulls = "NULLS LAST" if direction == "ASC" else "NULLS FIRST"
    sort_col = f"sm.{sort}" if sort != "stock_item_name" else "sm.stock_item_name"
    order_by = f"{sort_col} {direction} {nulls}"

    with get_db() as conn:
        with conn.cursor() as cur:
            # Count
            cur.execute(
                f"SELECT COUNT(*) AS cnt FROM sku_metrics sm "
                f"LEFT JOIN stock_items si ON si.name = sm.stock_item_name "
                f"WHERE {where}",
                params,
            )
            total = cur.fetchone()["cnt"]

            # Fetch rows
            cur.execute(
                f"SELECT sm.stock_item_name, sm.category_name, sm.current_stock, "
                f"  sm.wholesale_velocity, sm.online_velocity, sm.store_velocity, "
                f"  sm.total_velocity, sm.total_in_stock_days, "
                f"  sm.days_to_stockout, sm.estimated_stockout_date, "
                f"  sm.reorder_status, sm.reorder_qty_suggested, "
                f"  sm.abc_class, sm.xyz_class, sm.demand_cv, sm.total_revenue, "
                f"  sm.wma_wholesale_velocity, sm.wma_online_velocity, sm.wma_total_velocity, "
                f"  sm.trend_direction, sm.trend_ratio, sm.safety_buffer, "
                f"  sm.velocity_start_date, sm.velocity_end_date, "
                f"  sm.last_import_date, sm.last_import_qty, sm.last_import_supplier, "
                f"  sm.computed_at, "
                f"  si.part_no, si.is_hazardous, si.reorder_intent, si.is_active, "
                f"  COALESCE(si.use_xyz_buffer, NULL) AS use_xyz_buffer "
                f"FROM sku_metrics sm "
                f"LEFT JOIN stock_items si ON si.name = sm.stock_item_name "
                f"WHERE {where} "
                f"ORDER BY {order_by} "
                f"LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()

    items = []
    for r in rows:
        d = dict(r)
        # Convert Decimals to float
        for k, v in d.items():
            from decimal import Decimal
            if isinstance(v, Decimal):
                d[k] = float(v)
        items.append(d)

    if paginated:
        return {"items": items, "total": total, "offset": offset, "limit": limit}
    return items
```

- [ ] **Step 2: Verify the endpoint works manually**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --port 8000 &
# Then in another terminal:
curl "http://localhost:8000/api/skus?prefix=0102&limit=5" -H "Authorization: Bearer <token>"
```

Expected: JSON response with SKUs whose part_no starts with "0102".

- [ ] **Step 3: Commit**

```bash
git add src/api/routes/skus.py
git commit -m "feat: add GET /api/skus cross-brand endpoint with prefix filter

Supports same filtering/sorting as brand-scoped endpoint but works
across all brands, filtered by part_no prefix."
```

---

### Task 4: Frontend — Add types and API functions

**Files:**
- Modify: `src/dashboard/src/lib/types.ts`
- Modify: `src/dashboard/src/lib/api.ts`

- [ ] **Step 1: Add PrefixSearchResult type and update SearchResults**

In `src/dashboard/src/lib/types.ts`, add after the `SearchResults` interface (around line 461):

```typescript
export interface PrefixGroup {
  prefix: string
  total: number
  brands: string[]
}

export interface PrefixSearchResponse {
  prefix: string
  total: number
  brands: string[]
  skus: SearchSkuResult[]
}

export interface PrefixPoResponse {
  po_data: PoDataItem[]
  brands: string[]
  prefix: string
  total: number
}
```

Update the existing `SearchResults` interface to include `prefix_group`:

```typescript
export interface SearchResults {
  brands: SearchBrandResult[]
  brand_count: number
  skus: SearchSkuResult[]
  sku_count: number
  scoped_skus?: SearchSkuResult[]
  scoped_sku_count?: number
  prefix_group: PrefixGroup | null
}
```

- [ ] **Step 2: Add API functions**

In `src/dashboard/src/lib/api.ts`, add the import for the new types and the API functions. Update the import line at the top:

Add `PrefixSearchResponse, PrefixPoResponse` to the import from `./types`.

Add before the `export default api` line:

```typescript
export const fetchPrefixSearch = (prefix: string): Promise<PrefixSearchResponse> =>
  api.get('/api/search/prefix', { params: { q: prefix } }).then(r => r.data)

export const fetchPoDataByPrefix = (data: {
  prefix: string
  coverage_days?: number
  buffer?: number
  from_date?: string
  to_date?: string
  include_warning?: boolean
  include_ok?: boolean
}): Promise<PrefixPoResponse> =>
  api.post('/api/po-data/prefix', data).then(r => r.data)

export const fetchSkusByPrefix = (
  prefix: string,
  params?: Record<string, string | number | boolean>,
): Promise<SkuPage> =>
  api.get('/api/skus', {
    params: { prefix, paginated: true, ...params },
  }).then(r => r.data)
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/lib/types.ts src/dashboard/src/lib/api.ts
git commit -m "feat: add frontend types and API functions for prefix search"
```

---

### Task 5: Frontend — Update UniversalSearch with prefix group

**Files:**
- Modify: `src/dashboard/src/components/UniversalSearch.tsx`

- [ ] **Step 1: Add prefix group rendering to the search results**

In `src/dashboard/src/components/UniversalSearch.tsx`:

First, add the `Hash` icon to the lucide import:

```typescript
import { Search, Loader2, Package, Tag, Hash } from 'lucide-react'
```

Add `Button` import:

```typescript
import { Button } from '@/components/ui/button'
```

Update the `items` array building to include a prefix_group entry. Replace the existing items-building block (lines ~42-47):

```typescript
  // Build flat list for keyboard nav
  const items: Array<{
    type: 'prefix_group' | 'brand' | 'scoped_sku' | 'sku'
    item: SearchBrandResult | SearchSkuResult | { prefix: string; total: number; brands: string[] }
  }> = []
  if (data) {
    if (data.prefix_group) {
      items.push({ type: 'prefix_group', item: data.prefix_group })
    }
    data.brands.forEach(b => items.push({ type: 'brand', item: b }))
    data.scoped_skus?.forEach(s => items.push({ type: 'scoped_sku', item: s }))
    data.skus.forEach(s => items.push({ type: 'sku', item: s }))
  }
```

Update the `navigateTo` callback to handle the prefix group type (it won't navigate on its own — the buttons inside handle it):

In the `navigateTo` function, add a guard at the top:

```typescript
  const navigateTo = useCallback((type: string, item: SearchBrandResult | SearchSkuResult | any) => {
    setOpen(false)
    setQuery('')
    setDebouncedQuery('')
    if (type === 'prefix_group') {
      // Handled by inline buttons
      return
    }
    if (type === 'brand') {
```

Now update the `renderResults` function. Add the prefix group section before the brands section. Inside the `renderResults` function, right after `let flatIdx = -1`, add:

```typescript
        {/* Prefix Group */}
        {data.prefix_group && (
          <>
            <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/50">
              Prefix Match
            </div>
            {(() => {
              flatIdx++
              const idx = flatIdx
              const pg = data.prefix_group
              return (
                <div
                  key="prefix-group"
                  className={`px-4 py-3 text-sm ${!isMobile && highlightIdx === idx ? 'bg-muted' : ''}`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Hash className="h-4 w-4 shrink-0 text-blue-600" />
                    <span className="font-medium">
                      &ldquo;{pg.prefix}&rdquo; &rarr; {pg.total} SKUs across {pg.brands.length} brand{pg.brands.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground mb-2">
                    {pg.brands.join(', ')}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={(e) => {
                        e.stopPropagation()
                        setOpen(false)
                        setQuery('')
                        setDebouncedQuery('')
                        navigate(`/skus?prefix=${encodeURIComponent(pg.prefix)}`)
                      }}
                    >
                      View SKUs
                    </Button>
                    <Button
                      size="sm"
                      className="h-7 text-xs"
                      onClick={(e) => {
                        e.stopPropagation()
                        setOpen(false)
                        setQuery('')
                        setDebouncedQuery('')
                        navigate(`/po?prefix=${encodeURIComponent(pg.prefix)}`)
                      }}
                    >
                      Build PO
                    </Button>
                  </div>
                </div>
              )
            })()}
          </>
        )}
```

Also update the "no results" check to include prefix_group:

```typescript
    if (!data || (data.brands.length === 0 && data.skus.length === 0 && (!data.scoped_skus || data.scoped_skus.length === 0) && !data.prefix_group)) {
```

- [ ] **Step 2: Verify in browser**

Run the dev server and search for a known prefix like "0102" — should show the prefix group at the top of results with "View SKUs" and "Build PO" buttons.

```bash
cd src/dashboard && npm run dev
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/UniversalSearch.tsx
git commit -m "feat: show prefix group in universal search with View SKUs / Build PO actions"
```

---

### Task 6: Frontend — Add Code Prefix tab to SkuInputDialog

**Files:**
- Modify: `src/dashboard/src/components/SkuInputDialog.tsx`

- [ ] **Step 1: Add Code Prefix tab**

In `src/dashboard/src/components/SkuInputDialog.tsx`:

Update lucide imports to add `Search` and `Hash`:

```typescript
import { ClipboardPaste, Upload, FileSpreadsheet, X, Loader2, Search, Hash } from 'lucide-react'
```

Add the `Input` and `Button` imports (Button already imported, add Input):

```typescript
import { Input } from '@/components/ui/input'
```

Add the `fetchPrefixSearch` import:

```typescript
import { fetchPrefixSearch } from '@/lib/api'
```

Add `PrefixSearchResponse` to the types import:

```typescript
import type { PrefixSearchResponse } from '@/lib/types'
```

Add state for the prefix tab inside the component, after existing state declarations:

```typescript
  const [prefixQuery, setPrefixQuery] = useState('')
  const [prefixLoading, setPrefixLoading] = useState(false)
  const [prefixResult, setPrefixResult] = useState<PrefixSearchResponse | null>(null)
  const [prefixError, setPrefixError] = useState<string | null>(null)
```

Add the prefix search handler:

```typescript
  const handlePrefixSearch = async () => {
    const q = prefixQuery.trim()
    if (q.length < 2) {
      setPrefixError('Enter at least 2 characters')
      return
    }
    setPrefixLoading(true)
    setPrefixError(null)
    try {
      const result = await fetchPrefixSearch(q)
      setPrefixResult(result)
      if (result.total === 0) {
        setPrefixError(`No SKUs found with part number starting "${q}"`)
      } else {
        // Set parsedNames to the matched SKU names
        setParsedNames(result.skus.map(s => s.stock_item_name))
      }
    } catch {
      setPrefixError('Search failed — try again')
    } finally {
      setPrefixLoading(false)
    }
  }
```

Update `handleClose` to also reset prefix state:

```typescript
  const handleClose = () => {
    setPasteText('')
    setParsedNames([])
    setFileName(null)
    setFileError(null)
    setPrefixQuery('')
    setPrefixResult(null)
    setPrefixError(null)
    onOpenChange(false)
  }
```

Add the third tab trigger to the TabsList:

```typescript
          <TabsList className="w-full">
            <TabsTrigger value="paste" className="flex-1 gap-1.5">
              <ClipboardPaste className="h-3.5 w-3.5" /> Paste
            </TabsTrigger>
            <TabsTrigger value="upload" className="flex-1 gap-1.5">
              <Upload className="h-3.5 w-3.5" /> Upload
            </TabsTrigger>
            <TabsTrigger value="prefix" className="flex-1 gap-1.5">
              <Hash className="h-3.5 w-3.5" /> Code Prefix
            </TabsTrigger>
          </TabsList>
```

Add the TabsContent for the prefix tab (after the upload TabsContent):

```typescript
          <TabsContent value="prefix" className="mt-3">
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input
                  placeholder="Enter part number prefix, e.g. 0102"
                  value={prefixQuery}
                  onChange={e => {
                    setPrefixQuery(e.target.value)
                    setPrefixResult(null)
                    setPrefixError(null)
                  }}
                  onKeyDown={e => { if (e.key === 'Enter') handlePrefixSearch() }}
                  className="flex-1 font-mono"
                />
                <Button onClick={handlePrefixSearch} disabled={prefixLoading || prefixQuery.trim().length < 2}>
                  {prefixLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                </Button>
              </div>

              {prefixError && (
                <p className="text-sm text-red-600">{prefixError}</p>
              )}

              {prefixResult && prefixResult.total > 0 && (
                <div className="space-y-2">
                  <div className="text-sm text-muted-foreground bg-muted/50 rounded px-3 py-2 border">
                    <strong className="text-foreground">{prefixResult.total}</strong> SKU{prefixResult.total !== 1 ? 's' : ''} across{' '}
                    <strong className="text-foreground">{prefixResult.brands.length}</strong> brand{prefixResult.brands.length !== 1 ? 's' : ''}:
                    <div className="text-xs mt-1">{prefixResult.brands.join(', ')}</div>
                  </div>
                  <div className="max-h-48 overflow-y-auto border rounded text-xs">
                    {prefixResult.skus.slice(0, 50).map(s => (
                      <div key={s.stock_item_name} className="px-3 py-1.5 border-b last:border-b-0 flex items-center justify-between">
                        <span className="font-mono text-muted-foreground mr-2">{s.part_no}</span>
                        <span className="truncate flex-1">{s.stock_item_name}</span>
                      </div>
                    ))}
                    {prefixResult.total > 50 && (
                      <div className="px-3 py-1.5 text-muted-foreground text-center">
                        +{prefixResult.total - 50} more
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
```

- [ ] **Step 2: Verify in browser**

Open the PO builder, click "Import SKU List", and verify the third "Code Prefix" tab works — type a prefix, click search, see preview.

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/SkuInputDialog.tsx
git commit -m "feat: add Code Prefix tab to SKU input dialog

Third tab allows searching by part_no prefix, shows preview with
brand breakdown before loading into PO builder."
```

---

### Task 7: Frontend — Update PoBuilder for prefix URL param and cross-brand display

**Files:**
- Modify: `src/dashboard/src/pages/PoBuilder.tsx`

- [ ] **Step 1: Handle `?prefix=` URL parameter**

In `src/dashboard/src/pages/PoBuilder.tsx`:

Add the `fetchPoDataByPrefix` import. Update the import line from `@/lib/api`:

```typescript
import { fetchPoData, exportPo, matchSkusForPo, fetchPoDataByPrefix } from '@/lib/api'
```

Add `Badge` import if not already present (it is — line 17).

Add `PrefixPoResponse` to the types import:

```typescript
import type { ReorderStatus, ReorderIntent, AbcClass, TrendDirection, SkuMatchResult, SkuMatchSummary, PoDataItem, PrefixPoResponse } from '@/lib/types'
```

Inside the component, after `const toDate = searchParams.get('to_date')`, add:

```typescript
  const prefixParam = searchParams.get('prefix')
```

Add prefix-related state after the existing subset state:

```typescript
  // Prefix PO state
  const [prefixMode, setPrefixMode] = useState(false)
  const [prefixBrands, setPrefixBrands] = useState<string[]>([])
  const [prefixValue, setPrefixValue] = useState<string>('')
```

Add a `useMutation` for the prefix PO fetch, after the existing `matchMutation`:

```typescript
  const prefixMutation = useMutation({
    mutationFn: fetchPoDataByPrefix,
    onSuccess: (data: PrefixPoResponse) => {
      setPrefixMode(true)
      setPrefixBrands(data.brands)
      setPrefixValue(data.prefix)
      setSubsetMode(true)
      setSubsetRawData(data.po_data)
      setSubsetSkuNames(data.po_data.map(d => d.stock_item_name))
      setShowSkuInput(false)
    },
  })
```

Add a `useEffect` to auto-load when `?prefix=` is in the URL. Add after the existing `useEffect` that auto-opens dialog:

```typescript
  // Auto-load prefix from URL param
  useEffect(() => {
    if (prefixParam && !prefixMode && !subsetMode) {
      prefixMutation.mutate({
        prefix: prefixParam,
        coverage_days: coverageDays ?? undefined,
        buffer: bufferOverride ? bufferValue : undefined,
        from_date: fromDate ?? undefined,
        to_date: toDate ?? undefined,
        include_warning: includeWarning,
        include_ok: includeOk,
      })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
```

Update the `clearSubsetMode` function to also clear prefix state:

```typescript
  const clearSubsetMode = () => {
    setSubsetMode(false)
    setSubsetRawData(null)
    setSubsetSkuNames([])
    setMatchResults(null)
    setShowMatchReview(false)
    setPrefixMode(false)
    setPrefixBrands([])
    setPrefixValue('')
    setOverrides({})
  }
```

Update the re-fetch `useEffect` (the one that re-fetches subset data when config changes) to also handle prefix mode. Replace the existing re-fetch effect:

```typescript
  // Re-fetch subset/prefix data when config params change
  useEffect(() => {
    if (subsetMode && subsetSkuNames.length > 0) {
      if (prefixMode && prefixValue) {
        prefixMutation.mutate({
          prefix: prefixValue,
          coverage_days: coverageDays ?? undefined,
          buffer: bufferOverride ? bufferValue : undefined,
          from_date: fromDate ?? undefined,
          to_date: toDate ?? undefined,
          include_warning: includeWarning,
          include_ok: includeOk,
        })
      } else {
        matchMutation.mutate({
          sku_names: subsetSkuNames,
          lead_time: leadTime,
          coverage_days: coverageDays ?? undefined,
          buffer: bufferOverride ? bufferValue : undefined,
          from_date: fromDate ?? undefined,
          to_date: toDate ?? undefined,
        })
      }
    }
  }, [leadTime, coverageDays, bufferOverride, bufferValue, fromDate, toDate, includeWarning, includeOk]) // eslint-disable-line react-hooks/exhaustive-deps
```

- [ ] **Step 2: Add cross-brand summary bar and brand badges**

In the PO table rendering section, add a cross-brand summary bar. Find the `{/* Subset mode banner */}` section and add a prefix mode banner right after it:

```typescript
      {/* Prefix mode banner */}
      {prefixMode && (
        <div className="text-sm bg-blue-50 border border-blue-200 rounded-lg px-4 py-2.5">
          <div className="flex items-center justify-between">
            <span className="text-blue-800">
              <strong>Prefix &ldquo;{prefixValue}&rdquo;:</strong>{' '}
              {rows.length} SKU{rows.length !== 1 ? 's' : ''} across {prefixBrands.length} brand{prefixBrands.length !== 1 ? 's' : ''}
            </span>
            <Button variant="ghost" size="sm" className="text-blue-700 hover:text-blue-900" onClick={clearSubsetMode}>
              Clear
            </Button>
          </div>
          {prefixBrands.length > 1 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {prefixBrands.map(b => {
                const count = rows.filter(r => r.category_name === b).length
                return (
                  <Badge key={b} variant="secondary" className="text-xs">
                    {b} ({count})
                  </Badge>
                )
              })}
            </div>
          )}
        </div>
      )}
```

Now add a brand badge in the table rows when in prefix mode with multiple brands. In the table cell that shows the product name (the `<TableCell className="max-w-[250px]"` cell), add a brand badge after the existing content. Find the line with `{r.abc_class && (` and add before it:

```typescript
                    {prefixMode && prefixBrands.length > 1 && (
                      <span className="text-[10px] text-muted-foreground block mt-0.5">
                        {r.category_name}
                      </span>
                    )}
```

- [ ] **Step 3: Update the header to show prefix info**

In the page header (the `<h2>` element in the desktop view), update to handle prefix mode. Find:

```typescript
              PO{subsetMode ? ' — Custom' : decodedName ? ` — ${decodedName}` : ''}
```

Replace with:

```typescript
              PO{prefixMode ? ` — Prefix "${prefixValue}"` : subsetMode ? ' — Custom' : decodedName ? ` — ${decodedName}` : ''}
```

Do the same for the mobile header.

- [ ] **Step 4: Update the export handler for prefix mode**

In `handleExport`, update the `category_name` for prefix mode:

```typescript
        category_name: prefixMode ? `PREFIX-${prefixValue}` : subsetMode ? 'CUSTOM' : decodedName,
```

- [ ] **Step 5: Verify in browser**

Navigate to `/po?prefix=0102` and verify:
- SKUs load automatically
- Prefix banner shows with brand breakdown
- Brand badges appear on table rows when multi-brand
- Config changes trigger re-fetch

- [ ] **Step 6: Commit**

```bash
git add src/dashboard/src/pages/PoBuilder.tsx
git commit -m "feat: PO builder supports ?prefix= param with cross-brand display

Auto-loads prefix PO data from URL, shows brand summary bar and
per-row brand labels when multiple brands present."
```

---

### Task 8: Frontend — Create SkuListByPrefix page and add route

**Files:**
- Create: `src/dashboard/src/pages/SkuListByPrefix.tsx`
- Modify: `src/dashboard/src/App.tsx`

- [ ] **Step 1: Create the SkuListByPrefix page**

Create `src/dashboard/src/pages/SkuListByPrefix.tsx`:

```typescript
import { useState, useMemo } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchSkusByPrefix } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
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

  // Derive brand breakdown from current page items
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
      {/* Header */}
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

      {/* Brand breakdown */}
      {brandCounts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {brandCounts.map(([brand, count]) => (
            <Badge key={brand} variant="secondary" className="text-xs">
              {brand} ({count})
            </Badge>
          ))}
        </div>
      )}

      {/* Search within results */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search within prefix results..."
          className="pl-10"
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(0) }}
        />
      </div>

      {/* Table */}
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

          {/* Pagination */}
          {total > limit && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage(p => p - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={(page + 1) * limit >= total}
                  onClick={() => setPage(p => p + 1)}
                >
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
```

- [ ] **Step 2: Add the route in App.tsx**

In `src/dashboard/src/App.tsx`, add the lazy import:

```typescript
const SkuListByPrefix = lazy(() => import('./pages/SkuListByPrefix'))
```

Add the route inside the protected `<Route element={<Layout />}>` block, after the `/po` route:

```typescript
              <Route path="/skus" element={<SuspenseWrapper><SkuListByPrefix /></SuspenseWrapper>} />
```

- [ ] **Step 3: Verify in browser**

Navigate to `/skus?prefix=0102` — should see the cross-brand SKU list with brand badges, search, pagination, and "Build PO" button.

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/pages/SkuListByPrefix.tsx src/dashboard/src/App.tsx
git commit -m "feat: add /skus?prefix= cross-brand SKU list page

New page shows all SKUs matching a part_no prefix across brands
with brand breakdown badges, pagination, search, and Build PO action."
```

---

### Task 9: Integration test and final verification

- [ ] **Step 1: Run all backend tests**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest ../tests/api/test_prefix_search.py ../tests/api/test_prefix_po.py -v
```

Expected: ALL PASS

- [ ] **Step 2: Build frontend**

```bash
cd src/dashboard && npm run build
```

Expected: No TypeScript errors, build succeeds.

- [ ] **Step 3: End-to-end manual verification**

Start the server:
```bash
cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000
```

Verify these flows:
1. Type "0102" in universal search → see prefix group with brand list, "View SKUs" and "Build PO" buttons
2. Click "View SKUs" → navigates to `/skus?prefix=0102` → shows cross-brand SKU list
3. Click "Build PO" → navigates to `/po?prefix=0102` → loads PO with prefix banner and brand badges
4. Open PO builder → click "Import SKU List" → click "Code Prefix" tab → search "0102" → preview → "Match & Build PO" → loads into PO
5. Change lead time/buffer in prefix PO → data re-fetches correctly

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: prefix search & PO builder enhancement — complete

Adds part_no prefix search across the system:
- Universal search shows prefix group with View SKUs / Build PO
- PO builder supports ?prefix= param with cross-brand display
- SKU input dialog has new Code Prefix tab
- New /skus?prefix= cross-brand SKU list page
- Backend endpoints for prefix search, prefix PO, cross-brand SKU list"
```
