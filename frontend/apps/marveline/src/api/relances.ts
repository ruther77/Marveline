import { api } from './fetchClient'
import type { RelanceStatus, RelanceChannel, RelanceResponse, RelanceSchedulePayload } from '@/types/relance'
import type { PaginatedResponse } from '@/types'

export type { RelanceStatus, RelanceChannel, RelanceResponse, RelanceSchedulePayload } from '@/types/relance'

export const relancesApi = {
  list(params?: { invoice_id?: number; customer_id?: number; skip?: number; limit?: number }): Promise<PaginatedResponse<RelanceResponse>> {
    const p: Record<string, string> = {}
    if (params?.invoice_id !== undefined) p.invoice_id = String(params.invoice_id)
    if (params?.customer_id !== undefined) p.customer_id = String(params.customer_id)
    if (params?.skip !== undefined) p.skip = String(params.skip)
    if (params?.limit !== undefined) p.limit = String(params.limit)
    const qs = Object.keys(p).length ? `?${new URLSearchParams(p).toString()}` : ''
    return api.get<PaginatedResponse<RelanceResponse>>(`/relances${qs}`)
  },

  schedule(data: RelanceSchedulePayload): Promise<RelanceResponse> {
    return api.post<RelanceResponse>('/relances/schedule', data)
  },

  cancel(relanceId: number): Promise<RelanceResponse> {
    return api.post<RelanceResponse>(`/relances/cancel/${relanceId}`, {})
  },

  markSent(relanceId: number): Promise<RelanceResponse> {
    return api.post<RelanceResponse>(`/relances/mark-sent/${relanceId}`, {})
  },
}
