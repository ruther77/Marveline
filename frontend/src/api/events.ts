import apiClient from './client'
import type {
  Event,
  EventListItem,
  EventStats,
  EventStatus,
  EventType,
  CreateEventRequest,
  UpdateEventRequest,
  EventItem,
} from '../types/event'

export const eventsApi = {
  getEvents: async (params?: {
    page?: number
    page_size?: number
    start_date?: string
    end_date?: string
    status?: EventStatus
    event_type?: EventType
  }): Promise<{
    items: EventListItem[]
    total: number
    page: number
    page_size: number
    total_pages: number
  }> => {
    const { data } = await apiClient.get('/events', { params })
    // Backend retourne { success, data, pagination }
    // On transforme en { items, total, page, page_size, total_pages }
    return {
      items: data.data || [],
      total: data.pagination?.total_items || 0,
      page: data.pagination?.page || 1,
      page_size: data.pagination?.page_size || 20,
      total_pages: data.pagination?.total_pages || 0,
    }
  },

  getEvent: async (id: number): Promise<Event> => {
    const { data } = await apiClient.get(`/events/${id}`)
    return data.data || data
  },

  createEvent: async (event: CreateEventRequest): Promise<Event> => {
    const { data } = await apiClient.post('/events', event)
    return data.data || data
  },

  updateEvent: async (
    id: number,
    event: UpdateEventRequest
  ): Promise<Event> => {
    const { data } = await apiClient.patch(`/events/${id}`, event)
    return data.data || data
  },

  deleteEvent: async (id: number): Promise<void> => {
    await apiClient.delete(`/events/${id}`)
  },

  getStatistics: async (
    startDate?: string,
    endDate?: string
  ): Promise<EventStats> => {
    const { data } = await apiClient.get('/events/statistics', {
      params: { start_date: startDate, end_date: endDate },
    })
    // Backend retourne { success, data: {...stats...} }
    return data.data || data
  },

  calculateTotal: async (id: number): Promise<{
    subtotal: number
    cleaning_fees: number
    total: number
  }> => {
    const { data } = await apiClient.get(`/events/${id}/total`)
    return data.data || data
  },

  // Items
  addItem: async (
    eventId: number,
    item: {
      product_id?: number
      product_variation_id?: number
      bundle_id?: number
      quantity: number
      unit_price: number
      cleaning_fee?: number
      notes?: string
    }
  ): Promise<EventItem> => {
    const { data } = await apiClient.post(`/events/${eventId}/items`, item)
    return data.data || data
  },

  updateItem: async (
    itemId: number,
    item: {
      quantity?: number
      unit_price?: number
      cleaning_fee?: number
      notes?: string
    }
  ): Promise<EventItem> => {
    const { data } = await apiClient.patch(`/events/items/${itemId}`, item)
    return data.data || data
  },

  removeItem: async (itemId: number): Promise<void> => {
    await apiClient.delete(`/events/items/${itemId}`)
  },
}
