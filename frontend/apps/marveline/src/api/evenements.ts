import { api } from './fetchClient'
import type {
  EventListItem,
  EventDetailFull,
  EventIncident,
  EventStatus,
  IncidentAction,
  EventUpdate,
  RescheduleResponse,
  EventReport,
} from '../types/event'
import type { PaginatedResponse } from '../types'

export const evenementsApi = {
  listEvenements: async (params?: {
    skip?: number
    limit?: number
    status?: EventStatus
    date_from?: string
    date_to?: string
    search?: string
  }): Promise<PaginatedResponse<EventListItem>> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.status) p.status = params.status
    if (params?.date_from) p.date_from = params.date_from
    if (params?.date_to) p.date_to = params.date_to
    if (params?.search) p.search = params.search
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedResponse<EventListItem>>(`/evenements?${qs}`)
  },

  get: async (id: number): Promise<EventDetailFull> => {
    return api.get<EventDetailFull>(`/evenements/${id}`)
  },

  listIncidents: async (id: number): Promise<EventIncident[]> => {
    return api.get<EventIncident[]>(`/evenements/${id}/incidents`)
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

  close: async (id: number, notes: string): Promise<EventDetailFull> => {
    return api.post<EventDetailFull>(`/evenements/${id}/close`, { notes })
  },

  reschedule: async (
    id: number,
    new_date: string,
    force = false,
  ): Promise<RescheduleResponse> => {
    return api.post<RescheduleResponse>(`/evenements/${id}/reschedule`, { new_date, force })
  },

  getReport: async (id: number): Promise<EventReport> => {
    return api.get<EventReport>(`/evenements/${id}/report`)
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
