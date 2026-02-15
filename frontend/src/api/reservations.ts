import apiClient from './client'
import type {
  ReservationList,
  ReservationDetail,
  ReservationCreate,
  ReservationUpdate,
  ReservationStatus,
  PaginatedReservations,
} from '../types/reservation'

export const reservationsApi = {
  getReservations: async (params?: {
    page?: number
    page_size?: number
    status?: ReservationStatus
    start_date?: string
    end_date?: string
    customer_id?: number
  }): Promise<PaginatedReservations> => {
    const pageSize = params?.page_size || 20
    const page = params?.page || 1
    const backendParams: Record<string, unknown> = {
      skip: (page - 1) * pageSize,
      limit: pageSize,
    }
    if (params?.status) backendParams.status_filter = params.status
    if (params?.start_date) backendParams.start_date = params.start_date
    if (params?.end_date) backendParams.end_date = params.end_date
    if (params?.customer_id) backendParams.customer_id = params.customer_id

    const { data } = await apiClient.get('/reservations', { params: backendParams })
    const items = Array.isArray(data.items) ? data.items : []
    const total = data.total ?? 0
    return {
      items,
      total,
      page,
      page_size: pageSize,
      total_pages: Math.ceil(total / pageSize) || 0,
    }
  },

  getReservation: async (id: number): Promise<ReservationDetail> => {
    const { data } = await apiClient.get(`/reservations/${id}`)
    return data.data || data
  },

  createReservation: async (reservation: ReservationCreate): Promise<ReservationDetail> => {
    const { data } = await apiClient.post('/reservations', reservation)
    return data.data || data
  },

  updateReservation: async (
    id: number,
    reservation: ReservationUpdate
  ): Promise<ReservationDetail> => {
    const { data } = await apiClient.patch(`/reservations/${id}`, reservation)
    return data.data || data
  },

  confirmReservation: async (id: number): Promise<ReservationDetail> => {
    const { data } = await apiClient.post(`/reservations/${id}/confirm`)
    return data.data || data
  },

  cancelReservation: async (id: number): Promise<ReservationDetail> => {
    const { data } = await apiClient.post(`/reservations/${id}/cancel`)
    return data.data || data
  },
}
