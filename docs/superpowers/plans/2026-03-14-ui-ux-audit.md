# UI/UX Audit Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute 6 targeted UI/UX changes to reduce noise, surface what operations needs, and build confidence in the system's recommendations.

**Architecture:** Frontend-heavy refactor of 4 existing pages + 1 new page. One backend change (add store_velocity to SKU list API). One database migration (seed new settings keys). No engine changes.

**Tech Stack:** React + TypeScript + Vite + shadcn/ui (Radix + Tailwind), FastAPI + PostgreSQL backend.

**Spec:** `docs/superpowers/specs/2026-03-14-ui-ux-audit-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/db/migration_v4_settings_defaults.sql` | Create | Seed new app_settings keys |
| `src/api/routes/skus.py` | Modify | Add store_velocity to SKU list response |
| `src/dashboard/src/lib/types.ts` | Modify | Add store_velocity to SkuMetrics |
| `src/dashboard/src/pages/SkuDetail.tsx` | Modify | Column reorder + summary strip |
| `src/dashboard/src/components/CalculationBreakdown.tsx` | Modify | 3-layer confidence builder |
| `src/dashboard/src/pages/Home.tsx` | Modify | Simplify to actionable items |
| `src/dashboard/src/pages/Settings.tsx` | Create | Settings page with sidebar sections |
| `src/dashboard/src/App.tsx` | Modify | Add /settings route |
| `src/dashboard/src/components/Layout.tsx` | Modify | Grouped nav + Settings link |

---

## Chunk 1: Backend + Types

### Task 1: Database Migration — Seed New Settings Keys

**Files:**
- Create: `src/db/migration_v4_settings_defaults.sql`

- [ ] **Step 1: Write migration SQL**

```sql
BEGIN;

-- Analysis defaults (consumed by SkuDetail, CriticalSkus, DeadStock pages)
INSERT INTO app_settings (key, value) VALUES ('default_velocity_type', 'flat') ON CONFLICT DO NOTHING;
INSERT INTO app_settings (key, value) VALUES ('default_date_range', 'full_fy') ON CONFLICT DO NOTHING;

COMMIT;
```

Save to `src/db/migration_v4_settings_defaults.sql`.

- [ ] **Step 2: Run migration**

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -f src/db/migration_v4_settings_defaults.sql
```

Expected: `INSERT 0 1` (twice), `COMMIT`.

- [ ] **Step 3: Verify**

```bash
PGPASSWORD=password "/c/Program Files/PostgreSQL/17/bin/psql" -U reorder_app -d artlounge_reorder -c "SELECT * FROM app_settings WHERE key LIKE 'default_%' ORDER BY key"
```

Expected: 2 rows — `default_date_range = full_fy`, `default_velocity_type = flat`.

- [ ] **Step 4: Commit**

```bash
git add src/db/migration_v4_settings_defaults.sql
git commit -m "feat: seed analysis default settings (velocity type, date range)"
```

---

### Task 2: Backend — Add store_velocity to SKU List API

**Files:**
- Modify: `src/api/routes/skus.py:181-191` (effective values computation)

**Context:** `store_velocity` is not a stored DB column — it's derived as `max(0, total - wholesale - online)`. The breakdown endpoint already computes it (line 743-752), but the list endpoint does not include it. We need to add it so the summary strip can show channel velocities without a separate API call.

- [ ] **Step 1: Read the current effective values computation**

File: `src/api/routes/skus.py`, lines 181-191. This block computes `effective_velocity`, `effective_stock`, etc. after the main query. The row dict `d` already has `wholesale_velocity` and `online_velocity` from `sku_metrics`.

- [ ] **Step 2: Add store_velocity computation**

In `src/api/routes/skus.py`, in the effective values block (around line 191, after the existing effective value computations), add:

```python
# Derive store velocity (not stored — computed as remainder)
d["store_velocity"] = max(0, (d.get("total_velocity") or 0) - (d.get("wholesale_velocity") or 0) - (d.get("online_velocity") or 0))
```

This should be added inside the `for d in rows:` loop that processes effective values, AFTER all the `d["effective_*"]` assignments (around line 204), so it's clear this is a base value added to the response — not an input to the effective values computation.

- [ ] **Step 3: Verify with curl**

```bash
cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000
```

In another terminal:
```bash
curl -s "http://localhost:8000/api/brands/WINSOR%20%26%20NEWTON/skus?paginated=true&limit=1" | python -m json.tool | grep store_velocity
```

Expected: `"store_velocity": <some number>` in the response.

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/skus.py
git commit -m "feat: add store_velocity to SKU list API response"
```

---

### Task 3: Frontend Types — Add store_velocity

**Files:**
- Modify: `src/dashboard/src/lib/types.ts:48-50`

- [ ] **Step 1: Add store_velocity to SkuMetrics interface**

In `src/dashboard/src/lib/types.ts`, after `online_velocity` (line 49), add:

```typescript
  store_velocity: number
```

So lines 48-51 become:
```typescript
  wholesale_velocity: number
  online_velocity: number
  store_velocity: number
  total_velocity: number
```

- [ ] **Step 2: Build to verify no type errors**

```bash
cd src/dashboard && npm run build
```

Expected: Build succeeds (store_velocity was not previously required, so adding it won't break anything — it's just a new field the API now returns).

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/src/lib/types.ts
git commit -m "feat: add store_velocity to SkuMetrics type"
```

---

## Chunk 2: SKU Table Column Reorder + Summary Strip (Changes 1 & 2)

### Task 4: SkuDetail — Column Reorder

**Files:**
- Modify: `src/dashboard/src/pages/SkuDetail.tsx`

**What changes:** The table goes from 8 columns to 7: `[Expand] [Status] [Part No] [SKU Name] [Stock] [Velocity /mo] [ABC]`. Remove: Days Left, Suggested, Intent. Remove secondary metadata row. Add Part No column (bold monospace) and ABC column.

- [ ] **Step 1: Update table headers (lines 536-545)**

Replace the current 8 TableHead elements with 7:

```tsx
<TableHead className="w-8"></TableHead>
<TableHead className="w-[80px]">Status</TableHead>
<TableHead className="w-[110px]">Part No</TableHead>
<TableHead>SKU Name</TableHead>
<TableHead className="text-right">Stock</TableHead>
<TableHead className="text-right">Velocity /mo</TableHead>
<TableHead className="text-center w-[60px]">ABC</TableHead>
```

- [ ] **Step 2: Update skeleton loading to match 7 columns (lines 516, 524)**

Change `{ length: 8 }` to `{ length: 7 }` in both the header and body skeleton loops.

- [ ] **Step 3: Update "No SKUs found" colSpan (line 561)**

Change `colSpan={8}` to `colSpan={7}`.

- [ ] **Step 4: Update SkuRow primary row (lines 71-156)**

Replace the entire primary row (lines 71-156) with the new 7-column layout:

```tsx
{/* Primary row — 7 columns */}
<TableRow
  className="cursor-pointer hover:bg-muted/50"
  onClick={() => onToggle(s.stock_item_name)}
>
  <TableCell>
    {isExpanded
      ? <ChevronDown className="h-4 w-4" />
      : <ChevronRight className="h-4 w-4" />}
  </TableCell>
  <TableCell><StatusBadge status={s.effective_status ?? s.reorder_status} /></TableCell>
  <TableCell className="font-mono font-semibold text-sm">
    {s.part_no || '—'}
  </TableCell>
  <TableCell className="max-w-[280px] truncate" title={s.stock_item_name}>
    <span className="inline-flex items-center gap-1">
      {s.stock_item_name}
      {s.is_hazardous && (
        <Tooltip>
          <TooltipTrigger>
            <span className="text-amber-500 text-xs">■</span>
          </TooltipTrigger>
          <TooltipContent>Hazardous material</TooltipContent>
        </Tooltip>
      )}
      {s.reorder_intent === 'must_stock' && (
        <Badge className="bg-purple-100 text-purple-700 hover:bg-purple-100 text-[10px] px-1 py-0">Must Stock</Badge>
      )}
      {s.reorder_intent === 'do_not_reorder' && (
        <Badge className="bg-gray-100 text-gray-500 hover:bg-gray-100 text-[10px] px-1 py-0">DNR</Badge>
      )}
      {s.is_dead_stock && (
        <Tooltip>
          <TooltipTrigger>
            <Snowflake className="h-3.5 w-3.5 text-blue-500 shrink-0" />
          </TooltipTrigger>
          <TooltipContent>Dead stock — no sales for {s.days_since_last_sale ?? '∞'} days</TooltipContent>
        </Tooltip>
      )}
      {s.has_note && (
        <Tooltip>
          <TooltipTrigger>
            <StickyNote className="h-3.5 w-3.5 text-blue-500 shrink-0" />
          </TooltipTrigger>
          <TooltipContent>Has annotation note</TooltipContent>
        </Tooltip>
      )}
    </span>
  </TableCell>
  <TableCell className={`text-right ${(s.effective_stock ?? s.current_stock) <= 0 ? 'text-red-600 font-medium' : ''}`}>
    <span className="inline-flex items-center gap-1 justify-end">
      {s.effective_stock ?? s.current_stock}
      {s.has_stock_override && (
        <Tooltip>
          <TooltipTrigger>
            {s.stock_override_stale
              ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
              : <Pencil className="h-3.5 w-3.5 text-blue-500 shrink-0" />}
          </TooltipTrigger>
          <TooltipContent>
            Stock override active (computed: {s.current_stock})
            {s.stock_override_stale && ' — STALE: Tally data changed'}
          </TooltipContent>
        </Tooltip>
      )}
    </span>
  </TableCell>
  <TableCell className="text-right font-medium">
    <span className="inline-flex items-center gap-1 justify-end">
      {velocityType === 'wma'
        ? vel(s.wma_total_velocity ?? 0)
        : vel(s.effective_velocity ?? s.total_velocity)}
      <TrendIndicator direction={s.trend_direction} ratio={s.trend_ratio} />
      {s.has_velocity_override && (
        <Tooltip>
          <TooltipTrigger>
            {s.velocity_override_stale
              ? <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
              : <Pencil className="h-3.5 w-3.5 text-blue-500 shrink-0" />}
          </TooltipTrigger>
          <TooltipContent>
            Velocity override active (computed: {vel(s.total_velocity)}/mo)
            {s.velocity_override_stale && ' — STALE'}
          </TooltipContent>
        </Tooltip>
      )}
    </span>
  </TableCell>
  <TableCell className="text-center">
    {s.abc_class && (
      <Badge className={`text-[10px] px-2 py-0 font-semibold ${
        s.abc_class === 'A' ? 'bg-red-100 text-red-700 hover:bg-red-100' :
        s.abc_class === 'B' ? 'bg-amber-100 text-amber-700 hover:bg-amber-100' :
        'bg-gray-100 text-gray-500 hover:bg-gray-100'
      }`}>
        {s.abc_class}
      </Badge>
    )}
  </TableCell>
</TableRow>
```

- [ ] **Step 5: Remove secondary metadata row (lines 158-168)**

Delete the entire `{/* Secondary metadata line */}` TableRow block. This removes the ABC/XYZ/Part No/Hazardous secondary line.

- [ ] **Step 6: Update expanded row colSpan (line 173)**

Change `colSpan={8}` to `colSpan={7}`.

- [ ] **Step 7: Remove unused imports**

Remove `SkuSecondaryLine` import (line 19) and `ReorderIntentSelector` import (line 17) from the SkuRow section. Note: `ReorderIntentSelector` will be used in the summary strip (Task 5), so keep the import but it won't be in SkuRow anymore.

Actually — keep `ReorderIntentSelector` import for Task 5. Remove only `SkuSecondaryLine` import.

- [ ] **Step 8: Build and verify**

```bash
cd src/dashboard && npm run build
```

Expected: Build succeeds. Open browser and verify the SKU table now shows 7 columns with Part No prominent and ABC badge.

- [ ] **Step 9: Commit**

```bash
git add src/dashboard/src/pages/SkuDetail.tsx
git commit -m "feat: reorder SKU table columns — promote Part No and ABC class"
```

---

### Task 5: SkuDetail — Summary Strip in Expanded Row

**Files:**
- Modify: `src/dashboard/src/pages/SkuDetail.tsx` (SkuRow component, expanded section)

**What changes:** When a row is expanded, show a summary strip with channel velocity, stock & stockout, and reorder info ABOVE the existing tabs. Add ReorderIntentSelector to the reorder section.

- [ ] **Step 1: Add supplier_lead_time prop to SkuRow**

The summary strip shows lead time, which comes from `BrandMetrics`, not `SkuMetrics`. The SkuDetail page needs to pass it down. Update SkuRow's props interface to include `supplierLeadTime`:

```tsx
const SkuRow = memo(function SkuRow({
  s,
  isExpanded,
  onToggle,
  decodedName,
  analysisRange,
  velocityType,
  supplierLeadTime,
}: {
  s: SkuMetrics
  isExpanded: boolean
  onToggle: (name: string) => void
  decodedName: string
  analysisRange: { from: string; to: string } | null
  velocityType: 'flat' | 'wma'
  supplierLeadTime?: number
}) {
```

- [ ] **Step 2: Add summary strip to expanded section**

Replace the expanded detail block (the `{isExpanded && (...)}` section) with a version that includes the summary strip above the tabs:

```tsx
{/* Expanded detail */}
{isExpanded && (
  <TableRow>
    <TableCell colSpan={7} className="bg-muted/30 p-0">
      {/* Summary Strip */}
      <div className="grid grid-cols-[1.2fr_0.8fr_0.8fr] border-b-2 border-border">
        {/* Channel Velocity */}
        <div className="p-4 border-r border-border/50">
          <div className="text-[10px] uppercase text-muted-foreground tracking-wider mb-2">Velocity by Channel</div>
          <div className="flex gap-5 items-baseline">
            <div>
              <div className="text-[10px] text-muted-foreground">Wholesale</div>
              <div className="text-lg font-bold text-blue-600">{vel(s.wholesale_velocity)}</div>
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground">Online</div>
              <div className="text-lg font-bold text-purple-600">{vel(s.online_velocity)}</div>
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground">Store</div>
              <div className="text-lg font-bold text-emerald-600">{vel(s.store_velocity)}</div>
            </div>
            <div className="border-l border-border pl-4">
              <div className="text-[10px] text-muted-foreground">Total /mo</div>
              <div className="text-lg font-bold">
                {vel(s.effective_velocity ?? s.total_velocity)}
                <TrendIndicator direction={s.trend_direction} ratio={s.trend_ratio} />
              </div>
            </div>
          </div>
        </div>

        {/* Stock & Stockout */}
        <div className="p-4 border-r border-border/50">
          <div className="text-[10px] uppercase text-muted-foreground tracking-wider mb-2">Stock & Stockout</div>
          <div className="flex gap-4 items-baseline">
            <div>
              <div className="text-[10px] text-muted-foreground">In Stock</div>
              <div className="text-lg font-bold">{s.effective_stock ?? s.current_stock} <span className="text-xs font-normal text-muted-foreground">units</span></div>
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground">Days Left</div>
              <div className={`text-lg font-bold ${
                (s.effective_days_to_stockout ?? s.days_to_stockout) !== null &&
                (s.effective_days_to_stockout ?? s.days_to_stockout)! <= (supplierLeadTime ?? 90)
                  ? 'text-red-600'
                  : (s.effective_days_to_stockout ?? s.days_to_stockout) !== null &&
                    (s.effective_days_to_stockout ?? s.days_to_stockout)! <= (supplierLeadTime ?? 90) * 1.5
                    ? 'text-amber-600'
                    : ''
              }`}>
                {daysDisplay(s.effective_days_to_stockout ?? s.days_to_stockout)}
              </div>
            </div>
          </div>
        </div>

        {/* Reorder */}
        <div className="p-4">
          <div className="text-[10px] uppercase text-muted-foreground tracking-wider mb-2">Reorder</div>
          <div>
            <div className="text-[10px] text-muted-foreground">Suggested</div>
            <div className="text-lg font-bold">{s.effective_suggested_qty ?? s.reorder_qty_suggested ?? '—'} <span className="text-xs font-normal text-muted-foreground">units</span></div>
          </div>
          <div className="text-[10px] text-muted-foreground mt-1">
            Buffer {s.safety_buffer ?? '—'}x · Lead {supplierLeadTime ?? '—'}d
            {s.abc_class && (
              <span className="ml-1">
                · <Badge className={`text-[9px] px-1 py-0 ${
                  s.abc_class === 'A' ? 'bg-red-100 text-red-700 hover:bg-red-100' :
                  s.abc_class === 'B' ? 'bg-amber-100 text-amber-700 hover:bg-amber-100' :
                  'bg-gray-100 text-gray-500 hover:bg-gray-100'
                }`}>{s.abc_class}</Badge>
              </span>
            )}
          </div>
          <div className="mt-2" onClick={e => e.stopPropagation()}>
            <ReorderIntentSelector
              stockItemName={s.stock_item_name}
              currentIntent={s.reorder_intent || 'normal'}
            />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="timeline" className="p-4">
        <TabsList>
          <TabsTrigger value="timeline">Stock Timeline</TabsTrigger>
          <TabsTrigger value="transactions">Transactions</TabsTrigger>
          <TabsTrigger value="calculation">Calculation</TabsTrigger>
        </TabsList>
        <TabsContent value="timeline" className="pt-4">
          <StockTimelineChart categoryName={decodedName} stockItemName={s.stock_item_name} />
        </TabsContent>
        <TabsContent value="transactions" className="pt-4">
          <TransactionHistory categoryName={decodedName} stockItemName={s.stock_item_name} />
        </TabsContent>
        <TabsContent value="calculation" className="pt-4">
          <CalculationBreakdown
            categoryName={decodedName}
            stockItemName={s.stock_item_name}
            fromDate={analysisRange?.from}
            toDate={analysisRange?.to}
          />
        </TabsContent>
      </Tabs>
    </TableCell>
  </TableRow>
)}
```

- [ ] **Step 3: Pass supplierLeadTime from SkuDetail to SkuRow**

In the SkuDetail component, we need brand-level data for lead time. Check if there's already a brand query. If not, add a simple query for it. Look at the existing code — the page already has `decodedName` (the brand name). Add a query for brand summary or pass lead time from the suppliers API.

The simplest approach: fetch suppliers list and find the matching one. But since this is a brand page, we can use the existing dashboard summary which has brand-level data, or just add a direct query.

For now, use a simple approach — add a `useQuery` for brand metrics:

```tsx
import { fetchBrands } from '@/lib/api'

// Inside SkuDetail component, after other queries:
const { data: brands } = useQuery({
  queryKey: ['brands'],
  queryFn: fetchBrands,
  staleTime: 5 * 60 * 1000,
})
const brandLeadTime = brands?.find(b => b.category_name === decodedName)?.supplier_lead_time
```

Then pass to SkuRow:
```tsx
<SkuRow
  key={s.stock_item_name}
  s={s}
  isExpanded={expandedRow === s.stock_item_name}
  onToggle={handleToggleRow}
  decodedName={decodedName}
  analysisRange={analysisRange}
  velocityType={velocityType}
  supplierLeadTime={brandLeadTime}
/>
```

Also add `fetchBrands` to the import from `@/lib/api`.

- [ ] **Step 4: Build and verify**

```bash
cd src/dashboard && npm run build
```

Expected: Build succeeds. Open browser, navigate to a brand's SKU page, expand a row. Verify the summary strip appears above the tabs with channel velocity, stock & stockout, and reorder sections.

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/src/pages/SkuDetail.tsx
git commit -m "feat: add summary strip to expanded SKU row with channel velocity"
```

---

## Chunk 3: Calculation Breakdown Redesign (Change 3)

### Task 6: CalculationBreakdown — 3-Layer Confidence Builder

**Files:**
- Modify: `src/dashboard/src/components/CalculationBreakdown.tsx`

**What changes:** Replace the 5-card layout with 3 collapsible layers: Verdict (always visible) → Key Assumptions (expanded by default) → Methodology (collapsed by default). Remove Position Reconstruction and Transaction Breakdown cards. Reuse existing `OverrideForm`, `BufferModeSelector`, `InStockBar` components.

- [ ] **Step 1: Read the current component thoroughly**

Read `src/dashboard/src/components/CalculationBreakdown.tsx` lines 261-605 to understand the full data flow. The key data comes from `BreakdownResponse` which has: `data_source`, `position_reconstruction`, `transaction_summary`, `date_range`, `velocity`, `stockout`, `reorder`, `effective_values`.

- [ ] **Step 2: Add verdict generation helper**

Add this function before the main component (after the existing helper components, around line 260):

```tsx
function generateVerdict(data: BreakdownResponse): { text: string; color: string } {
  const { velocity, stockout, reorder } = data
  const channels = [
    { name: 'Wholesale', vel: velocity.wholesale.monthly_velocity },
    { name: 'Online', vel: velocity.online.monthly_velocity },
    { name: 'Store', vel: velocity.store.monthly_velocity },
  ]
  const dominant = channels.reduce((a, b) => a.vel >= b.vel ? a : b)
  const qty = reorder.suggested_qty
  const days = stockout.days_to_stockout
  const lead = reorder.supplier_lead_time
  const buffer = reorder.buffer_multiplier

  const status = reorder.status
  if (status === 'out_of_stock') {
    return {
      text: `Out of stock — order ${qty ?? '?'} units immediately.`,
      color: 'bg-red-50 border-red-200',
    }
  }
  if (status === 'no_data') {
    return {
      text: 'Insufficient data to make a recommendation. No velocity data available.',
      color: 'bg-gray-50 border-gray-200',
    }
  }
  if (status === 'critical') {
    return {
      text: `Order ${qty} units. ${dominant.name} demand is driving this at ${dominant.vel}/mo. At current velocity you have ~${days} days of stock, but with ${lead}-day lead time and ${buffer}x buffer, you should order now.`,
      color: 'bg-red-50 border-red-200',
    }
  }
  if (status === 'warning') {
    return {
      text: `Consider ordering ${qty} units. You have ~${days} days of stock — within the ${lead}-day lead time window.`,
      color: 'bg-amber-50 border-amber-200',
    }
  }
  // ok
  return {
    text: `No immediate action needed. You have ~${days} days of stock, well above the ${lead}-day lead time.`,
    color: 'bg-green-50 border-green-200',
  }
}
```

- [ ] **Step 3: Rewrite the main component render**

Replace the entire return block of the `CalculationBreakdown` component (everything after the loading/error/null checks, starting from `const { data_source, ... } = data`) with the 3-layer layout:

```tsx
  const { data_source, transaction_summary, date_range, velocity, stockout, reorder, effective_values } = data
  const overrides = data_source.overrides || {}
  const verdict = generateVerdict(data)

  return (
    <div className="space-y-4">
      {/* Layer 1: Verdict — always visible */}
      <div className={`rounded-lg border p-4 ${verdict.color}`}>
        <div className="text-xs uppercase font-semibold tracking-wider mb-1 opacity-70">
          {reorder.status === 'ok' ? '✓' : reorder.status === 'warning' ? '⚠' : '●'} Recommendation
        </div>
        <div className="text-sm leading-relaxed">
          <strong>{verdict.text.split('.')[0]}.</strong>
          {verdict.text.includes('.') && verdict.text.slice(verdict.text.indexOf('.') + 1)}
        </div>
        {data_source.data_as_of && (
          <div className="text-xs text-muted-foreground mt-2">
            Based on data as of {new Date(data_source.data_as_of).toLocaleDateString('en-IN', { dateStyle: 'medium' })}
            {' · '}Analysis: {date_range.from_date} — {date_range.to_date} ({date_range.total_days_in_range}d)
          </div>
        )}
      </div>

      {/* Layer 2: Key Assumptions — expanded by default */}
      <CollapsibleSection title="Key Assumptions" subtitle="Verify inputs" defaultOpen={true}>
        <table className="w-full text-sm">
          <tbody>
            <tr className="border-b border-border/50">
              <td className="py-2 text-muted-foreground w-[140px]">Lead Time</td>
              <td className="py-2 font-medium">{reorder.supplier_lead_time} days{reorder.supplier_name ? ` (${reorder.supplier_name})` : ''}</td>
              <td className="py-2 text-right">
                <a href="/suppliers" className="text-xs text-blue-600 hover:underline">Edit</a>
              </td>
            </tr>
            <tr className="border-b border-border/50">
              <td className="py-2 text-muted-foreground">Safety Buffer</td>
              <td className="py-2 font-medium">{reorder.buffer_multiplier}x ({reorder.buffer_mode === 'abc_xyz' ? 'ABC×XYZ' : 'ABC only'})</td>
              <td className="py-2 text-right">
                <BufferModeSelector
                  stockItemName={stockItemName}
                  categoryName={categoryName}
                  currentValue={reorder.use_xyz_buffer}
                  bufferMode={reorder.buffer_mode}
                />
              </td>
            </tr>
            <tr className="border-b border-border/50">
              <td className="py-2 text-muted-foreground">Total Velocity</td>
              <td className="py-2 font-medium">
                {velocity.total.monthly_velocity} /mo
                <span className="text-muted-foreground text-xs ml-1">
                  (W: {velocity.wholesale.monthly_velocity} + O: {velocity.online.monthly_velocity} + S: {velocity.store.monthly_velocity})
                </span>
              </td>
              <td className="py-2 text-right">
                <OverrideForm fieldName="total_velocity" label="total velocity" currentOverride={overrides.total_velocity} stockItemName={stockItemName} categoryName={categoryName} />
              </td>
            </tr>
            <tr className="border-b border-border/50">
              <td className="py-2 text-muted-foreground">Current Stock</td>
              <td className="py-2 font-medium">
                {stockout.current_stock} units
                {effective_values.stock_source === 'override' && (
                  <span className="text-xs text-blue-600 ml-1">(overridden from {data_source.closing_balance_from_tally})</span>
                )}
              </td>
              <td className="py-2 text-right">
                <OverrideForm fieldName="current_stock" label="stock" currentOverride={overrides.current_stock} stockItemName={stockItemName} categoryName={categoryName} />
              </td>
            </tr>
            <tr>
              <td className="py-2 text-muted-foreground">In-Stock Days</td>
              <td className="py-2 font-medium">{velocity.in_stock_days} of {date_range.total_days_in_range} days ({velocity.in_stock_pct}%)</td>
              <td className="py-2 text-right text-xs text-muted-foreground italic">gut check</td>
            </tr>
          </tbody>
        </table>

        {/* Note override */}
        <div className="mt-3 pt-3 border-t">
          <OverrideForm fieldName="note" label="Note" currentOverride={overrides.note} stockItemName={stockItemName} categoryName={categoryName} />
        </div>
      </CollapsibleSection>

      {/* Layer 3: Methodology — collapsed by default */}
      <CollapsibleSection title="Methodology & Formulas" subtitle="How the numbers are calculated" defaultOpen={false}>
        {/* M1: Velocity */}
        <MethodologySection number={1} title="Velocity — How we measure demand">
          <p className="text-sm text-muted-foreground mb-3">
            Velocity is calculated over <strong className="text-foreground">in-stock days only</strong> to avoid underestimating demand during stockout periods.
          </p>
          <div className="font-mono text-xs bg-muted/50 rounded p-2 mb-3">
            {velocity.formula}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Channel</TableHead>
                <TableHead className="text-right">Units Sold</TableHead>
                <TableHead className="text-right">÷ In-Stock Days</TableHead>
                <TableHead className="text-right">= Daily</TableHead>
                <TableHead className="text-right">×30 = Monthly</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(['wholesale', 'online', 'store'] as const).map(ch => {
                const c = velocity[ch]
                return (
                  <TableRow key={ch}>
                    <TableCell className="capitalize font-medium">{ch}</TableCell>
                    <TableCell className="text-right">{c.total_units}</TableCell>
                    <TableCell className="text-right text-muted-foreground">÷ {velocity.in_stock_days}</TableCell>
                    <TableCell className="text-right">{c.daily_velocity}</TableCell>
                    <TableCell className="text-right font-semibold">{c.monthly_velocity}</TableCell>
                  </TableRow>
                )
              })}
              <TableRow className="border-t-2 font-semibold">
                <TableCell>Total</TableCell>
                <TableCell className="text-right">{velocity.total.total_units}</TableCell>
                <TableCell className="text-right text-muted-foreground">÷ {velocity.in_stock_days}</TableCell>
                <TableCell className="text-right">{velocity.total.daily_velocity}</TableCell>
                <TableCell className="text-right">{velocity.total.monthly_velocity}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <div className="text-xs text-muted-foreground mt-2">
            Confidence: <Badge variant="outline" className={confidenceColors[velocity.confidence]}>{velocity.confidence}</Badge>
            {' '}{velocity.confidence_reason}
          </div>
        </MethodologySection>

        {/* M2: In-Stock Days */}
        <MethodologySection number={2} title="In-Stock Days — Active periods">
          <InStockBar data={data} />
          <div className="flex gap-4 text-sm mt-2">
            <span>Active: <strong className="text-green-600">{velocity.in_stock_days} days</strong> ({velocity.in_stock_pct}%)</span>
            <span>Inactive: <strong className="text-red-600">{velocity.out_of_stock_days} days</strong></span>
          </div>
          {velocity.out_of_stock_days > 0 && velocity.out_of_stock_exclusion_reason && (
            <div className="text-xs text-muted-foreground mt-2 bg-amber-50 border border-amber-200 rounded p-2">
              <Info className="h-3.5 w-3.5 inline mr-1 text-amber-600" />
              {velocity.out_of_stock_exclusion_reason}
            </div>
          )}
        </MethodologySection>

        {/* M3: Stockout */}
        <MethodologySection number={3} title="Stockout Projection">
          <div className="font-mono text-xs bg-muted/50 rounded p-2 mb-2">
            {stockout.formula}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <FlowBox label="Stock" value={`${stockout.current_stock}`} className="bg-blue-50 border-blue-200" />
            <FlowArrow />
            <FlowBox label="÷ Burn rate" value={`${stockout.daily_burn_rate}/day`} className="bg-orange-50 border-orange-200" />
            <FlowArrow />
            <FlowBox label="= Days left" value={stockout.days_to_stockout !== null ? `${stockout.days_to_stockout}` : 'N/A'} className="bg-purple-50 border-purple-200" />
          </div>
          {stockout.estimated_stockout_date && (
            <div className="text-sm text-muted-foreground mt-2">
              Estimated stockout: <strong>{new Date(stockout.estimated_stockout_date).toLocaleDateString('en-IN', { dateStyle: 'medium' })}</strong>
            </div>
          )}
        </MethodologySection>

        {/* M4: Reorder */}
        <MethodologySection number={4} title="Reorder Quantity">
          <div className="font-mono text-xs bg-muted/50 rounded p-2 mb-2">
            {reorder.formula}
          </div>
          {reorder.supplier_name && (
            <div className="text-sm text-muted-foreground">
              Supplier: <strong>{reorder.supplier_name}</strong> ({reorder.supplier_lead_time}d lead time) · Buffer: <strong>{reorder.buffer_multiplier}x</strong>
            </div>
          )}
          {reorder.suggested_qty !== null && (
            <div className="text-sm mt-1">
              Suggested order: <strong className="text-base">{reorder.suggested_qty} units</strong>
            </div>
          )}
        </MethodologySection>

        {/* M5: Status */}
        <MethodologySection number={5} title="Status Determination">
          <div className="text-sm text-muted-foreground mb-2">
            Status is determined by comparing days-to-stockout against the supplier's lead time:
          </div>
          <div className="text-xs space-y-1 mb-3">
            <div className="flex items-center gap-2">
              <StatusBadge status="critical" /> days_left ≤ lead_time × 1.0 ({reorder.supplier_lead_time}d)
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status="warning" /> days_left ≤ lead_time × 1.5 ({Math.round(reorder.supplier_lead_time * 1.5)}d)
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status="ok" /> days_left &gt; lead_time × 1.5
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status="out_of_stock" /> current_stock ≤ 0
            </div>
          </div>
          <div className={`rounded-lg border p-3 ${statusColors[reorder.status] || statusColors.no_data}`}>
            <div className="font-medium capitalize">{reorder.status.replace('_', ' ')}</div>
            <div className="text-sm mt-1">{reorder.status_reason}</div>
          </div>
        </MethodologySection>
      </CollapsibleSection>
    </div>
  )
```

- [ ] **Step 4: Add CollapsibleSection and MethodologySection helper components**

Add these before the main component (after `BufferModeSelector`, around line 259):

```tsx
function CollapsibleSection({ title, subtitle, defaultOpen, children }: {
  title: string
  subtitle: string
  defaultOpen: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border rounded-lg">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 rounded-t-lg text-left"
      >
        <span className="font-semibold text-sm">{open ? '▾' : '▸'} {title}</span>
        <span className="text-xs text-muted-foreground">{subtitle}</span>
      </button>
      {open && <div className="px-4 py-3">{children}</div>}
    </div>
  )
}

function MethodologySection({ number, title, children }: {
  number: number
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="mb-5 last:mb-0">
      <div className="text-sm font-semibold mb-2 flex items-center gap-2">
        <span className="bg-blue-50 text-blue-600 text-[10px] font-bold px-1.5 py-0.5 rounded">{number}</span>
        {title}
      </div>
      <div className="bg-muted/20 border rounded-lg p-3 text-sm">
        {children}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Clean up unused imports and variables**

Remove from the component:
- `position_reconstruction` from the destructuring (no longer used)
- `transaction_summary` from the destructuring (no longer used in this component)
- `SHOW_ASSUMPTIONS_STRIP` constant (no longer needed)
- Remove `CheckCircle2`, `XCircle`, `ArrowRight` from icon imports if no longer used
- Keep `Card`, `Table`, etc. imports that are still used in methodology sections
- Keep `FlowBox`, `FlowArrow`, `InStockBar` — they're reused in Layer 3

Actually, `Card`/`CardContent`/`CardHeader`/`CardTitle` are no longer used (we use plain divs now). Remove those imports. Keep `Table` components — used in methodology velocity table.

- [ ] **Step 6: Add StatusBadge import**

```tsx
import StatusBadge from '@/components/StatusBadge'
```

- [ ] **Step 7: Build and verify**

```bash
cd src/dashboard && npm run build
```

Expected: Build succeeds. Open browser, expand a SKU, click the Calculation tab. Verify the 3-layer layout: Verdict (always shown) → Key Assumptions (expanded) → Methodology (collapsed, click to expand).

- [ ] **Step 8: Commit**

```bash
git add src/dashboard/src/components/CalculationBreakdown.tsx
git commit -m "feat: redesign Calculation Breakdown as 3-layer confidence builder"
```

---

## Chunk 4: Home Page + Settings + Navigation (Changes 4, 5, 6)

### Task 7: Home Page — Simplify

**Files:**
- Modify: `src/dashboard/src/pages/Home.tsx`

**What changes:** Strip to 3 sections: brand search, 3 action cards, priority brands table. Remove Portfolio Health section (4 chart cards).

- [ ] **Step 1: Read current Home.tsx**

Read `src/dashboard/src/pages/Home.tsx` fully. Note the data flow: `fetchDashboardSummary()` returns a `DashboardSummary` object with all stats.

- [ ] **Step 2: Rewrite Home component**

Replace the entire component with a simplified version:

```tsx
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { fetchDashboardSummary, fetchBrands } from '@/lib/api'
import type { DashboardSummary, BrandMetrics } from '@/lib/types'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Search, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function Home() {
  const navigate = useNavigate()
  const [brandSearch, setBrandSearch] = useState('')
  const { data: summary, isLoading } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
  })
  const { data: brands } = useQuery({
    queryKey: ['brands'],
    queryFn: fetchBrands,
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading || !summary) {
    return (
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        <div className="h-8 w-48 bg-muted animate-pulse rounded" />
        <div className="h-12 bg-muted animate-pulse rounded-lg" />
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map(i => <div key={i} className="h-24 bg-muted animate-pulse rounded-lg" />)}
        </div>
      </div>
    )
  }

  const s = summary
  const filteredBrands = brands?.filter(b =>
    b.category_name.toLowerCase().includes(brandSearch.toLowerCase())
  ).slice(0, brandSearch ? 10 : 0) ?? []

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <h1 className="text-xl font-bold">Welcome back</h1>

      {/* Brand Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Jump to brand... (type to search)"
          value={brandSearch}
          onChange={e => setBrandSearch(e.target.value)}
          className="pl-10 h-12 text-base"
        />
        {filteredBrands.length > 0 && (
          <div className="absolute z-10 top-full mt-1 w-full bg-background border rounded-lg shadow-lg max-h-64 overflow-y-auto">
            {filteredBrands.map(b => (
              <button
                key={b.category_name}
                className="w-full text-left px-4 py-2 hover:bg-muted flex items-center justify-between text-sm"
                onClick={() => {
                  navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)
                  setBrandSearch('')
                }}
              >
                <span className="font-medium">{b.category_name}</span>
                <span className="text-muted-foreground text-xs">
                  {b.critical_skus > 0 && <span className="text-red-600 mr-2">{b.critical_skus} critical</span>}
                  {b.total_skus} SKUs
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Action Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="border-red-200 bg-red-50 cursor-pointer hover:bg-red-100 transition-colors" onClick={() => navigate('/critical')}>
          <CardContent className="p-4">
            <div className="text-3xl font-bold text-red-600">{s.a_critical + s.b_critical + s.c_critical}</div>
            <div className="text-sm text-red-800">Critical SKUs across {s.brands_with_critical} brands</div>
          </CardContent>
        </Card>
        <Card className="border-amber-200 bg-amber-50 cursor-pointer hover:bg-amber-100 transition-colors" onClick={() => navigate('/brands')}>
          <CardContent className="p-4">
            <div className="text-3xl font-bold text-amber-600">{s.brands_with_critical}</div>
            <div className="text-sm text-amber-800">Brands need POs</div>
          </CardContent>
        </Card>
        <Card className="border-border bg-muted/30">
          <CardContent className="p-4">
            <div className="text-3xl font-bold">{s.total_brands}</div>
            <div className="text-sm text-muted-foreground">Total brands tracked</div>
          </CardContent>
        </Card>
      </div>

      {/* Priority Brands Table */}
      <div>
        <h2 className="text-sm font-semibold mb-2">Brands Needing Attention</h2>
        <div className="border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Brand</TableHead>
                <TableHead className="text-right">Critical</TableHead>
                <TableHead className="text-right">Warning</TableHead>
                <TableHead className="text-right">Out of Stock</TableHead>
                <TableHead className="w-8"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(s.top_brands || []).slice(0, 10).map((b) => (
                <TableRow
                  key={b.category_name}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => navigate(`/brands/${encodeURIComponent(b.category_name)}/skus`)}
                >
                  <TableCell className="font-medium">{b.category_name}</TableCell>
                  <TableCell className="text-right">
                    {b.critical_skus > 0 && (
                      <span className="text-red-600 font-semibold">{b.critical_skus}</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {b.warning_skus > 0 && <span className="text-amber-600">{b.warning_skus}</span>}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">—</TableCell>
                  <TableCell>
                    <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <Button variant="link" className="mt-2 text-xs" onClick={() => navigate('/brands')}>
          View all brands →
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/pages/Home.tsx
git commit -m "feat: simplify home page to brand search + action cards + priority table"
```

---

### Task 8: Settings Page — New

**Files:**
- Create: `src/dashboard/src/pages/Settings.tsx`

- [ ] **Step 1: Create the Settings page**

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchSettings, updateSetting, fetchSuppliers } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings as SettingsIcon, ArrowRight, Check } from 'lucide-react'

const SECTIONS = [
  { id: 'buffers', label: 'Safety Buffers' },
  { id: 'lead-times', label: 'Lead Times' },
  { id: 'analysis', label: 'Analysis Defaults' },
  { id: 'dead-stock', label: 'Dead Stock Thresholds' },
  { id: 'classification', label: 'Classification' },
] as const

export default function Settings() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeSection, setActiveSection] = useState('buffers')
  const sectionRefs = useRef<Record<string, HTMLDivElement | null>>({})

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
  })
  const { data: suppliers } = useQuery({
    queryKey: ['suppliers'],
    queryFn: fetchSuppliers,
  })

  const saveMut = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => updateSetting(key, value),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  })

  const scrollTo = (id: string) => {
    setActiveSection(id)
    sectionRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  if (isLoading || !settings) {
    return (
      <div className="max-w-5xl mx-auto p-6">
        <div className="h-8 w-32 bg-muted animate-pulse rounded mb-6" />
        <div className="h-96 bg-muted animate-pulse rounded-lg" />
      </div>
    )
  }

  const useXyz = settings.use_xyz_buffer === 'true'

  return (
    <div className="max-w-5xl mx-auto p-6">
      <h1 className="text-xl font-bold mb-6 flex items-center gap-2">
        <SettingsIcon className="h-5 w-5" /> Settings
      </h1>

      <div className="grid grid-cols-[200px_1fr] gap-0 border rounded-lg overflow-hidden">
        {/* Sidebar */}
        <div className="bg-muted/30 border-r">
          {SECTIONS.map(s => (
            <button
              key={s.id}
              onClick={() => scrollTo(s.id)}
              className={`w-full text-left px-4 py-3 text-sm transition-colors ${
                activeSection === s.id
                  ? 'bg-blue-50 text-blue-700 border-l-2 border-l-blue-500 font-medium'
                  : 'text-muted-foreground hover:bg-muted/50'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-6 space-y-10 max-h-[calc(100vh-200px)] overflow-y-auto">
          {/* Safety Buffers */}
          <div ref={el => { sectionRefs.current['buffers'] = el }}>
            <h2 className="text-base font-semibold mb-4">Safety Buffer Configuration</h2>

            <div className="flex items-center justify-between mb-4 p-3 bg-muted/30 rounded-lg">
              <div>
                <div className="text-sm font-medium">Use XYZ-adjusted buffers</div>
                <div className="text-xs text-muted-foreground">Currently: {useXyz ? 'ABC×XYZ matrix' : 'ABC only (recommended)'}</div>
              </div>
              <Switch
                checked={useXyz}
                onCheckedChange={checked => saveMut.mutate({ key: 'use_xyz_buffer', value: String(checked) })}
              />
            </div>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Class</TableHead>
                  <TableHead>Buffer</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {['a', 'b', 'c'].map(cls => (
                  <SettingsBufferRow
                    key={cls}
                    label={cls.toUpperCase()}
                    settingKey={`buffer_${cls}`}
                    value={settings[`buffer_${cls}`] || (cls === 'a' ? '1.5' : cls === 'b' ? '1.3' : '1.1')}
                    onSave={(val) => saveMut.mutate({ key: `buffer_${cls}`, value: val })}
                    saving={saveMut.isPending}
                  />
                ))}
              </TableBody>
            </Table>

            <p className="text-xs text-muted-foreground mt-3">Changes take effect after next nightly sync. Per-item overrides are unaffected.</p>
          </div>

          {/* Lead Times */}
          <div ref={el => { sectionRefs.current['lead-times'] = el }}>
            <h2 className="text-base font-semibold mb-4">Lead Times</h2>
            {suppliers && suppliers.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Supplier</TableHead>
                    <TableHead className="text-right">Lead Time (days)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {suppliers.map((sup: any) => (
                    <TableRow key={sup.id}>
                      <TableCell className="font-medium">{sup.name}</TableCell>
                      <TableCell className="text-right">{sup.lead_time_days}d</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground">No suppliers configured.</p>
            )}
            <Button variant="link" className="mt-2 text-xs p-0" onClick={() => navigate('/suppliers')}>
              Manage suppliers →
            </Button>
          </div>

          {/* Analysis Defaults */}
          <div ref={el => { sectionRefs.current['analysis'] = el }}>
            <h2 className="text-base font-semibold mb-4">Analysis Defaults</h2>
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <span className="text-sm text-muted-foreground w-[140px]">Velocity type</span>
                <Select
                  value={settings.default_velocity_type || 'flat'}
                  onValueChange={v => saveMut.mutate({ key: 'default_velocity_type', value: v })}
                >
                  <SelectTrigger className="w-[200px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="flat">Flat (simple average)</SelectItem>
                    <SelectItem value="wma">WMA (weighted moving avg)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm text-muted-foreground w-[140px]">Default date range</span>
                <Select
                  value={settings.default_date_range || 'full_fy'}
                  onValueChange={v => saveMut.mutate({ key: 'default_date_range', value: v })}
                >
                  <SelectTrigger className="w-[200px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="full_fy">Full financial year</SelectItem>
                    <SelectItem value="6m">Last 6 months</SelectItem>
                    <SelectItem value="3m">Last 3 months</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-3">These are the default selections when opening SKU pages. You can still change them per-session.</p>
          </div>

          {/* Dead Stock */}
          <div ref={el => { sectionRefs.current['dead-stock'] = el }}>
            <h2 className="text-base font-semibold mb-4">Dead Stock Thresholds</h2>
            <div className="space-y-4">
              <SettingsNumberInput
                label="Dead stock after"
                suffix="days with no sales"
                settingKey="dead_stock_threshold_days"
                value={settings.dead_stock_threshold_days || '365'}
                onSave={(val) => saveMut.mutate({ key: 'dead_stock_threshold_days', value: val })}
                saving={saveMut.isPending}
              />
              <SettingsNumberInput
                label="Slow mover below"
                suffix="units/month velocity"
                settingKey="slow_mover_velocity_threshold"
                value={String(parseFloat(settings.slow_mover_velocity_threshold || '0.033') * 30)}
                onSave={(val) => saveMut.mutate({ key: 'slow_mover_velocity_threshold', value: String(parseFloat(val) / 30) })}
                saving={saveMut.isPending}
              />
            </div>
          </div>

          {/* Classification */}
          <div ref={el => { sectionRefs.current['classification'] = el }}>
            <h2 className="text-base font-semibold mb-4">Classification</h2>
            <div className="space-y-3 text-sm">
              <div>
                <div className="font-medium mb-1">ABC Classification (Revenue-based)</div>
                <div className="text-muted-foreground">A = top 80% of revenue · B = next 15% · C = remaining 5%</div>
              </div>
              <div>
                <div className="font-medium mb-1">XYZ Classification (Demand variability)</div>
                <div className="text-muted-foreground">X = CV &lt; 0.5 (stable) · Y = CV &lt; 1.0 (variable) · Z = CV ≥ 1.0 (sporadic)</div>
              </div>
              <p className="text-xs text-muted-foreground italic">These thresholds are engine constants and not configurable in V1.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// --- Helper components ---

function SettingsBufferRow({ label, settingKey, value, onSave, saving }: {
  label: string; settingKey: string; value: string; onSave: (v: string) => void; saving: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)

  if (!editing) {
    return (
      <TableRow>
        <TableCell className="font-medium">{label}-class</TableCell>
        <TableCell>{value}x</TableCell>
        <TableCell className="text-right">
          <Button variant="ghost" size="sm" className="text-xs" onClick={() => { setDraft(value); setEditing(true) }}>Edit</Button>
        </TableCell>
      </TableRow>
    )
  }

  return (
    <TableRow>
      <TableCell className="font-medium">{label}-class</TableCell>
      <TableCell>
        <Input type="number" step="0.1" min="1" max="3" value={draft} onChange={e => setDraft(e.target.value)} className="w-24 h-8" />
      </TableCell>
      <TableCell className="text-right space-x-1">
        <Button size="sm" className="h-7 text-xs" disabled={saving} onClick={() => { onSave(draft); setEditing(false) }}>
          <Check className="h-3 w-3 mr-1" /> Save
        </Button>
        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setEditing(false)}>Cancel</Button>
      </TableCell>
    </TableRow>
  )
}

function SettingsNumberInput({ label, suffix, settingKey, value, onSave, saving }: {
  label: string; suffix: string; settingKey: string; value: string; onSave: (v: string) => void; saving: boolean
}) {
  const [draft, setDraft] = useState(value)
  const changed = draft !== value

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-muted-foreground w-[140px]">{label}</span>
      <Input type="number" value={draft} onChange={e => setDraft(e.target.value)} className="w-24 h-8" />
      <span className="text-sm text-muted-foreground">{suffix}</span>
      {changed && (
        <Button size="sm" className="h-7 text-xs" disabled={saving} onClick={() => onSave(draft)}>
          Save
        </Button>
      )}
    </div>
  )
}
```

Write this to `src/dashboard/src/pages/Settings.tsx`.

- [ ] **Step 2: Verify Switch component exists**

Check if `src/dashboard/src/components/ui/switch.tsx` exists. If not, install it:

```bash
cd src/dashboard && npx shadcn-ui@latest add switch
```

- [ ] **Step 3: Build and verify**

```bash
cd src/dashboard && npm run build
```

Expected: Build succeeds (the page isn't routed yet, but it should compile).

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/src/pages/Settings.tsx
git commit -m "feat: add Settings page with safety buffers, lead times, analysis defaults"
```

---

### Task 9: App.tsx — Add Settings Route

**Files:**
- Modify: `src/dashboard/src/App.tsx`

- [ ] **Step 1: Add lazy import for Settings**

After the existing lazy imports (around line 12), add:

```tsx
const Settings = lazy(() => import('./pages/Settings'))
```

- [ ] **Step 2: Add route**

Inside the `<Route element={<Layout />}>` block, add before the closing `</Route>`:

```tsx
<Route path="/settings" element={<SuspenseWrapper><Settings /></SuspenseWrapper>} />
```

- [ ] **Step 3: Add dead-stock route if missing**

Check if `/brands/:categoryName/dead-stock` route exists. If present, no action needed.

- [ ] **Step 4: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/src/App.tsx
git commit -m "feat: add /settings route"
```

---

### Task 10: Layout — Grouped Navigation with Settings

**Files:**
- Modify: `src/dashboard/src/components/Layout.tsx`

- [ ] **Step 1: Read current Layout.tsx navigation items (lines 31-39)**

Current nav items are a flat array. We need to add grouping separators and the Settings link.

- [ ] **Step 2: Update nav items array**

Replace the current nav items (lines 31-39) with grouped structure:

```tsx
const navItems = [
  // Primary actions
  { path: '/', label: 'Home', icon: LayoutDashboard, exact: true },
  { path: '/brands', label: 'Brands', icon: Package, exact: true },
  { path: '/critical', label: 'Critical', icon: ShieldAlert },
  { path: '/po', label: 'Build PO', icon: ClipboardList },
  'separator' as const,
  // Data management
  { path: '/parties', label: 'Parties', icon: Users },
  { path: '/suppliers', label: 'Suppliers', icon: Truck },
  { path: '/overrides', label: 'Overrides', icon: Pencil },
  'separator' as const,
  // Settings
  { path: '/settings', label: 'Settings', icon: SettingsIcon },
]
```

- [ ] **Step 3: Add Settings icon import**

Add to the lucide-react import line:

```tsx
import { Settings as SettingsIcon } from 'lucide-react'
```

(May need to merge with existing imports — check for conflicts with the Settings page.)

- [ ] **Step 4: Update nav rendering to handle separators**

Replace the current nav link mapping with:

```tsx
{navItems.map((item, i) => {
  if (item === 'separator') {
    return <span key={`sep-${i}`} className="text-border mx-1">|</span>
  }
  const isActive = item.exact
    ? location.pathname === item.path
    : location.pathname.startsWith(item.path)
  return (
    <Link
      key={item.path}
      to={item.path}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
        isActive
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
      }`}
    >
      <item.icon className="h-4 w-4" />
      {item.label}
    </Link>
  )
})}
```

This is mostly the same as current rendering but adds the separator case.

- [ ] **Step 5: Build and verify**

```bash
cd src/dashboard && npm run build
```

Expected: Build succeeds. Open browser and verify navigation shows grouped items with separators and Settings link at the end.

- [ ] **Step 6: Commit**

```bash
git add src/dashboard/src/components/Layout.tsx
git commit -m "feat: group navigation with separators and add Settings link"
```

---

### Task 11: Settings Consumers — Analysis Defaults

**Files:**
- Modify: `src/dashboard/src/pages/SkuDetail.tsx`
- Modify: `src/dashboard/src/pages/CriticalSkus.tsx` (same pattern)
- Modify: `src/dashboard/src/pages/DeadStock.tsx` (same pattern — if it has velocity/date selectors)

**What changes:** Read `default_velocity_type` and `default_date_range` from settings to use as initial state values instead of hardcoded `'flat'` and `'full_fy'`. Apply the same pattern to all three pages that have these selectors.

- [ ] **Step 1: Add settings query import**

Add `fetchSettings` to the imports from `@/lib/api`.

- [ ] **Step 2: Fetch settings in SkuDetail**

Inside the SkuDetail component, add a settings query (near the other queries):

```tsx
const { data: appSettings } = useQuery({
  queryKey: ['settings'],
  queryFn: fetchSettings,
  staleTime: 5 * 60 * 1000,
})
```

- [ ] **Step 3: Initialize state from settings**

Find the velocity type state declaration (currently `useState<'flat' | 'wma'>('flat')` around line 215) and the date range preset state (currently `useState('full_fy')` around line 236).

Add a `useEffect` to set initial values from settings when they load:

```tsx
useEffect(() => {
  if (appSettings) {
    if (appSettings.default_velocity_type && velocityType === 'flat') {
      setVelocityType(appSettings.default_velocity_type as 'flat' | 'wma')
    }
    // Only apply default date range if user hasn't already changed it
    if (appSettings.default_date_range && rangePreset === 'full_fy' && appSettings.default_date_range !== 'full_fy') {
      setRangePreset(appSettings.default_date_range)
      const range = getPresetRange(appSettings.default_date_range)
      if (range) setAnalysisRange(range)
    }
  }
  // Only run once when settings first load
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [appSettings])
```

- [ ] **Step 4: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 5: Apply same pattern to CriticalSkus.tsx**

If `CriticalSkus.tsx` has a velocity type selector (it does — check for `useState<'flat' | 'wma'>`), add the same `fetchSettings` query and `useEffect` initialization pattern.

- [ ] **Step 6: Apply same pattern to DeadStock.tsx if applicable**

Check if `DeadStock.tsx` has velocity/date selectors. If so, apply the same pattern.

- [ ] **Step 7: Build and verify**

```bash
cd src/dashboard && npm run build
```

- [ ] **Step 8: Commit**

```bash
git add src/dashboard/src/pages/SkuDetail.tsx src/dashboard/src/pages/CriticalSkus.tsx src/dashboard/src/pages/DeadStock.tsx
git commit -m "feat: read analysis defaults from settings for initial state"
```

---

### Task 12: Final Build Verification

- [ ] **Step 1: Full build**

```bash
cd src/dashboard && npm run build
```

Expected: 0 errors, 0 warnings (TypeScript strict mode).

- [ ] **Step 2: Visual smoke test**

Start the API and frontend dev servers:
```bash
# Terminal 1: API
cd src && PYTHONPATH=. ./venv/Scripts/uvicorn api.main:app --reload --port 8000

# Terminal 2: Frontend
cd src/dashboard && npm run dev
```

Verify:
1. **Home page** — brand search works, 3 action cards show, priority brands table navigates to brand SKU page
2. **SKU table** — 7 columns: expand, status, Part No (bold mono), SKU name, stock, velocity, ABC badge
3. **Expanded row** — summary strip with channel velocity (W/O/S + total), stock & stockout, reorder section with intent selector
4. **Calculation tab** — 3 layers: verdict card, key assumptions (expanded), methodology (collapsed)
5. **Settings page** — sidebar nav, buffer config, lead times, analysis defaults, dead stock thresholds, classification info
6. **Navigation** — grouped with separators, Settings link at end

- [ ] **Step 3: Commit all remaining changes (if any)**

```bash
git status
# Add any remaining files
git add -A
git commit -m "feat: complete UI/UX audit implementation"
```

---

## Implementation Order

```
Task 1 (Migration)        → Run first, independent
Task 2 (Backend API)      → After Task 1
Task 3 (Frontend types)   → After Task 2
Task 4 (Column reorder)   → After Task 3
Task 5 (Summary strip)    → After Task 4 (same file)
Task 6 (Calc breakdown)   → After Task 3, parallel with 4-5
Task 7 (Home page)        → Independent, parallel with 4-6
Task 8 (Settings page)    → Independent, parallel with 4-7
Task 9 (Settings route)   → After Task 8
Task 10 (Nav grouping)    → After Task 9
Task 11 (Settings consumers) → After Tasks 8+4
Task 12 (Final verify)    → After all tasks
```

Tasks 4-5 are sequential (same file). Tasks 6, 7, 8 are parallel (different files). Tasks 9-11 depend on earlier work.
