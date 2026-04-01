# Field Rename: item_code + display_name — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `stock_item_name` → `item_code` and `part_no` → `display_name` across the entire stack (DB, backend, API, frontend) so field names match their Unicommerce semantics.

**Architecture:** Database migration renames columns in 8 tables. Backend code, API responses, TypeScript types, and React components all update to use the new names. A single `SKU_FIELDS` constant centralizes the mapping for DRY. The prefix search feature (already built) is updated to use `item_code` consistently.

**Tech Stack:** PostgreSQL (ALTER TABLE RENAME), Python/FastAPI, React/TypeScript

**Semantic mapping (from Unicommerce):**

| UC field | Old DB column | New DB column | Old API/TS field | New API/TS field |
|---|---|---|---|---|
| `skuCode` (e.g. "0102004") | `stock_items.name` | `stock_items.item_code` | `stock_item_name` | `item_code` |
| `skuCode` | `*.stock_item_name` (7 tables) | `*.item_code` | `stock_item_name` | `item_code` |
| `name` (e.g. "WN PWC 5ML ALIZ CRIMSON") | `stock_items.part_no` | `stock_items.display_name` | `part_no` | `display_name` |

**Tables affected by `stock_item_name` → `item_code`:**
1. `sku_metrics.stock_item_name`
2. `transactions.stock_item_name`
3. `daily_stock_positions.stock_item_name`
4. `overrides.stock_item_name`
5. `drift_log.stock_item_name`
6. `inventory_snapshots.stock_item_name`
7. `kg_demand.stock_item_name`

**Tables affected by `name` → `item_code` (PK):**
8. `stock_items.name` → `stock_items.item_code`

**Tables affected by `part_no` → `display_name`:**
9. `stock_items.part_no` → `stock_items.display_name`

---

## File Structure

### Database
- **Create:** `src/db/migrations/uc_004_rename_fields.sql` — the migration script

### Backend constants (new, DRY)
- **Create:** `src/constants.py` — `SKU_FIELDS` mapping used by all backend code

### Backend (modify)
- `src/api/routes/search.py` — use SKU_FIELDS, return `item_code`/`display_name`
- `src/api/routes/skus.py` — use SKU_FIELDS, return new field names
- `src/api/routes/po.py` — use SKU_FIELDS, return new field names
- `src/api/routes/brands.py` — update JOIN
- `src/api/sql_fragments.py` — update OVERRIDE_AGG_SUBQUERY
- `src/engine/pipeline.py` — update column references
- `src/engine/classification.py` — update dict key references
- `src/engine/recalculate_buffers.py` — update JOINs
- `src/engine/velocity.py` — check and update column references
- `src/engine/reorder.py` — check and update column references
- `src/unicommerce/catalog.py` — update INSERT to use `item_code`/`display_name`
- All other UC sync files that reference `stock_item_name`

### Frontend
- `src/dashboard/src/lib/types.ts` — rename fields in all interfaces
- `src/dashboard/src/lib/api.ts` — update any field references
- `src/dashboard/src/pages/PoBuilder.tsx` — `item_code`/`display_name`
- `src/dashboard/src/pages/SkuDetail.tsx` — same
- `src/dashboard/src/pages/CriticalSkus.tsx` — same
- `src/dashboard/src/pages/DeadStock.tsx` — same
- `src/dashboard/src/pages/SkuListByPrefix.tsx` — same
- `src/dashboard/src/components/UniversalSearch.tsx` — same
- `src/dashboard/src/components/SkuInputDialog.tsx` — same
- `src/dashboard/src/components/SkuMatchReview.tsx` — same
- `src/dashboard/src/components/mobile/MobileSkuDetail.tsx` — same
- `src/dashboard/src/components/CalculationBreakdown.tsx` — check

### Tests
- `tests/api/test_prefix_search.py` — update field names
- `src/tests/test_search.py` — update field names
- `src/tests/test_skus_pagination.py` — update field names

---

### Task 1: Database migration — rename all columns

**Files:**
- Create: `src/db/migrations/uc_004_rename_fields.sql`

This is the foundation. All other tasks depend on this being run first.

- [ ] **Step 1: Write the migration SQL**

Create `src/db/migrations/uc_004_rename_fields.sql`:

```sql
-- Migration: Rename stock_item_name → item_code, part_no → display_name
--
-- Unicommerce semantics:
--   skuCode (e.g. "0102004") was stored as stock_items.name / *.stock_item_name
--   name (e.g. "WN PWC 5ML ALIZ CRIMSON") was stored as stock_items.part_no
--
-- After this migration:
--   item_code = the SKU code (Unicommerce skuCode)
--   display_name = the human-readable product name (Unicommerce name)

BEGIN;

-- 1. stock_items: rename PK column and part_no
ALTER TABLE stock_items RENAME COLUMN name TO item_code;
ALTER TABLE stock_items RENAME COLUMN part_no TO display_name;

-- 2. sku_metrics
ALTER TABLE sku_metrics RENAME COLUMN stock_item_name TO item_code;

-- 3. transactions
ALTER TABLE transactions RENAME COLUMN stock_item_name TO item_code;

-- 4. daily_stock_positions
ALTER TABLE daily_stock_positions RENAME COLUMN stock_item_name TO item_code;

-- 5. overrides
ALTER TABLE overrides RENAME COLUMN stock_item_name TO item_code;

-- 6. drift_log
ALTER TABLE drift_log RENAME COLUMN stock_item_name TO item_code;

-- 7. inventory_snapshots
ALTER TABLE inventory_snapshots RENAME COLUMN stock_item_name TO item_code;

-- 8. kg_demand
ALTER TABLE kg_demand RENAME COLUMN stock_item_name TO item_code;

COMMIT;
```

Note: PostgreSQL's `ALTER TABLE RENAME COLUMN` automatically updates indexes, unique constraints, and CHECK constraints that reference the column. Foreign key references by column name also update. This is safe and instant (metadata-only, no data rewrite).

- [ ] **Step 2: Run the migration on local DB**

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -f src/db/migrations/uc_004_rename_fields.sql
```

Expected: `BEGIN`, `ALTER TABLE` x8, `COMMIT` — no errors.

- [ ] **Step 3: Verify the rename**

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "
SELECT table_name, column_name FROM information_schema.columns
WHERE column_name IN ('item_code', 'display_name', 'stock_item_name', 'part_no')
  AND table_schema = 'public'
ORDER BY table_name, column_name;
"
```

Expected: All 8 tables show `item_code`, stock_items also shows `display_name`. No `stock_item_name` or `part_no` left.

- [ ] **Step 4: Commit**

```bash
git add src/db/migrations/uc_004_rename_fields.sql
git commit -m "db: rename stock_item_name→item_code, part_no→display_name

Aligns DB column names with Unicommerce semantics:
- skuCode → item_code (was confusingly named stock_item_name/name)
- UC name → display_name (was confusingly named part_no)"
```

---

### Task 2: Create SKU_FIELDS constants (DRY source of truth)

**Files:**
- Create: `src/constants.py`

- [ ] **Step 1: Create the constants file**

Create `src/constants.py`:

```python
"""
Centralized field name constants for SKU data.

Unicommerce provides:
  - skuCode  → stored as `item_code` (the SKU identifier, e.g. "0102004")
  - name     → stored as `display_name` (human-readable, e.g. "WN PWC 5ML ALIZ CRIMSON")

All code should use these constants instead of hardcoding column/field names.
"""


class SKU_FIELDS:
    """Column and API field names for SKU identification."""
    # The SKU code / identifier (Unicommerce skuCode)
    # DB: stock_items.item_code (PK), sku_metrics.item_code, transactions.item_code, etc.
    ITEM_CODE = "item_code"

    # The human-readable product name (Unicommerce name)
    # DB: stock_items.display_name
    DISPLAY_NAME = "display_name"

    # Brand / category grouping
    CATEGORY = "category_name"
```

- [ ] **Step 2: Commit**

```bash
git add src/constants.py
git commit -m "feat: add SKU_FIELDS constants for DRY field name mapping"
```

---

### Task 3: Update Unicommerce catalog sync

**Files:**
- Modify: `src/unicommerce/catalog.py`

- [ ] **Step 1: Update the UPSERT SQL to use new column names**

In `src/unicommerce/catalog.py`, update the `_upsert_items` function. The INSERT references `name` and `part_no` which are now `item_code` and `display_name`.

Change the SQL in `_upsert_items` (around line 117-134):

```python
    sql = """
        INSERT INTO stock_items (item_code, sku_code, display_name, category_name, stock_group, brand,
                                 cost_price, mrp, ean, hsn_code, is_active)
        VALUES (%(sku_code)s, %(sku_code)s, %(display_name)s, %(category_code)s,
                %(product_category)s, %(brand)s, %(cost_price)s, %(mrp)s, %(ean)s,
                %(hsn_code)s, %(enabled)s)
        ON CONFLICT (item_code) DO UPDATE SET
            sku_code = EXCLUDED.sku_code,
            display_name = EXCLUDED.display_name,
            category_name = EXCLUDED.category_name,
            stock_group = EXCLUDED.stock_group,
            brand = EXCLUDED.brand,
            cost_price = EXCLUDED.cost_price,
            mrp = EXCLUDED.mrp,
            ean = EXCLUDED.ean,
            hsn_code = EXCLUDED.hsn_code,
            is_active = EXCLUDED.is_active,
            updated_at = NOW()
    """
```

Also update `get_all_sku_codes` if it references `stock_item_name`.

- [ ] **Step 2: Verify import works**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -c "from unicommerce.catalog import load_catalog; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/unicommerce/catalog.py
git commit -m "fix: update UC catalog sync to use item_code/display_name columns"
```

---

### Task 4: Update all backend SQL — api/sql_fragments, engine, pipeline

**Files:**
- Modify: `src/api/sql_fragments.py`
- Modify: `src/engine/pipeline.py`
- Modify: `src/engine/classification.py`
- Modify: `src/engine/recalculate_buffers.py`
- Modify: `src/engine/velocity.py`
- Modify: `src/engine/reorder.py`
- Modify: any other `src/engine/*.py` or `src/unicommerce/*.py` files that reference `stock_item_name` or `part_no`

This is a bulk find-and-replace task across the engine and shared SQL layer.

- [ ] **Step 1: Update sql_fragments.py**

In `src/api/sql_fragments.py`, replace all `stock_item_name` with `item_code`:
- `SELECT stock_item_name,` → `SELECT item_code,`
- `GROUP BY stock_item_name` → `GROUP BY item_code`
- `ovr.stock_item_name` → `ovr.item_code`

- [ ] **Step 2: Update engine/pipeline.py**

Replace all occurrences:
- `stock_item_name` → `item_code` in SQL strings
- `si.name` → `si.item_code` in JOIN conditions
- `["stock_item_name"]` → `["item_code"]` in Python dict key access
- `part_no` → `display_name` in any SQL or dict references

- [ ] **Step 3: Update engine/classification.py**

Replace `m["stock_item_name"]` → `m["item_code"]` in all dict key access.

- [ ] **Step 4: Update engine/recalculate_buffers.py**

Replace `si.name = m.stock_item_name` → `si.item_code = m.item_code` and similar JOIN patterns.

- [ ] **Step 5: Update engine/velocity.py and engine/reorder.py**

Search for any `stock_item_name` or `part_no` references and replace.

- [ ] **Step 6: Update all unicommerce sync files**

Search `src/unicommerce/*.py` for `stock_item_name` and `part_no` references. Update all.

- [ ] **Step 7: Verify all engine modules import**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -c "
from engine import pipeline, classification, recalculate_buffers, velocity, reorder
from api.sql_fragments import OVERRIDE_AGG_SUBQUERY
print('All engine imports OK')
"
```

- [ ] **Step 8: Commit**

```bash
git add src/api/sql_fragments.py src/engine/ src/unicommerce/
git commit -m "fix: update all engine/pipeline SQL to use item_code/display_name"
```

---

### Task 5: Update API routes — search, skus, po, brands

**Files:**
- Modify: `src/api/routes/search.py`
- Modify: `src/api/routes/skus.py`
- Modify: `src/api/routes/po.py`
- Modify: `src/api/routes/brands.py`
- Modify: any other route files referencing these fields

All SQL queries use `item_code` and `display_name` now. The API response dicts must also return `item_code` and `display_name` instead of `stock_item_name` and `part_no`.

- [ ] **Step 1: Update search.py**

Replace throughout:
- SQL: `sm.stock_item_name` → `sm.item_code`
- SQL: `si.name` → `si.item_code`
- SQL: `si.part_no` → `si.display_name`
- SQL fragments `_SKU_SELECT`: update column names
- SQL fragments `_SKU_MATCH`: update column names
- Comments referencing old names
- Dict keys in response: `"stock_item_name"` → `"item_code"`, `"part_no"` → `"display_name"`

- [ ] **Step 2: Update skus.py**

Same pattern as search.py. This is a large file (~500+ lines) with many SQL queries. Replace all:
- `sm.stock_item_name` → `sm.item_code`
- `si.name = sm.stock_item_name` → `si.item_code = sm.item_code`
- `si.part_no` → `si.display_name`
- `["stock_item_name"]` → `["item_code"]` in Python dict access
- `["part_no"]` → `["display_name"]` in Python dict access

- [ ] **Step 3: Update po.py**

Same pattern. Key areas:
- `_PO_SELECT_COLS`: update column references
- `_PO_FROM_JOINS`: update JOIN condition `si.name = sm.stock_item_name` → `si.item_code = sm.item_code`
- `_compute_po_items`: update dict key references
- `_match_sku_names`: update `si.name` → `si.item_code`
- Response dicts: `"stock_item_name"` → `"item_code"`, `"part_no"` → `"display_name"`
- `PoItem` model: `stock_item_name` → `item_code`, `part_no` → `display_name`
- `PoExportRequest`: same
- Excel export: update column references

- [ ] **Step 4: Update brands.py**

Update the JOIN: `si.name = sm.stock_item_name` → `si.item_code = sm.item_code`

- [ ] **Step 5: Update any other route files**

Check `src/api/routes/` for any other files referencing `stock_item_name` or `part_no` (e.g., overrides routes, settings routes).

- [ ] **Step 6: Verify all API routes import**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -c "
from api.main import app
print('API app OK, routes:', len(app.routes))
"
```

- [ ] **Step 7: Commit**

```bash
git add src/api/
git commit -m "fix: update all API routes to use item_code/display_name"
```

---

### Task 6: Update frontend types and API functions

**Files:**
- Modify: `src/dashboard/src/lib/types.ts`
- Modify: `src/dashboard/src/lib/api.ts`

- [ ] **Step 1: Update types.ts**

Replace across all interfaces:
- `stock_item_name: string` → `item_code: string`
- `part_no: string | null` → `display_name: string | null`

Affected interfaces: `SkuMetrics`, `PoDataItem`, `SkuMatchResult`, `CriticalItem`, `SearchSkuResult`, `BreakdownResponse`, and any others.

- [ ] **Step 2: Update api.ts**

Update any field references in API function parameters or response handling.

- [ ] **Step 3: TypeScript check**

```bash
cd src/dashboard && npx tsc --noEmit
```

This will show ALL frontend files that need updating (TypeScript will flag every reference to the old field names). Use the error list as a checklist for Task 7.

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/lib/types.ts src/dashboard/src/lib/api.ts
git commit -m "fix: update frontend types — item_code/display_name"
```

---

### Task 7: Update all frontend components

**Files:**
- Modify: All `.tsx` files that reference `stock_item_name` or `part_no`

Use the TypeScript errors from Task 6 Step 3 as the definitive list. Key files:

- `src/dashboard/src/pages/PoBuilder.tsx`
- `src/dashboard/src/pages/SkuDetail.tsx`
- `src/dashboard/src/pages/CriticalSkus.tsx`
- `src/dashboard/src/pages/DeadStock.tsx`
- `src/dashboard/src/pages/SkuListByPrefix.tsx`
- `src/dashboard/src/components/UniversalSearch.tsx`
- `src/dashboard/src/components/SkuInputDialog.tsx`
- `src/dashboard/src/components/SkuMatchReview.tsx`
- `src/dashboard/src/components/CalculationBreakdown.tsx`
- `src/dashboard/src/components/mobile/MobileSkuDetail.tsx`
- Any other components flagged by TypeScript

- [ ] **Step 1: Bulk replace across all component files**

In every `.tsx` file:
- `.stock_item_name` → `.item_code`
- `.part_no` → `.display_name`
- `stock_item_name:` (in type literals) → `item_code:`
- `part_no:` (in type literals) → `display_name:`

Also update the PoBuilder local `PoRow` interface to use the new names.

- [ ] **Step 2: TypeScript check — zero errors**

```bash
cd src/dashboard && npx tsc --noEmit
```

Expected: Zero errors.

- [ ] **Step 3: Build**

```bash
cd src/dashboard && npm run build
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/
git commit -m "fix: update all frontend components — item_code/display_name"
```

---

### Task 8: Update tests

**Files:**
- Modify: `tests/api/test_prefix_search.py`
- Modify: `src/tests/test_search.py`
- Modify: `src/tests/test_skus_pagination.py`

- [ ] **Step 1: Update test_prefix_search.py**

Replace all mock data and assertions:
- `"stock_item_name"` → `"item_code"`
- `"part_no"` → `"display_name"`
- `stock_item_name=` → `item_code=` in `_make_row` calls

- [ ] **Step 2: Update test_search.py**

Replace `"part_no"` → `"display_name"` in assertions and mock data.

- [ ] **Step 3: Update test_skus_pagination.py**

Replace `"part_no"` → `"display_name"` in mock data.

- [ ] **Step 4: Run all tests**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -m pytest ../tests/ tests/ -v
```

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/ src/tests/
git commit -m "fix: update all tests — item_code/display_name"
```

---

### Task 9: Fix the prefix search to use item_code correctly

Now that the fields are properly named, update the prefix search to use `item_code` — which is what it semantically should match on.

**Files:**
- Modify: `src/api/routes/search.py` (should already be correct from Task 5)
- Modify: `src/api/routes/po.py` (should already be correct from Task 5)
- Modify: `src/api/routes/skus.py` (should already be correct from Task 5)

- [ ] **Step 1: Verify prefix search queries use item_code**

After the Task 5 rename, the prefix queries should already read `sm.item_code ILIKE ...`. Verify this is the case in all three files. If any still reference `stock_item_name`, fix them.

- [ ] **Step 2: Test prefix search against live data**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/python -c "
from api.database import get_db
with get_db() as conn:
    with conn.cursor() as cur:
        cur.execute(\"SELECT COUNT(*) AS cnt FROM sku_metrics WHERE item_code ILIKE '0102%'\")
        print('Prefix 0102 matches:', cur.fetchone()['cnt'])
"
```

Expected: ~117 matches.

- [ ] **Step 3: Commit (if any fixes needed)**

```bash
git add src/api/routes/
git commit -m "fix: verify prefix search uses item_code after rename"
```

---

### Task 10: Run Railway migration + deploy

- [ ] **Step 1: Run the migration on Railway**

```bash
# Get Railway DB connection string from environment
railway run -- psql -f src/db/migrations/uc_004_rename_fields.sql
```

Or use the sync script approach:
```bash
PGPASSWORD=<railway_password> psql -h <railway_host> -U <railway_user> -d <railway_db> -f src/db/migrations/uc_004_rename_fields.sql
```

- [ ] **Step 2: Push to trigger deploy**

```bash
git push origin main
```

- [ ] **Step 3: Verify Railway deploy succeeds**

```bash
railway deployment list --limit 3
```

- [ ] **Step 4: Verify the live application works**

Test on https://reorder.artlounge.in:
1. Search "0102" → should show prefix match group
2. Click "Build PO" → should load PO with correct data
3. Browse brands → SKU list should show correctly
4. API response should use `item_code` and `display_name` field names

---

### Task 11: Update schema documentation and CLAUDE.md

- [ ] **Step 1: Update the UC schema file**

Update `src/db/migrations/uc_001_schema.sql` comments to reflect the new column names (for reference — this file isn't re-run, but documents the intended schema).

- [ ] **Step 2: Update CLAUDE.md**

Add a note about the field naming convention:
```
## SKU Field Names
- `item_code` = the SKU code from Unicommerce (skuCode). Used as PK across all tables.
- `display_name` = the human-readable product name from Unicommerce (name).
- Do NOT use `stock_item_name` or `part_no` — these were renamed in uc_004.
```

- [ ] **Step 3: Update memory**

Update the project memory to reflect the rename.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md src/db/migrations/uc_001_schema.sql
git commit -m "docs: update schema docs and CLAUDE.md for field rename"
```
