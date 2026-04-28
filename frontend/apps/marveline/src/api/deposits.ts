import { api } from './fetchClient'
import type { PaginatedResponse } from '../types'

export interface DepositWithReservation {
  id: number
  tenant_id: number
  reservation_id: number
  amount_cents: number
  status: 'held' | 'released' | 'retained'
  retained_amount_cents: number | null
  collection_date: string | null
  release_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
  reservation_reference: string
  customer_name: string | null
  event_date: string | null
}

export interface DepositSummary {
  count_held: number
  count_retained: number
  count_released: number
  total_held_cents: number
  total_retained_cents: number
  total_released_cents: number
}

export const depositsApi = {
  list: async (params?: {
    status?: string
    date_from?: string
    date_to?: string
    skip?: number
    limit?: number
  }): Promise<PaginatedResponse<DepositWithReservation>> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 50),
    }
    if (params?.status) p.status = params.status
    if (params?.date_from) p.date_from = params.date_from
    if (params?.date_to) p.date_to = params.date_to
    return api.get('/deposits', p)
  },

  summary: async (): Promise<DepositSummary> => {
    return api.get('/deposits/summary')
  },
}
