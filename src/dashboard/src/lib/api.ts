import axios from 'axios'
import type { BrandMetrics, BrandSummary, SkuMetrics, DailyPosition, Transaction, SyncStatus, Party, Supplier, PoDataItem, BreakdownResponse, Override, OverrideCreate } from './types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
})

export const fetchBrands = (search?: string): Promise<BrandMetrics[]> =>
  api.get('/api/brands', { params: { search } }).then(r => r.data)

export const fetchBrandSummary = (): Promise<BrandSummary> =>
  api.get('/api/brands/summary').then(r => r.data)

export const fetchSkus = (categoryName: string, params?: Record<string, string | number | boolean>): Promise<SkuMetrics[]> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus`, { params }).then(r => r.data)

export const fetchPositions = (categoryName: string, itemName: string): Promise<DailyPosition[]> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus/${encodeURIComponent(itemName)}/positions`).then(r => r.data)

export const fetchTransactions = (categoryName: string, itemName: string, limit = 50): Promise<Transaction[]> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus/${encodeURIComponent(itemName)}/transactions`, { params: { limit } }).then(r => r.data)

export const fetchBreakdown = (categoryName: string, itemName: string, params?: { from_date?: string; to_date?: string }): Promise<BreakdownResponse> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/skus/${encodeURIComponent(itemName)}/breakdown`, { params }).then(r => r.data)

export const fetchPoData = (categoryName: string, params?: Record<string, string | number | boolean>): Promise<PoDataItem[]> =>
  api.get(`/api/brands/${encodeURIComponent(categoryName)}/po-data`, { params }).then(r => r.data)

export const exportPo = (data: Record<string, unknown>): Promise<Blob> =>
  api.post('/api/export/po', data, { responseType: 'blob' }).then(r => r.data)

export const fetchSyncStatus = (): Promise<SyncStatus> =>
  api.get('/api/sync/status').then(r => r.data)

export const fetchUnclassifiedParties = (): Promise<Party[]> =>
  api.get('/api/parties/unclassified').then(r => r.data)

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

export default api
