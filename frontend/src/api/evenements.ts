import { api } from './fetchClient'
import type { EventListItem, EventDetailFull, EventStatus, IncidentAction, EventUpdate } from '../types/event'

export const evenementsApi = {
  list: async (params?: {
    page?: number
    page_size?: number
    status?: EventStatus
    date_from?: string
    date_to?: string
    search?: string
  }): Promise<{ items: EventListItem[]; total: number; page: number; page_size: number; total_pages: number }> => {
    const page = params?.page || 1
    const pageSize = params?.page_size || 20
    const p: Record<string, string> = {
      skip: String((page - 1) * pageSize),
      limit: String(pageSize),
    }
    if (params?.status) p.status = params.status
    if (params?.date_from) p.date_from = params.date_from
    if (params?.date_to) p.date_to = params.date_to
    if (params?.search) p.search = params.search
    const qs = new URLSearchParams(p).toString()
    const data = await api.get<{ items?: EventListItem[]; total?: number }>(`/evenements?${qs}`)
    const items = Array.isArray(data.items) ? data.items : []
    const total = data.total ?? 0
    return { items, total, page, page_size: pageSize, total_pages: Math.ceil(total / pageSize) || 0 }
  },

  get: async (id: number): Promise<EventDetailFull> => {
    return api.get<EventDetailFull>(`/evenements/${id}`)
  },

  create: async (payload: {
    reservation_id?: number
    name: string
    event_date: string
    event_location?: string
  }): Promise<EventDetailFull> => {
    return api.post<EventDetailFull>('/evenements', payload)
  },

  markReturned: async (id: number, notes?: string): Promise<EventDetailFull> => {
    return api.post<EventDetailFull>(`/evenements/${id}/mark-returned`, notes ? { notes } : {})
  },

  close: async (id: number): Promise<EventDetailFull> => {
    return api.post<EventDetailFull>(`/evenements/${id}/close`, {})
  },

  flagRisk: async (id: number): Promise<EventDetailFull> => {
    return api.post<EventDetailFull>(`/evenements/${id}/flag-risk`, {})
  },

  update: async (id: number, payload: EventUpdate): Promise<EventDetailFull> => {
    return api.patch<EventDetailFull>(`/evenements/${id}`, payload)
  },

  cancel: async (id: number): Promise<EventDetailFull> => {
    return api.post<EventDetailFull>(`/evenements/${id}/cancel`, {})
  },

  start: async (id: number): Promise<EventDetailFull> => {
    return api.post<EventDetailFull>(`/evenements/${id}/start`, {})
  },

  declareIncident: async (
    id: number,
    payload: {
      description: string
      severity: 'low' | 'medium' | 'high' | 'critical'
      declared_at?: string
      affected_items?: number[]
      owner_id?: number
    }
  ): Promise<EventDetailFull> => {
    const body = {
      ...payload,
      declared_at: payload.declared_at ?? new Date().toISOString(),
    }
    return api.post<EventDetailFull>(`/evenements/${id}/incidents`, body)
  },

  addActionPlan: async (
    id: number,
    incidentId: number,
    payload: { label: string; assignee_id: number; deadline: string; status?: string } | Array<{ label: string; assignee_id: number; deadline: string; status?: string }>
  ): Promise<IncidentAction[]> => {
    // Accept single action or array of actions, normalize to array
    const actions = Array.isArray(payload) ? payload : [payload]
    return api.post<IncidentAction[]>(`/evenements/${id}/incidents/${incidentId}/action-plan`, actions)
  },

  closeAction: async (
    eventId: number,
    incidentId: number,
    actionId: number
  ): Promise<{ id: number; status: string }> => {
    return api.patch(`/evenements/${eventId}/incidents/${incidentId}/actions/${actionId}/close`)
  },
}
