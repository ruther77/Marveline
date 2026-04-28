export type StockItemStatus = 'available' | 'reserved' | 'on_location' | 'damaged' | 'in_repair' | 'retired'

export interface StockItem {
  id: number
  product_id: number
  serial_number?: string
  status: StockItemStatus
  current_reservation_id?: number
  notes?: string
  created_at: string
}

export interface ProductStockDetail {
  product_id: number
  qty_available: number
  qty_reserved: number
  qty_on_location: number
  qty_damaged: number
  qty_in_repair: number
  qty_retired: number
  total: number
  items: StockItem[]
}

export interface ProductStockBatchResponse {
  items: ProductStockDetail[]
}

export interface StockItemHistoryEntry {
  movement_id: number
  movement_type: string
  scheduled_date: string
  actual_date?: string
  movement_status: string
  reservation_id?: number
  status_before?: string
  status_after?: string
  condition?: string
  condition_notes?: string
}

export interface StockItemHistory {
  stock_item_id: number
  product_id: number
  serial_number?: string
  current_status: string
  entries: StockItemHistoryEntry[]
}
