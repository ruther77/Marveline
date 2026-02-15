import apiClient from './client'
import type {
  InventoryMovement,
  InventoryMovementListItem,
  AgendaView,
  MovementStats,
  MovementType,
  MovementStatus,
  CreateMovementRequest,
  UpdateMovementRequest,
  MovementItem,
} from '../types/inventory'

export const inventoryApi = {
  getMovements: async (params?: {
    page?: number
    page_size?: number
    movement_type?: MovementType
    status?: MovementStatus
    event_id?: number
    start_date?: string
    end_date?: string
  }): Promise<{
    items: InventoryMovementListItem[]
    total: number
    page: number
    page_size: number
    total_pages: number
  }> => {
    const { data } = await apiClient.get('/inventory-movements', { params })
    // Backend CaroCorp_new retourne { items, total }
    const items = Array.isArray(data.items) ? data.items : (Array.isArray(data.data) ? data.data : [])
    const total = data.total ?? data.pagination?.total_items ?? 0
    const pageSize = params?.page_size || 20
    return {
      items,
      total,
      page: params?.page || 1,
      page_size: pageSize,
      total_pages: Math.ceil(total / pageSize) || 0,
    }
  },

  getLateMovements: async (): Promise<InventoryMovementListItem[]> => {
    const { data } = await apiClient.get('/inventory-movements/late')
    // Backend retourne { success, data: [...] }
    return data.data || data
  },

  getPendingInspections: async (): Promise<InventoryMovementListItem[]> => {
    const { data } = await apiClient.get('/inventory-movements/pending-inspections')
    // Backend retourne { success, data: [...] }
    return data.data || data
  },

  getAgenda: async (
    startDate?: string,
    endDate?: string
  ): Promise<AgendaView> => {
    const { data } = await apiClient.get('/inventory-movements/agenda', {
      params: { start_date: startDate, end_date: endDate },
    })
    return data.data || data
  },

  getStatistics: async (
    startDate?: string,
    endDate?: string
  ): Promise<MovementStats> => {
    const { data } = await apiClient.get('/inventory-movements/statistics', {
      params: { start_date: startDate, end_date: endDate },
    })
    return data.data || data
  },

  getMovement: async (id: number): Promise<InventoryMovement> => {
    const { data } = await apiClient.get(`/inventory-movements/${id}`)
    return data.data || data
  },

  createMovement: async (
    movement: CreateMovementRequest
  ): Promise<InventoryMovement> => {
    const { data } = await apiClient.post('/inventory-movements', movement)
    return data.data || data
  },

  updateMovement: async (
    id: number,
    movement: UpdateMovementRequest
  ): Promise<InventoryMovement> => {
    const { data } = await apiClient.patch(`/inventory-movements/${id}`, movement)
    return data.data || data
  },

  deleteMovement: async (id: number): Promise<void> => {
    await apiClient.delete(`/inventory-movements/${id}`)
  },

  completeMovement: async (id: number): Promise<InventoryMovement> => {
    const { data } = await apiClient.patch(`/inventory-movements/${id}/complete`)
    return data.data || data
  },

  // Items
  addItem: async (
    movementId: number,
    item: {
      event_item_id?: number
      product_id?: number
      product_variation_id?: number
      quantity_expected: number
      condition?: string
      condition_notes?: string
    }
  ): Promise<MovementItem> => {
    const { data } = await apiClient.post(
      `/inventory-movements/${movementId}/items`,
      item
    )
    return data.data || data
  },

  updateItem: async (
    itemId: number,
    item: {
      quantity_actual?: number
      condition?: string
      condition_notes?: string
    }
  ): Promise<MovementItem> => {
    const { data } = await apiClient.patch(
      `/inventory-movements/items/${itemId}`,
      item
    )
    return data.data || data
  },

  removeItem: async (itemId: number): Promise<void> => {
    await apiClient.delete(`/inventory-movements/items/${itemId}`)
  },
}
