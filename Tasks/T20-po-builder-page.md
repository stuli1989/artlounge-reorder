# T20: PO Builder Page + Party Classification Page

## Prerequisites
- T17 (React scaffolding)
- T16 (PO + Party API endpoints exist)

## Objective
Build the PO Builder page (generate purchase orders with adjustable settings and Excel export) and the Party Classification page.

## Design System
Use shadcn/ui: `Card`, `Table`, `Slider`, `Select`, `Checkbox`, `Input`, `Button`, `Switch`, `Label`.

## Files to Create/Modify

### 1. `dashboard/src/pages/PoBuilder.tsx`

Route: `/brands/:categoryName/po`

#### Layout Structure

**Header:**
```
Purchase Order — Speedball Art Products LLC
```

**Settings Bar (shadcn Card with form controls):**

| Setting | Control | Default |
|---------|---------|---------|
| Lead Time | Select: Sea Freight (180d) / Air Freight (30d) / Custom | Supplier default |
| Safety Buffer | Slider: 1.0x — 2.0x (step 0.1) | 1.3x |
| Include "warning" items | Switch toggle | Yes |
| Include "OK" items | Switch toggle | No |

Changing any setting → recalculates suggested quantities by re-fetching:
`GET /api/brands/{cat}/po-data?lead_time=X&buffer=Y&include_warning=true`

**Editable Table:**

| Column | Editable? | Notes |
|--------|-----------|-------|
| Include | Checkbox | Yes — uncheck to exclude from PO |
| SKU Name | No | Text |
| Current Stock | No | Integer |
| Velocity (/mo) | No | total_velocity × 30 |
| Days Left | No | Integer or "OUT" |
| Suggested Qty | No | Recalculates with settings |
| Order Qty | **Yes** — number input | Defaults to suggested_qty |
| Notes | **Yes** — text input | Free text |

**Footer:**
- Total Items: count of checked rows
- Total Order Quantity: sum of order_qty for checked rows
- "Export as Excel" button (shadcn `Button`)

#### Excel Export Flow
1. User clicks "Export as Excel"
2. Collect all checked rows with their order_qty and notes
3. POST to `/api/export/po` with category_name, supplier, lead_time, buffer, items
4. Receive blob response
5. Create download link and trigger download:
```typescript
const blob = await exportPo(payload)
const url = window.URL.createObjectURL(new Blob([blob]))
const link = document.createElement('a')
link.href = url
link.setAttribute('download', `PO-${brand}-${date}.xlsx`)
document.body.appendChild(link)
link.click()
link.remove()
```

### 2. `dashboard/src/pages/PartyClassification.tsx`

Route: `/parties`

Simple page for classifying unclassified parties.

**Layout:**
- Header: "Party Classification"
- Count: "3 parties need classification"
- Table of unclassified parties:

| Column | Notes |
|--------|-------|
| Party Name | tally_name |
| Tally Group | tally_parent (Sundry Debtors, etc.) |
| Channel | Select dropdown with all 6 channel options |
| Action | "Save" button |

Channel options in dropdown:
- supplier — International brand you import from
- wholesale — Shops/distributors that buy from you
- online — E-commerce platform
- store — Own retail store
- internal — Accounting entries
- ignore — System adjustments

On "Save":
- POST to `/api/parties/classify` with tally_name and selected channel
- Remove row from list
- Show success toast/message

Data from `GET /api/parties/unclassified`

### 3. Update `dashboard/src/components/Layout.tsx`

Add warning banner that appears when unclassified parties exist:
```tsx
// Fetch sync status on mount
// If unclassified_parties_count > 0, show Alert:
// "⚠ {count} new parties need classification. Velocity calculations may be incomplete."
// With link/button to /parties page
```

Use shadcn `Alert` with variant="warning" or custom amber styling.

### 4. `dashboard/src/pages/SupplierManagement.tsx`

Route: `/suppliers`

Simple CRUD page for managing suppliers and their lead times.

**Layout:**
- Header: "Supplier Management"
- "Add Supplier" button (opens inline form or modal)
- Table of all suppliers:

| Column | Notes |
|--------|-------|
| Name | Supplier display name |
| Tally Party | Corresponding Tally ledger name |
| Sea Lead Time | Days (editable) |
| Air Lead Time | Days (editable) |
| Default Lead Time | Sea or Air (select) |
| Currency | USD/EUR/GBP etc. |
| Notes | Free text |
| Actions | Edit / Delete buttons |

**Add/Edit form fields:**
- Name (required, text)
- Tally Party (text — match to Tally ledger name)
- Sea Freight Lead Time (number, days)
- Air Freight Lead Time (number, days)
- Default Lead Time (number, days)
- Currency (text, default "USD")
- Min Order Value (number, optional)
- Typical Order Months (number, optional)
- Notes (textarea)

**Delete:** Confirm dialog. Show error if supplier is in use by brands.

Data from `GET /api/suppliers`, mutations via POST/PUT/DELETE.

### 5. Update `dashboard/src/App.tsx` (routing)

Add route for supplier management:
```tsx
<Route path="/suppliers" element={<SupplierManagement />} />
```

Add navigation link in Layout header or sidebar.

## Acceptance Criteria
- [ ] PO settings bar recalculates on change (lead time, buffer, include toggles)
- [ ] Order Qty column is editable, defaults to suggested
- [ ] Include checkboxes work, footer totals update in real-time
- [ ] Excel export downloads a .xlsx file with correct filename
- [ ] Party classification shows unclassified parties
- [ ] Channel dropdown has all 6 valid options
- [ ] Saving classification removes party from list
- [ ] Warning banner appears in Layout when unclassified parties exist
- [ ] Banner links to /parties page
- [ ] Supplier list page shows all suppliers with lead times
- [ ] Can add new supplier with required field validation
- [ ] Can edit existing supplier lead times and details
- [ ] Delete blocked with error message if supplier is in use
- [ ] Navigation includes link to supplier management
