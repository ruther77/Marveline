import { api } from './fetchClient'
import type { PaginatedResponse } from '../types'

export interface TreasuryEntry {
  entry_type: 'deposit' | 'payment'
  source_id: number
  amount_cents: number
  entry_date: string
  method: string | null
  status: string | null
  reference: string | null
  customer_name: string | null
  notes: string | null
}

export interface TreasurySummary {
  total_collected_cents: number
  deposits_held_cents: number
  deposits_retained_cents: number
  deposits_released_cents: number
  payments_total_cents: number
  deposits_count: number
  payments_count: number
  by_method: Record<string, number>
}

export const treasuryApi = {
  entries: async (params?: {
    entry_type?: string
    date_from?: string
    date_to?: string
    method?: string
    skip?: number
    limit?: number
  }): Promise<PaginatedResponse<TreasuryEntry>> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 200),
    }
    if (params?.entry_type) p.entry_type = params.entry_type
    if (params?.date_from) p.date_from = params.date_from
    if (params?.date_to) p.date_to = params.date_to
    if (params?.method) p.method = params.method
    return api.get('/treasury/entries', p)
  },

  summary: async (params?: {
    date_from?: string
    date_to?: string
  }): Promise<TreasurySummary> => {
    const p: Record<string, string> = {}
    if (params?.date_from) p.date_from = params.date_from
    if (params?.date_to) p.date_to = params.date_to
    return api.get('/treasury/summary', p)
  },
}
