import axios from 'axios'
import type { BrandMetrics, BrandSummary, DashboardSummary, SkuCounts, SkuMetrics, SkuPage, DailyPosition, Transaction, SyncStatus, Party, Supplier, PoDataItem, BreakdownResponse, Override, OverrideCreate, ReorderIntent, SkuMatchResponse, CriticalSkusResponse, AuthUser, LoginResponse, SearchResults } from './types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
})

// ── Auth token interceptor ──
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export const fetchBrands = (search?: string): Promise<BrandMetrics[]> =>
  api.get('/api/brands', { params: { search } }).then(r => r.data)

export const fetchBrandSummary = (): Promise<BrandSummary> =>
  api.get('/api/brands/summary').then(r => r.data)

export const fetchDashboardSummary = (): Promise<DashboardSummary> =>
  api.get('/api/dashboard-summary').then(r => r.data)

export const fetchSkus = (categoryName: string, params?: Record<string, string | number | boolean>): Promise<SkuMetrics[]> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus`, { params }).then(r => r.data)

const EMPTY_SKU_COUNTS: SkuCounts = {
  urgent: 0,
  reorder: 0,
  healthy: 0,
  out_of_stock: 0,
  no_data: 0,
  dead_stock: 0,
}

function computeSkuCounts(items: SkuMetrics[]): SkuCounts {
  const counts = { ...EMPTY_SKU_COUNTS }
  for (const item of items) {
    const status = item.effective_status ?? item.reorder_status
    if (status in counts) {
      counts[status as keyof SkuCounts] += 1
    }
    if (item.is_dead_stock) {
      counts.dead_stock += 1
    }
  }
  return counts
}

export const fetchSkusPage = (
  categoryName: string,
  params?: Record<string, string | number | boolean>,
  pagination?: { limit?: number; offset?: number },
): Promise<SkuPage> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus`, {
    params: {
      ...(params || {}),
      paginated: true,
      limit: pagination?.limit ?? 100,
      offset: pagination?.offset ?? 0,
    },
  }).then(r => {
    const data = r.data as SkuPage | SkuMetrics[]
    const limit = pagination?.limit ?? 100
    const offset = pagination?.offset ?? 0

    // Backward compatibility: older API servers may still return a plain list.
    if (Array.isArray(data)) {
      return {
        items: data.slice(offset, offset + limit),
        total: data.length,
        offset,
        limit,
        counts: computeSkuCounts(data),
      }
    }

    return data
  })

export const fetchPositions = (categoryName: string, itemName: string): Promise<DailyPosition[]> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus/${encodeURIComponent(itemName)}/positions`).then(r => r.data)

export const fetchTransactions = (categoryName: string, itemName: string, limit = 50): Promise<Transaction[]> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus/${encodeURIComponent(itemName)}/transactions`, { params: { limit } }).then(r => r.data)

export const fetchBreakdown = (categoryName: string, itemName: string, params?: { from_date?: string; to_date?: string }): Promise<BreakdownResponse> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus/${encodeURIComponent(itemName)}/breakdown`, { params }).then(r => r.data)

export const fetchPoData = (categoryName: string, params?: Record<string, string | number | boolean>): Promise<PoDataItem[]> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/po-data`, { params }).then(r => r.data)

export const fetchCriticalSkus = (params?: Record<string, string | number | boolean>): Promise<CriticalSkusResponse> =>
  api.get('/api/critical-skus', { params }).then(r => r.data)

export const exportPo = (data: Record<string, unknown>): Promise<Blob> =>
  api.post('/api/export/po', data, { responseType: 'blob' }).then(r => r.data)

export const fetchSyncStatus = (): Promise<SyncStatus> =>
  api.get('/api/sync/status').then(r => r.data)

export const fetchUnclassifiedParties = (): Promise<Party[]> =>
  api.get('/api/parties/unclassified').then(r => r.data)

export const fetchAllParties = (params?: { channel?: string; search?: string }): Promise<(Party & { channel: string; classified_at: string | null })[]> =>
  api.get('/api/parties', { params }).then(r => r.data)

export const classifyParty = (tallyName: string, channel: string) =>
  api.post('/api/parties/classify', { tally_name: tallyName, channel }).then(r => r.data)

export const fetchSuppliers = (): Promise<Supplier[]> =>
  api.get('/api/suppliers').then(r => r.data)

export const createSupplier = (data: Record<string, unknown>): Promise<Supplier> =>
  api.post('/api/suppliers', data).then(r => r.data)

export const updateSupplier = (id: number, data: Record<string, unknown>): Promise<Supplier> =>
  api.put(`/api/suppliers/${id}`, data).then(r => r.data)

export const deleteSupplier = (id: number) =>
  api.delete(`/api/suppliers/${id}`).then(r => r.data)

// Hazardous
export const toggleHazardous = (stockItemName: string, isHazardous: boolean) =>
  api.patch(`/api/skus/${encodeURIComponent(stockItemName)}/hazardous`, { is_hazardous: isHazardous }).then(r => r.data)

// Reorder Intent
export const updateReorderIntent = (stockItemName: string, reorderIntent: ReorderIntent) =>
  api.patch(`/api/skus/${encodeURIComponent(stockItemName)}/reorder-intent`, { reorder_intent: reorderIntent }).then(r => r.data)

// XYZ Buffer Toggle
export const updateXyzBuffer = (stockItemName: string, useXyzBuffer: boolean | null) =>
  api.patch(`/api/skus/${encodeURIComponent(stockItemName)}/xyz-buffer`, { use_xyz_buffer: useXyzBuffer }).then(r => r.data)

// Overrides
export const fetchOverrides = (params?: Record<string, string | boolean>): Promise<Override[]> =>
  api.get('/api/overrides', { params }).then(r => r.data)

export const createOverride = (data: OverrideCreate): Promise<Override> =>
  api.post('/api/overrides', data).then(r => r.data)

export const deleteOverride = (id: number, reason: string, performed_by = 'user') =>
  api.delete(`/api/overrides/${id}`, { data: { reason, performed_by } }).then(r => r.data)

export const reviewOverride = (id: number, data: { action: 'keep' | 'remove'; reason?: string; new_value?: number; performed_by?: string }) =>
  api.post(`/api/overrides/${id}/review`, data).then(r => r.data)

// Settings
export const fetchSettings = (): Promise<Record<string, string>> =>
  api.get('/api/settings').then(r => r.data)

export const updateSetting = (key: string, value: string) =>
  api.put(`/api/settings/${key}`, { value }).then(r => r.data)

export const matchSkusForPo = (data: {
  sku_names: string[]
  lead_time?: number
  coverage_days?: number
  buffer?: number
  from_date?: string
  to_date?: string
}): Promise<SkuMatchResponse> =>
  api.post('/api/po-data/match', data).then(r => r.data)

// ── Auth ──
export const login = (username: string, password: string): Promise<LoginResponse> =>
  api.post('/api/auth/login', { username, password }).then(r => r.data)

export const fetchMe = (): Promise<AuthUser> =>
  api.get('/api/auth/me').then(r => r.data)

export const changePassword = (currentPassword: string, newPassword: string) =>
  api.put('/api/auth/change-password', { current_password: currentPassword, new_password: newPassword }).then(r => r.data)

// ── Users (admin) ──
export const fetchUsers = () =>
  api.get('/api/users').then(r => r.data)

export const createUser = (data: { username: string; password: string; role: string }) =>
  api.post('/api/users', data).then(r => r.data)

export const updateUser = (id: number, data: { role?: string; is_active?: boolean }) =>
  api.put(`/api/users/${id}`, data).then(r => r.data)

export const resetUserPassword = (id: number, newPassword: string) =>
  api.put(`/api/users/${id}/reset-password`, { new_password: newPassword }).then(r => r.data)

export const fetchSearch = (q: string, scope?: string): Promise<SearchResults> =>
  api.get('/api/search', { params: { q, scope } }).then(r => r.data)

export default api
