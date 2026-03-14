# Subset PO Builder — Paste / Upload SKU List

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users build a Purchase Order from a pasted list of SKU names or an uploaded Excel/CSV file, instead of only from the full brand catalog.

**Architecture:** New backend endpoint accepts a JSON list of SKU name strings, fuzzy-matches them against `stock_items.tally_name` using PostgreSQL `pg_trgm`, and returns PO data for matched items. All file parsing (Excel, CSV) happens **client-side** via SheetJS — the backend only receives clean string arrays. The frontend adds a modal dialog with paste/upload tabs, a match-review step for fuzzy/unmatched items, then feeds confirmed matches into the existing PO Builder table. All existing PO features (overrides, hazardous warnings, export) work unchanged.

**Tech Stack:**
- Backend: Python/FastAPI, PostgreSQL (`pg_trgm` for fuzzy matching)
- Frontend: React + TypeScript, SheetJS (`xlsx` npm package) for Excel/CSV parsing, base-ui Dialog + shadcn Tabs

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/db/migration_v4_trgm.sql` | Create | pg_trgm extension + trigram index |
| `src/api/routes/po.py` | Modify | Extract `_compute_po_items` helper, add `POST /po-data/match` |
| `src/dashboard/src/components/ui/dialog.tsx` | Create | Dialog component using `@base-ui/react/dialog` |
| `src/dashboard/src/lib/sku-parser.ts` | Create | Parse paste text / Excel / CSV into SKU name list |
| `src/dashboard/src/lib/types.ts` | Modify | Add `SkuMatchResult`, `SkuMatchResponse`, extend `PoDataItem` |
| `src/dashboard/src/lib/api.ts` | Modify | Add `matchSkusForPo` API function |
| `src/dashboard/src/components/SkuInputDialog.tsx` | Create | Modal with paste textarea + file upload tabs |
| `src/dashboard/src/components/SkuMatchReview.tsx` | Create | Review table for fuzzy/unmatched SKUs |
| `src/dashboard/src/pages/PoBuilder.tsx` | Modify | Add "Import SKU List" button, subset mode, standalone /po route |
| `src/dashboard/src/App.tsx` | Modify | Add `/po` route |
| `src/dashboard/src/components/Layout.tsx` | Modify | Add "Build PO" nav link |
| `src/dashboard/package.json` | Modify | Add `xlsx` dependency |

---

## Chunk 1: Backend — Database + Shared Helper + Match Endpoint

### Task 1: Enable pg_trgm Extension and Create Index

**Files:**
- Create: `src/db/migration_v4_trgm.sql`

- [ ] **Step 1: Enable extension (requires superuser)**

Run:
```bash
PGPASSWORD=admin "/c/Program Files/PostgreSQL/17/bin/psql" -U postgres -d artlounge_reorder -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

- [ ] **Step 2: Create trigram index**

Run:
```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "CREATE INDEX IF NOT EXISTS idx_stock_items_tally_name_trgm ON stock_items USING gin (tally_name gin_trgm_ops);"
```

- [ ] **Step 3: Verify fuzzy matching works**

Run:
```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "SELECT tally_name, similarity(tally_name, 'Cotman Watercolour 8ml') AS sim FROM stock_items WHERE similarity(tally_name, 'Cotman Watercolour 8ml') >= 0.25 ORDER BY sim DESC LIMIT 5;"
```

Expected: Returns fuzzy matches for Winsor & Newton Cotman items.

- [ ] **Step 4: Save migration file**

Create `src/db/migration_v4_trgm.sql`:
```sql
-- Run as superuser (postgres):
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Run as reorder_app:
CREATE INDEX IF NOT EXISTS idx_stock_items_tally_name_trgm
  ON stock_items USING gin (tally_name gin_trgm_ops);
```

- [ ] **Step 5: Commit**

```bash
git add src/db/migration_v4_trgm.sql
git commit -m "feat: add pg_trgm extension and trigram index for fuzzy SKU matching"
```

---

### Task 2: Extract Shared PO Computation Helper

Before adding the new endpoint, extract the duplicated PO item computation into a reusable helper. This keeps both the existing `po_data` endpoint and the new `match_and_build_po` endpoint DRY from the start.

**Files:**
- Modify: `src/api/routes/po.py`

- [ ] **Step 1: Add the helper function**

Add before the `po_data` endpoint in `src/api/routes/po.py`:

```python
def _compute_po_items(
    rows: list[dict],
    lead_time: int,
    buffer: float | None,
    vel_by_sku: dict,
) -> list[dict]:
    """Shared PO item computation used by both brand and subset endpoints."""
    result = []
    for r in rows:
        d = dict(r)
        if d["hold_from_po"] or d.get("reorder_intent") == "do_not_reorder":
            continue

        if vel_by_sku:
            base_wholesale, base_online, _, base_total = velocities_from_batch_row(
                vel_by_sku.get(d["stock_item_name"])
            )
        else:
            base_wholesale = float(d["wholesale_velocity"] or 0)
            base_online = float(d["online_velocity"] or 0)
            base_total = float(d["total_velocity"] or 0)

        vals = compute_effective_values(
            float(d["current_stock"] or 0),
            base_wholesale, base_online, base_total,
            stock_ovr=opt_float(d["stock_override"]),
            wholesale_ovr=opt_float(d["wholesale_vel_override"]),
            online_ovr=opt_float(d["online_vel_override"]),
            store_ovr=opt_float(d.get("store_vel_override")),
            total_ovr=opt_float(d["total_vel_override"]),
        )
        st = compute_effective_status(vals["eff_stock"], vals["eff_total"], lead_time)

        sku_buffer = float(d.get("safety_buffer") or 1.3)
        effective_buffer = buffer if buffer is not None else sku_buffer
        if vals["eff_total"] > 0:
            raw_need = vals["eff_total"] * lead_time * effective_buffer
            suggested = max(0, round(raw_need - max(0, vals["eff_stock"])))
            if suggested == 0:
                suggested = None
        elif d.get("reorder_intent") == "must_stock":
            suggested = must_stock_fallback_qty(lead_time)
        else:
            suggested = None

        item = {
            "stock_item_name": d["stock_item_name"],
            "part_no": d.get("part_no"),
            "current_stock": vals["eff_stock"],
            "total_velocity": vals["eff_total"],
            "days_to_stockout": st["eff_days"],
            "reorder_status": st["eff_status"],
            "suggested_qty": suggested,
            "lead_time": lead_time,
            "buffer": effective_buffer,
            "sku_buffer": sku_buffer,
            "has_override": vals["has_stock_override"] or vals["has_velocity_override"],
            "is_hazardous": d.get("is_hazardous") or False,
            "reorder_intent": d.get("reorder_intent", "normal"),
            "abc_class": d.get("abc_class"),
            "trend_direction": d.get("trend_direction"),
        }
        if "category_name" in d:
            item["category_name"] = d["category_name"]
        result.append(item)
    return result
```

- [ ] **Step 2: Replace the existing po_data computation loop**

In the `po_data` endpoint, replace the entire `result = []` block (from `result = []` through the final `result.append(...)`) with:

```python
    result = _compute_po_items(rows, lead_time, buffer, vel_by_sku)
```

- [ ] **Step 3: Verify existing endpoint still works**

Run:
```bash
cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src" && PYTHONPATH=. ./venv/Scripts/python -c "from api.routes.po import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/po.py
git commit -m "refactor: extract _compute_po_items helper for shared PO computation"
```

---

### Task 3: Add POST /po-data/match Endpoint

The core backend endpoint. Accepts a JSON list of SKU name strings, matches each against `stock_items`, returns PO data for all matched items using the shared helper.

**Matching strategy (per input string):**
1. **Exact match** — `tally_name = input` (case-sensitive)
2. **Case-insensitive match** — `LOWER(tally_name) = LOWER(input)`
3. **Batched trigram fuzzy match** — single SQL query using `unnest()` for all remaining names, threshold ≥ 0.25

**Files:**
- Modify: `src/api/routes/po.py`

- [ ] **Step 1: Add Pydantic models**

Add after the existing `PoExportRequest` class:

```python
class SkuMatchRequest(BaseModel):
    sku_names: list[str]
    lead_time: int | None = None
    buffer: float | None = None
    from_date: str | None = None
    to_date: str | None = None


class MatchedSku(BaseModel):
    input_name: str
    matched_name: str | None = None
    match_type: str  # "exact", "fuzzy", "unmatched"
    similarity: float | None = None
```

- [ ] **Step 2: Add the matching helper function**

```python
def _match_sku_names(cur, input_names: list[str]) -> list[MatchedSku]:
    """Match input SKU names against stock_items: exact -> ilike -> trigram (batched)."""
    if not input_names:
        return []

    # Pre-fetch all tally_names for exact/ilike matching
    cur.execute("SELECT tally_name FROM stock_items")
    all_names = {row["tally_name"] for row in cur.fetchall()}
    all_names_lower = {n.lower(): n for n in all_names}

    results: list[MatchedSku] = []
    unmatched_inputs: list[str] = []

    for raw in input_names:
        name = raw.strip()
        if not name:
            continue
        # 1. Exact match
        if name in all_names:
            results.append(MatchedSku(
                input_name=name, matched_name=name,
                match_type="exact", similarity=1.0,
            ))
            continue
        # 2. Case-insensitive match
        lower = name.lower()
        if lower in all_names_lower:
            results.append(MatchedSku(
                input_name=name, matched_name=all_names_lower[lower],
                match_type="exact", similarity=1.0,
            ))
            continue
        unmatched_inputs.append(name)

    # 3. Batched trigram fuzzy match for remaining
    if unmatched_inputs:
        cur.execute("""
            SELECT DISTINCT ON (input.name)
                   input.name AS input_name,
                   si.tally_name,
                   similarity(si.tally_name, input.name) AS sim
            FROM unnest(%s::text[]) AS input(name)
            LEFT JOIN stock_items si
              ON similarity(si.tally_name, input.name) >= 0.25
            ORDER BY input.name, sim DESC NULLS LAST
        """, (unmatched_inputs,))

        for row in cur.fetchall():
            if row["tally_name"]:
                results.append(MatchedSku(
                    input_name=row["input_name"],
                    matched_name=row["tally_name"],
                    match_type="fuzzy",
                    similarity=round(float(row["sim"]), 3),
                ))
            else:
                results.append(MatchedSku(
                    input_name=row["input_name"],
                    matched_name=None,
                    match_type="unmatched",
                    similarity=None,
                ))

    return results
```

Key improvements over naive approach:
- Uses `unnest()` to batch all fuzzy matches into a single SQL query (vs N individual queries)
- Uses `WHERE similarity() >= 0.25` instead of `SET pg_trgm.similarity_threshold` (avoids session-level side effects)
- `LEFT JOIN` ensures unmatched inputs still appear in results
- `DISTINCT ON` picks the best match per input name

- [ ] **Step 3: Add the endpoint**

```python
@router.post("/po-data/match")
def match_and_build_po(req: SkuMatchRequest):
    """Match SKU names and return PO data for matched items."""
    # Cap input size
    if len(req.sku_names) > 500:
        from fastapi import HTTPException
        raise HTTPException(400, f"Too many SKU names ({len(req.sku_names)}). Maximum is 500.")

    if not req.sku_names:
        return {"matches": [], "po_data": [], "summary": {
            "total_input": 0, "exact": 0, "fuzzy": 0, "unmatched": 0,
        }}

    custom_range = req.from_date is not None or req.to_date is not None

    with get_db() as conn:
        with conn.cursor() as cur:
            # Step 1: Match names
            matches = _match_sku_names(cur, req.sku_names)
            matched_names = [m.matched_name for m in matches if m.matched_name]

            if not matched_names:
                summary = {
                    "total_input": len(matches),
                    "exact": 0, "fuzzy": 0,
                    "unmatched": len(matches),
                }
                return {"matches": [m.model_dump() for m in matches], "po_data": [], "summary": summary}

            # Step 2: Resolve lead time from first matched item's brand
            lead_time = req.lead_time
            if lead_time is None:
                cur.execute("""
                    SELECT bm.supplier_lead_time
                    FROM stock_items si
                    JOIN brand_metrics bm ON bm.category_name = si.category_name
                    WHERE si.tally_name = %s
                """, (matched_names[0],))
                row = cur.fetchone()
                lead_time = row["supplier_lead_time"] if row and row["supplier_lead_time"] else 180

            # Step 3: Fetch PO data for matched SKUs (cross-brand)
            placeholders = ",".join(["%s"] * len(matched_names))
            cur.execute(f"""
                SELECT sm.stock_item_name, sm.current_stock, sm.total_velocity,
                       sm.wholesale_velocity, sm.online_velocity,
                       sm.days_to_stockout, sm.reorder_status,
                       sm.abc_class, sm.trend_direction, sm.safety_buffer,
                       si.part_no, si.is_hazardous, si.reorder_intent,
                       si.category_name,
                       ovr.stock_override_value AS stock_override,
                       ovr.total_vel_override_value AS total_vel_override,
                       ovr.wholesale_vel_override_value AS wholesale_vel_override,
                       ovr.online_vel_override_value AS online_vel_override,
                       ovr.store_vel_override_value AS store_vel_override,
                       COALESCE(ovr.stock_hold_from_po, ovr.total_vel_hold,
                                ovr.wholesale_vel_hold, ovr.online_vel_hold,
                                ovr.store_vel_hold, FALSE) AS hold_from_po
                FROM sku_metrics sm
                LEFT JOIN stock_items si ON si.tally_name = sm.stock_item_name
                LEFT JOIN {OVERRIDE_AGG_SUBQUERY} ovr ON ovr.stock_item_name = sm.stock_item_name
                WHERE sm.stock_item_name IN ({placeholders})
                ORDER BY sm.days_to_stockout ASC NULLS LAST
            """, matched_names)
            rows = cur.fetchall()

            # Batch velocity recalculation when custom date range is active
            vel_by_sku = {}
            if custom_range:
                range_start, range_end = resolve_date_range(req.from_date, req.to_date)
                sku_names_list = [r["stock_item_name"] for r in rows]
                vel_by_sku = fetch_batch_velocities(cur, sku_names_list, range_start, range_end)

    # Step 4: Compute PO data using shared helper
    po_result = _compute_po_items(rows, lead_time, req.buffer, vel_by_sku)

    summary = {
        "total_input": len(matches),
        "exact": sum(1 for m in matches if m.match_type == "exact"),
        "fuzzy": sum(1 for m in matches if m.match_type == "fuzzy"),
        "unmatched": sum(1 for m in matches if m.match_type == "unmatched"),
    }

    return {
        "matches": [m.model_dump() for m in matches],
        "po_data": po_result,
        "summary": summary,
    }
```

- [ ] **Step 4: Verify the endpoint starts**

Run:
```bash
cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src" && PYTHONPATH=. ./venv/Scripts/python -c "from api.routes.po import router; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/po.py
git commit -m "feat: add POST /po-data/match endpoint with batched fuzzy SKU matching"
```

---

## Chunk 2: Frontend — Dependencies + Parser + Types

### Task 4: Install xlsx Package

**Files:**
- Modify: `src/dashboard/package.json`

- [ ] **Step 1: Install**

Run:
```bash
cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src/dashboard" && npm install xlsx
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/package.json src/dashboard/package-lock.json
git commit -m "chore: add xlsx (SheetJS) for client-side Excel/CSV parsing"
```

---

### Task 5: Create sku-parser.ts

Handles all three input formats — pasted text, Excel files, and CSV files — normalizing them into a flat `string[]` of SKU names.

**Files:**
- Create: `src/dashboard/src/lib/sku-parser.ts`

- [ ] **Step 1: Create the parser module**

```typescript
import { read, utils } from 'xlsx'

/**
 * Parse pasted text into SKU names.
 *
 * Handles:
 * - One SKU per line (newline-separated)
 * - Tab-separated (pasted from Excel column)
 *
 * Strips empty lines, trims whitespace, deduplicates.
 */
export function parsePastedText(text: string): string[] {
  const lines = text.split(/\r?\n/)
  const names: string[] = []

  for (const line of lines) {
    // If line has tabs (Excel paste), split by tab and take each cell
    if (line.includes('\t')) {
      for (const cell of line.split('\t')) {
        const trimmed = cell.trim()
        if (trimmed) names.push(trimmed)
      }
    } else {
      const trimmed = line.trim()
      if (trimmed) names.push(trimmed)
    }
  }

  return dedupe(names)
}

/**
 * Parse an Excel (.xlsx/.xls) or CSV file into SKU names.
 *
 * Strategy:
 * 1. Read the first sheet
 * 2. Look for a header row containing a SKU-like column name
 * 3. If found, extract that column's values
 * 4. If not found, take the first column's values (skip header if it looks like one)
 */
export async function parseFile(file: File): Promise<string[]> {
  const buffer = await file.arrayBuffer()
  const workbook = read(buffer, { type: 'array' })

  const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
  if (!firstSheet) return []

  const rows: string[][] = utils.sheet_to_json(firstSheet, { header: 1 })
  if (rows.length === 0) return []

  // Find the SKU column by header name
  const headerRow = rows[0]
  const skuColumnPatterns = [
    /^sku$/i,
    /^sku.?name$/i,
    /^stock.?item/i,
    /^item.?name$/i,
    /^product.?name$/i,
    /^name$/i,
    /^description$/i,
    /^tally.?name$/i,
    /^part.?no/i,
    /^item$/i,
  ]

  let skuColIndex = -1
  if (headerRow) {
    for (let col = 0; col < headerRow.length; col++) {
      const header = String(headerRow[col] ?? '').trim()
      if (skuColumnPatterns.some(p => p.test(header))) {
        skuColIndex = col
        break
      }
    }
  }

  const names: string[] = []
  const colIdx = skuColIndex >= 0 ? skuColIndex : 0

  // Skip first row if we identified it as a header
  const firstCell = String(rows[0]?.[colIdx] ?? '').trim().toLowerCase()
  const looksLikeHeader = skuColIndex >= 0 || skuColumnPatterns.some(p => p.test(firstCell))
  const startRow = looksLikeHeader ? 1 : 0

  for (let i = startRow; i < rows.length; i++) {
    const val = String(rows[i]?.[colIdx] ?? '').trim()
    if (val && val.toLowerCase() !== 'null' && val !== '0') {
      names.push(val)
    }
  }

  return dedupe(names)
}

function dedupe(names: string[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const name of names) {
    const key = name.toLowerCase()
    if (!seen.has(key)) {
      seen.add(key)
      result.push(name)
    }
  }
  return result
}
```

- [ ] **Step 2: Verify build**

Run: `cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src/dashboard" && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/lib/sku-parser.ts
git commit -m "feat: add sku-parser module for paste, Excel, and CSV input parsing"
```

---

### Task 6: Add Types and API Function

**Files:**
- Modify: `src/dashboard/src/lib/types.ts`
- Modify: `src/dashboard/src/lib/api.ts`

- [ ] **Step 1: Extend PoDataItem and add new types in types.ts**

Add `category_name` to the existing `PoDataItem` interface:
```typescript
// In PoDataItem, add after trend_direction:
  category_name?: string
```

Add at the end of `src/dashboard/src/lib/types.ts`:
```typescript
export interface SkuMatchResult {
  input_name: string
  matched_name: string | null
  match_type: 'exact' | 'fuzzy' | 'unmatched'
  similarity: number | null
}

export interface SkuMatchSummary {
  total_input: number
  exact: number
  fuzzy: number
  unmatched: number
}

export interface SkuMatchResponse {
  matches: SkuMatchResult[]
  po_data: PoDataItem[]
  summary: SkuMatchSummary
}
```

- [ ] **Step 2: Add API function to api.ts**

Add `SkuMatchResponse` to the existing `import type { ... } from './types'` line.

Then add the function:
```typescript
export const matchSkusForPo = (data: {
  sku_names: string[]
  lead_time?: number
  buffer?: number
  from_date?: string
  to_date?: string
}): Promise<SkuMatchResponse> =>
  api.post('/api/po-data/match', data).then(r => r.data)
```

- [ ] **Step 3: Verify build**

Run: `cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src/dashboard" && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/lib/types.ts src/dashboard/src/lib/api.ts
git commit -m "feat: add SkuMatchResponse types and matchSkusForPo API function"
```

---

## Chunk 3: Frontend — UI Components

### Task 7: Create Dialog Component

The project uses `@base-ui/react/dialog` (same primitive as the Sheet component), but has no `dialog.tsx` wrapper. We need to create one following the same pattern as `sheet.tsx`.

**Files:**
- Create: `src/dashboard/src/components/ui/dialog.tsx`

- [ ] **Step 1: Create the dialog component**

Model it on `src/dashboard/src/components/ui/sheet.tsx` which uses `Dialog as SheetPrimitive` from `@base-ui/react/dialog`. The dialog version centers content instead of sliding from a side.

```tsx
import * as React from "react"
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { XIcon } from "lucide-react"

function Dialog({ ...props }: DialogPrimitive.Root.Props) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({ ...props }: DialogPrimitive.Trigger.Props) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogClose({ ...props }: DialogPrimitive.Close.Props) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogPortal({ ...props }: DialogPrimitive.Portal.Props) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogOverlay({ className, ...props }: DialogPrimitive.Backdrop.Props) {
  return (
    <DialogPrimitive.Backdrop
      data-slot="dialog-overlay"
      className={cn(
        "fixed inset-0 z-50 bg-black/50 transition-opacity duration-150 data-ending-style:opacity-0 data-starting-style:opacity-0",
        className
      )}
      {...props}
    />
  )
}

function DialogContent({
  className,
  children,
  showCloseButton = true,
  ...props
}: DialogPrimitive.Popup.Props & { showCloseButton?: boolean }) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Popup
        data-slot="dialog-content"
        className={cn(
          "fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-background p-6 shadow-lg transition duration-200 data-ending-style:opacity-0 data-ending-style:scale-95 data-starting-style:opacity-0 data-starting-style:scale-95",
          className
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <DialogPrimitive.Close
            data-slot="dialog-close"
            render={
              <Button
                variant="ghost"
                className="absolute top-3 right-3"
                size="icon-sm"
              />
            }
          >
            <XIcon />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Popup>
    </DialogPortal>
  )
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex flex-col gap-1.5 text-center sm:text-left", className)}
      {...props}
    />
  )
}

function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn("flex flex-col-reverse gap-2 sm:flex-row sm:justify-end", className)}
      {...props}
    />
  )
}

function DialogTitle({ className, ...props }: DialogPrimitive.Title.Props) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-lg font-semibold leading-none", className)}
      {...props}
    />
  )
}

function DialogDescription({ className, ...props }: DialogPrimitive.Description.Props) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogTrigger,
  DialogClose,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
}
```

- [ ] **Step 2: Verify build**

Run: `cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src/dashboard" && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/ui/dialog.tsx
git commit -m "feat: add Dialog component using base-ui Dialog primitive"
```

---

### Task 8: Create SkuInputDialog Component

Modal dialog with two tabs — "Paste" and "Upload" — that collects SKU names.

**Files:**
- Create: `src/dashboard/src/components/SkuInputDialog.tsx`

- [ ] **Step 1: Create the component**

```tsx
import { useState, useCallback, useRef } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { ClipboardPaste, Upload, FileSpreadsheet, X, Loader2 } from 'lucide-react'
import { parsePastedText, parseFile } from '@/lib/sku-parser'

interface SkuInputDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (skuNames: string[]) => void
  isLoading?: boolean
}

export default function SkuInputDialog({ open, onOpenChange, onSubmit, isLoading }: SkuInputDialogProps) {
  const [pasteText, setPasteText] = useState('')
  const [parsedNames, setParsedNames] = useState<string[]>([])
  const [fileName, setFileName] = useState<string | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handlePasteChange = (text: string) => {
    setPasteText(text)
    setParsedNames(parsePastedText(text))
    setFileName(null)
    setFileError(null)
  }

  const handleFile = useCallback(async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !['xlsx', 'xls', 'csv'].includes(ext)) {
      setFileError('Unsupported file type. Use .xlsx, .xls, or .csv')
      return
    }
    try {
      setFileError(null)
      setFileName(file.name)
      const names = await parseFile(file)
      setParsedNames(names)
      setPasteText('')
    } catch {
      setFileError('Failed to parse file. Make sure it is a valid Excel or CSV file.')
      setFileName(null)
      setParsedNames([])
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const handleSubmit = () => {
    if (parsedNames.length > 0) {
      onSubmit(parsedNames)
    }
  }

  const handleClose = () => {
    setPasteText('')
    setParsedNames([])
    setFileName(null)
    setFileError(null)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Import SKU List</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="paste">
          <TabsList className="w-full">
            <TabsTrigger value="paste" className="flex-1 gap-1.5">
              <ClipboardPaste className="h-3.5 w-3.5" /> Paste
            </TabsTrigger>
            <TabsTrigger value="upload" className="flex-1 gap-1.5">
              <Upload className="h-3.5 w-3.5" /> Upload File
            </TabsTrigger>
          </TabsList>

          <TabsContent value="paste" className="mt-3">
            <textarea
              className="w-full h-48 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none font-mono"
              placeholder={"Paste SKU names, one per line:\n\nWN COTMAN WATERCOLOUR 8ML CADMIUM RED\nSennelier L Aquarelle 10Ml Sennelier Red\nHolbein AWC Scarlet Lake B 5ml\n\nOr paste a column from Excel (tab-separated)"}
              value={pasteText}
              onChange={e => handlePasteChange(e.target.value)}
            />
          </TabsContent>

          <TabsContent value="upload" className="mt-3">
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                dragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/25'
              }`}
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              {fileName ? (
                <div className="space-y-2">
                  <FileSpreadsheet className="h-8 w-8 mx-auto text-green-600" />
                  <p className="text-sm font-medium">{fileName}</p>
                  <Button variant="ghost" size="sm" onClick={() => { setFileName(null); setParsedNames([]); setFileError(null) }}>
                    <X className="h-3 w-3 mr-1" /> Remove
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <Upload className="h-8 w-8 mx-auto text-muted-foreground" />
                  <div>
                    <p className="text-sm text-muted-foreground">
                      Drag & drop an Excel or CSV file here
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Supports .xlsx, .xls, .csv
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                    Browse Files
                  </Button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    className="hidden"
                    onChange={handleFileInput}
                  />
                </div>
              )}
            </div>
            {fileError && (
              <p className="text-sm text-red-600 mt-2">{fileError}</p>
            )}
          </TabsContent>
        </Tabs>

        {/* Preview count */}
        {parsedNames.length > 0 && (
          <div className="text-sm text-muted-foreground bg-muted/50 rounded px-3 py-2 border">
            <strong className="text-foreground">{parsedNames.length}</strong> unique SKU name{parsedNames.length !== 1 ? 's' : ''} detected
            {parsedNames.length > 500 && (
              <p className="text-red-600 text-xs mt-1">Maximum 500 SKUs. Only the first 500 will be submitted.</p>
            )}
            {parsedNames.length <= 5 && (
              <ul className="mt-1 text-xs space-y-0.5">
                {parsedNames.map((n, i) => <li key={i} className="truncate">• {n}</li>)}
              </ul>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={parsedNames.length === 0 || isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
            Match & Build PO
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src/dashboard" && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/SkuInputDialog.tsx
git commit -m "feat: add SkuInputDialog with paste and file upload tabs"
```

---

### Task 9: Create SkuMatchReview Component

Shows which SKUs matched exactly, which were fuzzy, and which failed — so users can confirm before proceeding.

**Files:**
- Create: `src/dashboard/src/components/SkuMatchReview.tsx`

- [ ] **Step 1: Create the component**

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Check, HelpCircle, X, ArrowRight } from 'lucide-react'
import type { SkuMatchResult, SkuMatchSummary } from '@/lib/types'

interface SkuMatchReviewProps {
  matches: SkuMatchResult[]
  summary: SkuMatchSummary
  onConfirm: (acceptedNames: string[]) => void
  onBack: () => void
}

export default function SkuMatchReview({ matches, summary, onConfirm, onBack }: SkuMatchReviewProps) {
  const handleConfirm = () => {
    const accepted = matches
      .filter(m => m.matched_name)
      .map(m => m.matched_name!)
    onConfirm(accepted)
  }

  const matchedCount = summary.exact + summary.fuzzy

  return (
    <div className="space-y-4">
      {/* Summary badges */}
      <div className="flex gap-3">
        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
          <Check className="h-3 w-3 mr-1" /> {summary.exact} exact
        </Badge>
        {summary.fuzzy > 0 && (
          <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
            <HelpCircle className="h-3 w-3 mr-1" /> {summary.fuzzy} fuzzy
          </Badge>
        )}
        {summary.unmatched > 0 && (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
            <X className="h-3 w-3 mr-1" /> {summary.unmatched} unmatched
          </Badge>
        )}
      </div>

      {summary.unmatched > 0 && (
        <Alert className="border-amber-200 bg-amber-50">
          <AlertDescription className="text-amber-800 text-sm">
            {summary.unmatched} SKU{summary.unmatched !== 1 ? 's' : ''} could not be matched.
            Unmatched items will be skipped. Check spelling or use exact Tally names.
          </AlertDescription>
        </Alert>
      )}

      {/* Match table — only show fuzzy and unmatched rows */}
      {(summary.fuzzy > 0 || summary.unmatched > 0) && (
        <div className="border rounded-lg max-h-64 overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Your Input</TableHead>
                <TableHead className="w-10"></TableHead>
                <TableHead>Matched To</TableHead>
                <TableHead className="w-20">Match</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {matches
                .filter(m => m.match_type !== 'exact')
                .map((m, i) => (
                <TableRow key={i} className={m.match_type === 'unmatched' ? 'opacity-50' : ''}>
                  <TableCell className="text-sm truncate max-w-[200px]">{m.input_name}</TableCell>
                  <TableCell>
                    {m.matched_name ? <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" /> : null}
                  </TableCell>
                  <TableCell className="text-sm truncate max-w-[200px]">
                    {m.matched_name ?? <span className="text-red-500 italic">No match</span>}
                  </TableCell>
                  <TableCell>
                    {m.match_type === 'fuzzy' && (
                      <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-700">
                        {Math.round((m.similarity ?? 0) * 100)}%
                      </Badge>
                    )}
                    {m.match_type === 'unmatched' && (
                      <Badge variant="outline" className="text-[10px] bg-red-50 text-red-700">
                        miss
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* All exact — just confirm */}
      {summary.fuzzy === 0 && summary.unmatched === 0 && (
        <p className="text-sm text-muted-foreground">
          All {summary.exact} SKUs matched exactly. Ready to build PO.
        </p>
      )}

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <Button onClick={handleConfirm} disabled={matchedCount === 0}>
          Build PO with {matchedCount} item{matchedCount !== 1 ? 's' : ''}
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src/dashboard" && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/components/SkuMatchReview.tsx
git commit -m "feat: add SkuMatchReview component for reviewing fuzzy/unmatched matches"
```

---

## Chunk 4: Frontend — PO Builder Integration

### Task 10: Integrate Subset Mode into PoBuilder

The PO Builder currently only works in "full brand" mode. We add a second mode: "subset" — where the user imports a SKU list. Subset mode stores the **raw API response** (as `PoDataItem[]`) and applies overrides in the `rows` memo, so toggleRow/updateQty/updateNotes remain fully reactive.

**Files:**
- Modify: `src/dashboard/src/pages/PoBuilder.tsx`

- [ ] **Step 1: Add imports**

Add to the imports at the top of PoBuilder.tsx:

```typescript
import { useMutation } from '@tanstack/react-query'
import { matchSkusForPo } from '@/lib/api'
import type { SkuMatchResult, SkuMatchSummary, PoDataItem } from '@/lib/types'
import SkuInputDialog from '@/components/SkuInputDialog'
import SkuMatchReview from '@/components/SkuMatchReview'
import { ClipboardList } from 'lucide-react'
```

Make sure `useMutation` is added to the existing `@tanstack/react-query` import (don't duplicate it — merge with the existing `useQuery` import).

- [ ] **Step 2: Add subset state and mutation**

Inside the `PoBuilder` function, after the existing state declarations (after the `[includeOk, setIncludeOk]` line, around line 63), add:

```typescript
  // Subset PO state
  const [showSkuInput, setShowSkuInput] = useState(false)
  const [subsetMode, setSubsetMode] = useState(false)
  const [subsetRawData, setSubsetRawData] = useState<PoDataItem[] | null>(null)
  const [matchResults, setMatchResults] = useState<{ matches: SkuMatchResult[]; summary: SkuMatchSummary } | null>(null)
  const [showMatchReview, setShowMatchReview] = useState(false)

  // Auto-open dialog when accessing /po directly (no brand)
  useEffect(() => {
    if (!decodedName && !subsetMode) setShowSkuInput(true)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const matchMutation = useMutation({
    mutationFn: matchSkusForPo,
    onSuccess: (data) => {
      setMatchResults({ matches: data.matches, summary: data.summary })
      if (data.summary.fuzzy === 0 && data.summary.unmatched === 0) {
        // All exact — skip review, go straight to PO table
        setSubsetMode(true)
        setSubsetRawData(data.po_data)
        setShowSkuInput(false)
      } else {
        setShowMatchReview(true)
        setShowSkuInput(false)
      }
    },
  })

  const handleSkuSubmit = (skuNames: string[]) => {
    matchMutation.mutate({
      sku_names: skuNames.slice(0, 500),
      lead_time: leadTime,
      buffer: bufferOverride ? bufferValue : undefined,
      from_date: fromDate ?? undefined,
      to_date: toDate ?? undefined,
    })
  }

  const activateSubsetFromReview = (acceptedNames: string[]) => {
    const accepted = new Set(acceptedNames)
    const filtered = (matchMutation.data?.po_data ?? []).filter(
      item => accepted.has(item.stock_item_name)
    )
    setSubsetMode(true)
    setSubsetRawData(filtered)
    setShowMatchReview(false)
  }

  const clearSubsetMode = () => {
    setSubsetMode(false)
    setSubsetRawData(null)
    setMatchResults(null)
    setShowMatchReview(false)
    setOverrides({})
  }
```

Also add `useEffect` to the React imports at the top if not already imported.

- [ ] **Step 3: Update the rows computation to support subset mode**

Replace the existing `rows` useMemo:

```typescript
  const rows: PoRow[] = useMemo(() =>
    (poData || []).map(item => {
      const o = overrides[item.stock_item_name] || {}
      return {
        ...item,
        sku_buffer: item.sku_buffer ?? 1.3,
        included: o.included ?? true,
        order_qty: o.order_qty ?? (item.suggested_qty || 0),
        notes: o.notes ?? '',
      }
    }),
    [poData, overrides]
  )
```

With:

```typescript
  const rows: PoRow[] = useMemo(() => {
    const source = subsetMode && subsetRawData ? subsetRawData : (poData || [])
    return source.map(item => {
      const o = overrides[item.stock_item_name] || {}
      return {
        ...item,
        sku_buffer: item.sku_buffer ?? 1.3,
        included: o.included ?? true,
        order_qty: o.order_qty ?? (item.suggested_qty || 0),
        notes: o.notes ?? '',
      }
    })
  }, [poData, overrides, subsetMode, subsetRawData])
```

This keeps overrides reactive in both modes — `toggleRow`, `updateQty`, `updateNotes` all work correctly because overrides are applied fresh each render.

- [ ] **Step 4: Update the header**

Replace:
```tsx
        <h2 className="text-xl font-semibold">Purchase Order — {decodedName}</h2>
```

With:
```tsx
        <h2 className="text-xl font-semibold">
          Purchase Order{subsetMode ? ' — Custom List' : decodedName ? ` — ${decodedName}` : ''}
        </h2>
```

- [ ] **Step 5: Add "Import SKU List" button**

Find the Export Excel button area (`<div className="flex items-end">` around line 263) and replace:

```tsx
            <div className="flex items-end">
              <Button onClick={handleExport} disabled={totalItems === 0}>
                <Download className="h-4 w-4 mr-1" /> Export Excel
              </Button>
            </div>
```

With:
```tsx
            <div className="flex items-end gap-2">
              <Button variant="outline" onClick={() => setShowSkuInput(true)}>
                <ClipboardList className="h-4 w-4 mr-1" /> Import SKU List
              </Button>
              <Button onClick={handleExport} disabled={totalItems === 0}>
                <Download className="h-4 w-4 mr-1" /> Export Excel
              </Button>
            </div>
```

- [ ] **Step 6: Add subset banner and match review UI**

After the hazardous warning section (after the closing `</Alert>` around line 290), add:

```tsx
      {/* Subset mode banner */}
      {subsetMode && (
        <div className="text-sm bg-blue-50 border border-blue-200 rounded-lg px-4 py-2.5 flex items-center justify-between">
          <span className="text-blue-800">
            <strong>Subset mode:</strong> Showing {rows.length} imported SKU{rows.length !== 1 ? 's' : ''} (may span multiple brands)
          </span>
          <Button variant="ghost" size="sm" className="text-blue-700 hover:text-blue-900" onClick={clearSubsetMode}>
            Clear & return to full brand
          </Button>
        </div>
      )}

      {/* Match review (shown after fuzzy/unmatched results) */}
      {showMatchReview && matchResults && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Review SKU Matches</CardTitle>
          </CardHeader>
          <CardContent>
            <SkuMatchReview
              matches={matchResults.matches}
              summary={matchResults.summary}
              onConfirm={activateSubsetFromReview}
              onBack={() => {
                setShowMatchReview(false)
                setShowSkuInput(true)
              }}
            />
          </CardContent>
        </Card>
      )}
```

- [ ] **Step 7: Add the dialog**

Add right before the closing `</TooltipProvider>`:

```tsx
      <SkuInputDialog
        open={showSkuInput}
        onOpenChange={setShowSkuInput}
        onSubmit={handleSkuSubmit}
        isLoading={matchMutation.isPending}
      />
```

- [ ] **Step 8: Update export handler for subset mode**

In the `handleExport` function, change:
```typescript
      category_name: decodedName,
```
To:
```typescript
      category_name: subsetMode ? 'CUSTOM' : decodedName,
```

- [ ] **Step 9: Verify build**

Run: `cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src/dashboard" && npm run build`

Expected: Build succeeds with no errors.

- [ ] **Step 10: Commit**

```bash
git add src/dashboard/src/pages/PoBuilder.tsx
git commit -m "feat: integrate subset PO builder with import dialog, match review, and reactive overrides"
```

---

## Chunk 5: Frontend — Routing & Navigation

### Task 11: Add Standalone /po Route

Allow accessing the PO Builder directly at `/po` (without a brand). The dialog auto-opens when no brand is in the URL.

**Files:**
- Modify: `src/dashboard/src/App.tsx`

- [ ] **Step 1: Add the route**

Add after the existing PO route (`/brands/:categoryName/po`):
```tsx
<Route path="/po" element={<SuspenseWrapper><PoBuilder /></SuspenseWrapper>} />
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/src/App.tsx
git commit -m "feat: add standalone /po route for cross-brand subset PO building"
```

---

### Task 12: Add Navigation Link

**Files:**
- Modify: `src/dashboard/src/components/Layout.tsx`

- [ ] **Step 1: Read Layout.tsx to understand nav structure**

Read the file and understand the existing navigation pattern.

- [ ] **Step 2: Add "Build PO" link**

Add a navigation item linking to `/po` using the `ClipboardList` icon from lucide-react. Place it logically near the "Critical SKUs" link. Match the existing nav item pattern exactly.

- [ ] **Step 3: Verify build**

Run: `cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src/dashboard" && npm run build`

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/components/Layout.tsx
git commit -m "feat: add 'Build PO' link to main navigation"
```

---

## Implementation Order

```
Task 1  (pg_trgm)               — backend, independent
Task 2  (extract PO helper)     — backend, independent
Task 3  (match endpoint)        — depends on Task 1 + 2
Task 4  (xlsx npm package)      — frontend, independent
Task 5  (sku-parser.ts)         — depends on Task 4
Task 6  (types + API)           — frontend, independent
Task 7  (dialog.tsx)            — frontend, independent
Task 8  (SkuInputDialog)        — depends on Tasks 5, 7
Task 9  (SkuMatchReview)        — depends on Task 6
Task 10 (PoBuilder integration) — depends on Tasks 6, 8, 9
Task 11 (standalone /po route)  — depends on Task 10
Task 12 (nav link)              — depends on Task 11
```

**Parallelizable groups:**
- Tasks 1-2 (backend) || Tasks 4, 6, 7 (frontend libs)
- Task 3 (after 1+2) || Tasks 5, 8, 9 (after their deps)
- Tasks 10-12 are sequential

## Verification

1. **Backend smoke test:**
   ```bash
   cd "C:/Users/Kshitij Shah/OneDrive/Documents/Art Lounge/ReOrderingProject/src"
   PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --port 8000 &
   curl -X POST http://localhost:8000/api/po-data/match \
     -H 'Content-Type: application/json' \
     -d '{"sku_names": ["WN COTMAN WATERCOLOUR 8ML", "Holbein AWC Scarlet Lake", "NONEXISTENT ITEM"]}'
   ```
   Expected: JSON with matches array (exact/fuzzy/unmatched) + po_data array.

2. **Frontend build:** `cd src/dashboard && npm run build` — no errors.

3. **Visual tests:**
   - Navigate to `/brands/WINSOR%20%26%20NEWTON/po` — existing PO builder works unchanged
   - Click "Import SKU List" — dialog opens with paste/upload tabs
   - Paste 3 SKU names — shows "3 unique SKU names detected"
   - Click "Match & Build PO" — if all exact, table loads; if fuzzy/unmatched, review screen shows
   - In subset mode, toggle rows, change quantities, add notes — all work reactively
   - Navigate to `/po` directly — dialog auto-opens
   - Banner shows "Subset mode: Showing N imported SKUs"
   - "Clear & return to full brand" exits subset mode
   - Export works in both modes
   - Nav has "Build PO" link
