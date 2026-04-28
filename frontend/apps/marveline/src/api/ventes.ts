import { api, fetchBlob } from './fetchClient'
import type { VenteListItem, VenteDetail, VenteDetailFull, VenteStatus, VentePayment } from '../types/vente'
import type { PaginatedResponse } from '../types'

export const ventesApi = {
  listVentes: async (params?: {
    skip?: number
    limit?: number
    status?: VenteStatus
    customer_id?: number
    date_from?: string
    date_to?: string
    search?: string
  }): Promise<PaginatedResponse<VenteListItem>> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.status) p.status = params.status
    if (params?.customer_id) p.customer_id = String(params.customer_id)
    if (params?.date_from) p.date_from = params.date_from
    if (params?.date_to) p.date_to = params.date_to
    if (params?.search) p.search = params.search
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedResponse<VenteListItem>>(`/ventes?${qs}`)
  },

  get: async (id: number): Promise<VenteDetailFull> => {
    return api.get<VenteDetailFull>(`/ventes/${id}`)
  },

  listOverdue: async (params?: { skip?: number; limit?: number }): Promise<PaginatedResponse<VenteListItem>> => {
    const p = new URLSearchParams()
    p.set('skip', String(params?.skip ?? 0))
    p.set('limit', String(params?.limit ?? 20))
    return api.get<PaginatedResponse<VenteListItem>>(`/ventes/overdue?${p.toString()}`)
  },

  create: async (payload: {
    customer_id: number
    lines: { product_id?: number; label: string; quantity: number; unit_price_cents: number }[]
    deposit_pct?: number
    payment_due_date?: string
    notes?: string
  }): Promise<VenteDetail> => {
    return api.post<VenteDetail>('/ventes', payload)
  },

  update: async (
    id: number,
    payload: { deposit_pct?: number; payment_due_date?: string; notes?: string }
  ): Promise<VenteDetail> => {
    return api.patch<VenteDetail>(`/ventes/${id}`, payload)
  },

  addPayment: async (
    id: number,
    payload: {
      amount_cents: number
      payment_method: string
      payment_date: string
      is_deposit?: boolean
      notes?: string
    }
  ): Promise<VentePayment> => {
    return api.post<VentePayment>(`/ventes/${id}/payments`, payload)
  },

  listPayments: async (id: number): Promise<VentePayment[]> => {
    const data = await api.get<VentePayment[] | VentePayment>(`/ventes/${id}/payments`)
    return Array.isArray(data) ? data : []
  },

  refund: async (
    id: number,
    payload: { amount_cents: number; reason: string; method: string }
  ): Promise<VenteDetail> => {
    return api.post<VenteDetail>(`/ventes/${id}/refund`, payload)
  },

  cancel: async (id: number): Promise<VenteDetail> => {
    return api.post<VenteDetail>(`/ventes/${id}/cancel`)
  },

  getPdf: async (id: number): Promise<Blob> => {
    return fetchBlob(`/ventes/${id}/pdf`)
  },
}
