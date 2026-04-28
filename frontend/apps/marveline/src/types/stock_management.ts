// Types alignés sur app/schemas/stock_management.py

// ── Inventaire physique ────────────────────────────────────────────────────

export interface CountingEntry {
  product_id: number
  counted_quantity: number
}

export interface InventaireSessionResponse {
  id: number
  tenant_id: number
  status: 'in_progress' | 'completed'
  started_at: string
  completed_at: string | null
  created_by: number
  variances_json: Record<string, { expected: number; counted: number; delta: number }> | null
}

// ── Ajustements manuels ────────────────────────────────────────────────────

export interface StockAdjustmentCreate {
  product_id: number
  delta: number
  reason: string
}

export interface StockAdjustmentResponse {
  id: number
  tenant_id: number
  product_id: number
  delta: number
  reason: string
  created_at: string
  created_by: number
}

// ── Niveaux stock ──────────────────────────────────────────────────────────

export type StockLevel = 'critical' | 'low' | 'ok' | 'overstock'

export interface StockLevelItem {
  product_id: number
  product_name: string
  stock_quantity: number
  available_quantity: number
  level: StockLevel
  low_stock_threshold: number
}

// ── Réassort ───────────────────────────────────────────────────────────────

export interface ReorderItem {
  product_id: number
  product_name: string
  available_quantity: number
  low_stock_threshold: number
  deficit: number
}

export interface ReorderRequestItem {
  product_id: number
  quantity: number
}

export interface ReorderRequest {
  items: ReorderRequestItem[]
  supplier_id?: number
  notes?: string
}

export interface ReorderResponse {
  created: number
  message: string
}

// ── Couverture stock ────────────────────────────────────────────────────────

export type StockCoverageStatus = 'critical' | 'low' | 'ok' | 'good'

export interface StockCoverageItem {
  product_id: number
  product_name: string
  sku: string
  available_qty: number
  total_qty: number
  movements_30d: number
  avg_daily_movements: number
  days_of_coverage: number | null
  rotation_rate: number
  status: StockCoverageStatus
}

export interface StockCoverageResponse {
  items: StockCoverageItem[]
  computed_at: string
}
