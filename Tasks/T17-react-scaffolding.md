# T17: React App Scaffolding

## Prerequisites
- T14 (FastAPI backend exists to connect to)

## Objective
Set up the React frontend with Vite, TypeScript, shadcn/ui design system, and routing.

## Design System: shadcn/ui

Use **shadcn/ui** as the design system. It provides high-quality, accessible, customizable components built on Radix UI + Tailwind CSS. This gives us a professional, consistent look without custom CSS.

## Setup Steps

### 1. Initialize Vite + React + TypeScript
```bash
cd dashboard
npm create vite@latest . -- --template react-ts
npm install
```

### 2. Install Tailwind CSS
```bash
npm install -D tailwindcss @tailwindcss/vite
```

### 3. Install and configure shadcn/ui
```bash
npx shadcn@latest init
```
Choose: TypeScript, Default style, Neutral base color, CSS variables.

### 4. Add shadcn components we'll need
```bash
npx shadcn@latest add button card table badge input select tabs separator
npx shadcn@latest add dropdown-menu dialog checkbox slider tooltip
npx shadcn@latest add alert sheet command
```

### 5. Install additional dependencies
```bash
npm install react-router-dom axios recharts @tanstack/react-query @tanstack/react-table lucide-react
```

## Files to Create

### 1. `dashboard/src/main.tsx`
Standard React entry with React Query provider and Router.

### 2. `dashboard/src/App.tsx`
Router setup with three main routes:
```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import BrandOverview from './pages/BrandOverview'
import SkuDetail from './pages/SkuDetail'
import PoBuilder from './pages/PoBuilder'
import PartyClassification from './pages/PartyClassification'

// Routes:
// /           -> BrandOverview
// /brands/:name/skus  -> SkuDetail
// /brands/:name/po    -> PoBuilder
// /parties            -> PartyClassification
```

### 3. `dashboard/src/lib/api.ts`
Axios API client:
```typescript
import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
})

export const fetchBrands = (search?: string) =>
  api.get('/api/brands', { params: { search } }).then(r => r.data)

export const fetchBrandSummary = () =>
  api.get('/api/brands/summary').then(r => r.data)

export const fetchSkus = (categoryName: string, params?: Record<string, any>) =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus`, { params }).then(r => r.data)

export const fetchPositions = (categoryName: string, itemName: string) =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus/${encodeURIComponent(itemName)}/positions`).then(r => r.data)

export const fetchTransactions = (categoryName: string, itemName: string, limit = 50) =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus/${encodeURIComponent(itemName)}/transactions`, { params: { limit } }).then(r => r.data)

export const fetchPoData = (categoryName: string, params?: Record<string, any>) =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/po-data`, { params }).then(r => r.data)

export const exportPo = (data: any) =>
  api.post('/api/export/po', data, { responseType: 'blob' }).then(r => r.data)

export const fetchSyncStatus = () =>
  api.get('/api/sync/status').then(r => r.data)

export const fetchUnclassifiedParties = () =>
  api.get('/api/parties/unclassified').then(r => r.data)

export const classifyParty = (tallyName: string, channel: string) =>
  api.post('/api/parties/classify', { tally_name: tallyName, channel }).then(r => r.data)

export default api
```

### 4. `dashboard/src/lib/types.ts`
TypeScript interfaces for all API responses:
```typescript
export interface BrandMetrics {
  category_name: string
  total_skus: number
  in_stock_skus: number
  out_of_stock_skus: number
  critical_skus: number
  warning_skus: number
  ok_skus: number
  no_data_skus: number
  avg_days_to_stockout: number | null
  primary_supplier: string | null
  supplier_lead_time: number | null
}

export interface SkuMetrics {
  stock_item_name: string
  category_name: string
  current_stock: number
  wholesale_velocity: number
  online_velocity: number
  total_velocity: number
  total_in_stock_days: number
  days_to_stockout: number | null
  estimated_stockout_date: string | null
  last_import_date: string | null
  last_import_qty: number | null
  last_import_supplier: string | null
  reorder_status: 'critical' | 'warning' | 'ok' | 'out_of_stock' | 'no_data'
  reorder_qty_suggested: number | null
}

export interface DailyPosition { ... }
export interface Transaction { ... }
export interface SyncStatus { ... }
export interface Party { ... }
export type ReorderStatus = 'critical' | 'warning' | 'ok' | 'out_of_stock' | 'no_data'
```

### 5. `dashboard/src/components/Layout.tsx`
Shell layout with:
- Header: "Art Lounge — Stock Intelligence"
- Sync status indicator (green/amber/red dot + timestamp)
- Warning banner for unclassified parties (if any)
- Tab navigation: Brands | SKU Detail | PO Builder
- Content area (Outlet)

Use shadcn components: `Button`, `Badge`, `Alert`, `Tabs`.

### 6. Stub page components:
- `dashboard/src/pages/BrandOverview.tsx` — placeholder "Brand Overview"
- `dashboard/src/pages/SkuDetail.tsx` — placeholder "SKU Detail"
- `dashboard/src/pages/PoBuilder.tsx` — placeholder "PO Builder"
- `dashboard/src/pages/PartyClassification.tsx` — placeholder "Party Classification"

## Acceptance Criteria
- [ ] `npm run dev` starts the React app on port 5173
- [ ] Router works: /, /brands/:name/skus, /brands/:name/po, /parties
- [ ] shadcn/ui components installed and usable
- [ ] API client configured with all endpoints
- [ ] TypeScript types defined for all API responses
- [ ] Layout shows header with app name and navigation tabs
- [ ] All 4 page stubs render without errors
- [ ] `npm run build` produces a production build in `dashboard/dist/`
