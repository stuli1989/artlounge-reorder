export type ReorderStatus = 'urgent' | 'reorder' | 'healthy' | 'out_of_stock' | 'lost_sales' | 'dead_stock' | 'no_data'
export type ReorderIntent = 'must_stock' | 'normal' | 'do_not_reorder'

export type AbcClass = 'A' | 'B' | 'C'
export type XyzClass = 'X' | 'Y' | 'Z'
export type TrendDirection = 'up' | 'down' | 'flat'

export interface BrandMetrics {
  category_name: string
  total_skus: number
  in_stock_skus: number
  out_of_stock_skus: number
  urgent_skus: number
  reorder_skus: number
  healthy_skus: number
  no_data_skus: number
  avg_days_to_stockout: number | null
  dead_stock_skus: number
  slow_mover_skus: number
  primary_supplier: string | null
  supplier_lead_time: number | null
  a_class_skus: number
  b_class_skus: number
  c_class_skus: number
  inactive_skus: number
  computed_at: string
}

export interface BrandSummary {
  total_brands: number
  brands_with_urgent: number
  brands_with_reorder: number
  total_skus_out_of_stock: number
  total_dead_stock_skus: number
  total_slow_mover_skus: number
  total_a_class_skus: number
  total_b_class_skus: number
  total_c_class_skus: number
  total_inactive_skus: number
}

export interface SkuMetrics {
  stock_item_name: string
  part_no: string | null
  is_hazardous: boolean
  category_name: string
  current_stock: number
  wholesale_velocity: number
  online_velocity: number
  store_velocity: number
  total_velocity: number
  total_in_stock_days: number
  velocity_start_date: string | null
  velocity_end_date: string | null
  days_to_stockout: number | null
  estimated_stockout_date: string | null
  last_import_date: string | null
  last_import_qty: number | null
  last_import_supplier: string | null
  reorder_status: ReorderStatus
  reorder_qty_suggested: number | null
  computed_at: string
  // Override effective values
  effective_stock: number
  effective_wholesale_velocity: number
  effective_online_velocity: number
  effective_store_velocity: number
  effective_velocity: number
  effective_days_to_stockout: number | null
  effective_status: ReorderStatus
  effective_suggested_qty: number | null
  has_stock_override: boolean
  has_velocity_override: boolean
  has_note: boolean
  stock_override_stale: boolean
  velocity_override_stale: boolean
  hold_from_po: boolean
  last_sale_date: string | null
  days_since_last_sale: number | null
  total_zero_activity_days: number
  is_dead_stock: boolean
  reorder_intent: ReorderIntent
  is_slow_mover: boolean
  // V2 fields
  abc_class: AbcClass | null
  xyz_class: XyzClass | null
  demand_cv: number | null
  total_revenue: number
  wma_wholesale_velocity: number
  wma_online_velocity: number
  wma_total_velocity: number
  trend_direction: TrendDirection
  trend_ratio: number | null
  safety_buffer: number
  use_xyz_buffer: boolean | null
}

export interface SkuCounts {
  urgent: number
  reorder: number
  healthy: number
  out_of_stock: number
  no_data: number
  dead_stock: number
}

export interface SkuPage {
  items: SkuMetrics[]
  total: number
  offset: number
  limit: number
  counts: SkuCounts
}

export interface DailyPosition {
  position_date: string
  opening_qty: number
  closing_qty: number
  inward_qty: number
  outward_qty: number
  wholesale_out: number
  online_out: number
  store_out: number
  is_in_stock: boolean
}

export interface Transaction {
  txn_date: string
  quantity: number
  is_inward: boolean
  channel: string
  voucher_type: string
  voucher_number: string
  sale_order_code: string | null
  facility: string | null
  entity_type: string | null
}

export interface SyncStatus {
  last_sync_completed: string | null
  status: string
  categories_synced: number
  items_synced: number
  transactions_synced: number
  new_parties_found: number
  freshness: 'fresh' | 'stale' | 'critical'
  unclassified_parties_count: number
}

export interface Party {
  name: string
  party_group: string | null
  created_at: string
  transaction_count: number
}

export interface Supplier {
  id: number
  name: string
  tally_party: string
  lead_time_sea: number | null
  lead_time_air: number | null
  lead_time_default: number
  currency: string
  min_order_value: number | null
  typical_order_months: number | null
  notes: string
  buffer_override: number | null
  lead_time_demand_mode: string
}

export interface OverrideInfo {
  id: number
  value: number | null
  note: string
  hold_from_po: boolean
  is_stale: boolean
  stale_since: string | null
  computed_at_creation: number | null
  computed_latest: number | null
  drift_pct: number | null
  created_at: string | null
  created_by: string
}

export interface Override {
  id: number
  stock_item_name: string
  field_name: string
  override_value: number | null
  note: string
  hold_from_po: boolean
  created_by: string
  created_at: string
  expires_at: string | null
  is_active: boolean
  is_stale: boolean
  stale_since: string | null
  computed_value_at_creation: number | null
  computed_value_latest: number | null
  drift_pct: number | null
  last_reviewed_at: string | null
  // Joined from sku_metrics
  computed_current_stock?: number | null
  computed_total_velocity?: number | null
  computed_wholesale_velocity?: number | null
  computed_online_velocity?: number | null
  category_name?: string
}

export interface OverrideCreate {
  stock_item_name: string
  field_name: string
  override_value?: number | null
  note: string
  hold_from_po?: boolean
  created_by?: string
  expires_at?: string | null
}

export interface BreakdownVelocityChannel {
  total_units: number
  daily_velocity: number
  monthly_velocity: number
}

export interface BreakdownInStockPeriod {
  from: string
  to: string
  days: number
}

export interface BreakdownTransactionRow {
  channel: string
  direction: string
  count: number
  total_qty: number
  included_in_demand: boolean
  explanation: string
}

export interface BreakdownResponse {
  stock_item_name: string
  data_source: {
    closing_balance_from_ledger: number | null
    last_computed: string | null
    data_as_of: string | null
    fy_period: string
    overrides: Record<string, OverrideInfo>
  }
  effective_values: {
    current_stock: number
    stock_source: 'override' | 'computed'
    total_velocity: number
    velocity_source: 'override' | 'computed'
    wholesale_velocity: number
    online_velocity: number
    store_velocity: number
  }
  position_reconstruction: {
    implied_opening: number
    total_inward: number
    total_outward: number
    closing_balance: number | null
    formula: string
  }
  transaction_summary: BreakdownTransactionRow[]
  date_range: {
    from_date: string
    to_date: string
    total_days_in_range: number
  }
  velocity: {
    in_stock_days: number
    out_of_stock_days: number
    in_stock_pct: number
    in_stock_periods: BreakdownInStockPeriod[]
    out_of_stock_exclusion_reason: string
    wholesale: BreakdownVelocityChannel
    online: BreakdownVelocityChannel
    store: BreakdownVelocityChannel
    total: BreakdownVelocityChannel
    formula: string
    confidence: 'high' | 'medium' | 'low'
    confidence_reason: string
  }
  stockout: {
    current_stock: number
    daily_burn_rate: number
    days_to_stockout: number | null
    estimated_stockout_date: string | null
    formula: string
  }
  reorder: {
    supplier_name: string | null
    supplier_lead_time: number
    buffer_multiplier: number
    buffer_mode: 'abc_only' | 'abc_xyz'
    use_xyz_buffer: boolean | null
    suggested_qty: number | null
    formula: string
    status: string
    status_reason: string
    status_thresholds: string
  }
}

export interface DashboardSummaryBrand {
  category_name: string
  urgent_skus: number
  reorder_skus: number
  a_class_skus: number
  b_class_skus: number
  avg_days_to_stockout: number | null
  a_urgent_skus: number
}

export interface DashboardSummary {
  // ABC x Status
  total_active_skus: number
  a_urgent: number
  a_reorder: number
  b_urgent: number
  b_reorder: number
  c_urgent: number
  c_reorder: number
  // Status totals
  total_urgent: number
  total_reorder: number
  total_healthy: number
  total_out_of_stock: number
  // Trends
  trending_up: number
  trending_down: number
  trending_flat: number
  // Brand summary
  total_brands: number
  brands_with_urgent: number
  brands_with_reorder: number
  total_skus_out_of_stock: number
  total_dead_stock_skus: number
  total_slow_mover_skus: number
  total_a_class_skus: number
  total_b_class_skus: number
  total_c_class_skus: number
  total_inactive_skus: number
  // Top priority brands
  top_brands: DashboardSummaryBrand[]
}

export interface PoDataItem {
  stock_item_name: string
  part_no: string | null
  is_hazardous: boolean
  current_stock: number
  total_velocity: number
  days_to_stockout: number | null
  reorder_status: ReorderStatus
  suggested_qty: number | null
  lead_time: number
  coverage_period: number
  buffer: number
  sku_buffer?: number
  reorder_intent: ReorderIntent
  abc_class: AbcClass | null
  trend_direction: TrendDirection | null
  total_in_stock_days: number
  category_name?: string
}

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

export interface CriticalItem {
  stock_item_name: string
  category_name: string
  current_stock: number
  total_velocity: number
  wholesale_velocity: number
  online_velocity: number
  days_of_stock: number | null
  days_to_stockout: number | null
  reorder_status: string
  safety_buffer: number
  abc_class: string | null
  xyz_class: string | null
  is_hazardous: boolean
  reorder_intent: string
  part_no: string | null
  wma_total_velocity: number
  wma_wholesale_velocity: number
}

export interface CriticalSkusResponse {
  items: CriticalItem[]
  total: number
}

export type UserRole = 'admin' | 'purchaser' | 'viewer'

export interface AuthUser {
  id: number
  username: string
  role: UserRole
}

export interface LoginResponse {
  token: string
  user: AuthUser
}

// ── Universal Search ──

export interface SearchBrandResult {
  category_name: string
  total_skus: number
  urgent_skus: number
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
