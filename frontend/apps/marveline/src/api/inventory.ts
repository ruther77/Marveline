import { api } from './fetchClient'
import type {
  InventoryMovement,
  InventoryMovementListItem,
  MovementStats,
  MovementType,
  MovementStatus,
  CreateMovementRequest,
  UpdateMovementRequest,
  MovementItem,
} from '../types/inventory'
import type { ProductStockBatchResponse, ProductStockDetail, StockItemHistory, PaginatedResponse } from '@/types'

export const inventoryApi = {
  listMovements: async (params?: {
    skip?: number
    limit?: number
    movement_type?: MovementType
    status?: MovementStatus
    event_id?: number
    reservation_id?: number
    product_id?: number
    start_date?: string
    end_date?: string
  }): Promise<PaginatedResponse<InventoryMovementListItem>> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.movement_type) p.movement_type = params.movement_type
    if (params?.status) p.status = params.status
    if (params?.event_id) p.event_id = String(params.event_id)
    if (params?.reservation_id) p.reservation_id = String(params.reservation_id)
    if (params?.product_id) p.product_id = String(params.product_id)
    if (params?.start_date) p.start_date = params.start_date
    if (params?.end_date) p.end_date = params.end_date
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedResponse<InventoryMovementListItem>>(`/inventory-movements?${qs}`)
  },

  getLateMovements: async (): Promise<InventoryMovementListItem[]> => {
    const data = await api.get<InventoryMovementListItem[] | { items?: InventoryMovementListItem[]; data?: InventoryMovementListItem[] }>(
      '/inventory-movements/late'
    )
    if (Array.isArray(data)) return data
    const obj = data as { items?: InventoryMovementListItem[]; data?: InventoryMovementListItem[] }
    return obj.items || obj.data || []
  },

  getPendingInspections: async (): Promise<InventoryMovementListItem[]> => {
    const data = await api.get<InventoryMovementListItem[] | { items?: InventoryMovementListItem[]; data?: InventoryMovementListItem[] }>(
      '/inventory-movements/pending-inspections'
    )
    if (Array.isArray(data)) return data
    const obj = data as { items?: InventoryMovementListItem[]; data?: InventoryMovementListItem[] }
    return obj.items || obj.data || []
  },


  getStatistics: async (startDate?: string, endDate?: string): Promise<MovementStats> => {
    const p: Record<string, string> = {}
    if (startDate) p.start_date = startDate
    if (endDate) p.end_date = endDate
    const qs = new URLSearchParams(p).toString()
    const path = qs ? `/inventory-movements/statistics?${qs}` : '/inventory-movements/statistics'
    return api.get<MovementStats>(path)
  },

  getMovement: async (id: number): Promise<InventoryMovement> => {
    return api.get<InventoryMovement>(`/inventory-movements/${id}`)
  },

  createMovement: async (movement: CreateMovementRequest): Promise<InventoryMovement> => {
    return api.post<InventoryMovement>('/inventory-movements', movement)
  },

  updateMovement: async (id: number, movement: UpdateMovementRequest): Promise<InventoryMovement> => {
    return api.patch<InventoryMovement>(`/inventory-movements/${id}`, movement)
  },

  deleteMovement: async (id: number): Promise<void> => {
    await api.delete(`/inventory-movements/${id}`)
  },

  completeMovement: async (id: number): Promise<InventoryMovement> => {
    return api.patch<InventoryMovement>(`/inventory-movements/${id}/complete`)
  },

  // Items
  addItem: async (
    movementId: number,
    item: {
      event_item_id?: number
      product_id?: number
      variant_id?: number
      quantity_expected: number
      condition?: string
      condition_notes?: string
    }
  ): Promise<MovementItem> => {
    return api.post<MovementItem>(`/inventory-movements/${movementId}/items`, item)
  },

  updateItem: async (
    movementId: number,
    itemId: number,
    item: {
      quantity_actual?: number
      condition?: string
      condition_notes?: string
    }
  ): Promise<MovementItem> => {
    return api.patch<MovementItem>(`/inventory-movements/${movementId}/items/${itemId}`, item)
  },

  removeItem: async (movementId: number, itemId: number): Promise<void> => {
    await api.delete(`/inventory-movements/${movementId}/items/${itemId}`)
  },

  getProductStock: async (productId: number): Promise<ProductStockDetail> => {
    return api.get<ProductStockDetail>(`/products/${productId}/stock`)
  },

  getProductsStock: async (productIds: number[]): Promise<ProductStockDetail[]> => {
    if (productIds.length === 0) return []
    const qs = new URLSearchParams()
    productIds.forEach((productId) => qs.append('ids', String(productId)))
    const data = await api.get<ProductStockBatchResponse>(`/products/stock?${qs.toString()}`)
    return data.items
  },

  getStockItemHistory: async (productId: number, itemId: number): Promise<StockItemHistory> => {
    return api.get<StockItemHistory>(`/products/${productId}/stock-items/${itemId}/history`)
  },

  patchStockItemStatus: async (productId: number, itemId: number, status: string): Promise<unknown> => {
    return api.patch(`/products/${productId}/stock-items/${itemId}`, { status })
  },
}
