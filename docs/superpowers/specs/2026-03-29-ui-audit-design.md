# UI Audit & Fix-Up — Design Spec

## Problem

After the Unicommerce migration and status rename, the UI has accumulated inconsistencies: wrong buffer defaults in Settings, incomplete status filters, overflow issues, stale labels, and unverified recalculation triggers. This is a comprehensive fix-up pass.

## 7 Workstreams

### 1. Buffer Settings Mismatch (HIGH)

Settings page reads/writes `buffer_a`/`buffer_b`/`buffer_c` but DB only has XYZ matrix keys (`buffer_ax` through `buffer_cz`). Engine in ABC-only mode looks up `buffer_a`, doesn't find it, silently falls back to 1.3. Settings UI shows wrong fallbacks (1.5/1.0/0.5).

**Fix:**
- Seed `buffer_a=1.3`, `buffer_b=1.2`, `buffer_c=1.1` in DB if missing (add to uc_004 migration or Settings API)
- Fix Settings.tsx fallbacks from 1.5/1.0/0.5 to 1.3/1.2/1.1
- When `use_xyz_buffer=true`, Settings should show the 3×3 matrix; when false, show ABC-only fields
- Verify engine `compute_safety_buffer()` uses the correct keys in both modes

### 2. Dead Stock / Slow Mover Threshold Fallbacks

- `skus.py` line 161: dead stock fallback `"30"` → `"90"` (match pipeline + DB)
- `Settings.tsx` line 65: dead stock fallback `'30'` → `'90'`
- Verify slow mover threshold consistent (0.1 units/day = 3 units/month)

### 3. Status Filter Labels

`SkuDetail.tsx`, `CriticalSkus.tsx`: filter dropdowns missing statuses. Add complete set:
- All Statuses, Lost Sales, Urgent Only, Urgent & Reorder, Reorder Only, Healthy, Out of Stock, Dead Stock

### 4. Table Overflow

`CalculationBreakdown.tsx`: Methodology & Formulas tables overflow container on narrow screens. Wrap tables in `overflow-x: auto` div.

### 5. Parties → Channel Rules

- `Layout.tsx`, `MobileLayout.tsx`: nav label "Parties" → "Channel Rules"
- `PartyClassification.tsx`: page title update
- Alert text: "unclassified parties" → "unclassified channels"
- Route stays `/parties`

### 6. Sortable Columns

`SkuDetail.tsx`: make table headers clickable to sort. Columns: Status, Part No, Stock, Velocity, Days Left, ABC. Click toggles asc/desc. Current sort column gets an arrow indicator.

### 7. Recalculation Audit

Verify these trigger background recomputation:
- Override create/delete → targeted_recompute ✓ (channel_rules.py)
- Reorder intent change → targeted_recompute (verify in skus.py)
- Supplier lead time change → recalculate_buffers ✓ (suppliers.py — only on buffer_override change, NOT on lead time change — needs fix)
- Settings change → recalculate_buffers/pipeline (verify all relevant keys trigger)
- XYZ buffer toggle per-SKU → recalculate_buffers (verify in skus.py)

## Files Changed

| File | Changes |
|------|---------|
| `src/api/routes/skus.py` | Fix dead stock fallback, verify intent recalc |
| `src/api/routes/suppliers.py` | Trigger recalc on lead_time change |
| `src/api/routes/settings.py` | Seed missing buffer_a/b/c keys, verify recalc triggers |
| `src/dashboard/src/pages/Settings.tsx` | Fix buffer fallbacks, fix dead stock fallback, show ABC vs ABC×XYZ matrix |
| `src/dashboard/src/pages/SkuDetail.tsx` | Complete status filters, sortable columns |
| `src/dashboard/src/pages/CriticalSkus.tsx` | Complete status filters |
| `src/dashboard/src/pages/PartyClassification.tsx` | Rename title |
| `src/dashboard/src/components/Layout.tsx` | Rename nav label + alert text |
| `src/dashboard/src/components/mobile/MobileLayout.tsx` | Rename nav label |
| `src/dashboard/src/components/CalculationBreakdown.tsx` | Fix table overflow |
