import { api } from './fetchClient'
import type { PlanningDayResponse, PlanningWeek, PlanningMonth, PlanningResources, PlanningToday, PlanningAssignResponse, PlanningTimeline } from '../types/planning'

export const planningApi = {
  day: async (date?: string): Promise<PlanningDayResponse> => {
    const params = date ? `?date=${date}` : ''
    return api.get<PlanningDayResponse>(`/planning/day${params}`)
  },

  week: async (date?: string): Promise<PlanningWeek> => {
    const params = date ? `?date=${date}` : ''
    return api.get<PlanningWeek>(`/planning/week${params}`)
  },

  month: async (date?: string): Promise<PlanningMonth> => {
    const params = date ? `?date=${date}` : ''
    return api.get<PlanningMonth>(`/planning/month${params}`)
  },

  resources: async (date?: string): Promise<PlanningResources> => {
    const params = date ? `?date=${date}` : ''
    return api.get<PlanningResources>(`/planning/resources${params}`)
  },

  today: async (): Promise<PlanningToday> => {
    return api.get<PlanningToday>('/planning/today')
  },

  timeline: async (startDate?: string, endDate?: string): Promise<PlanningTimeline> => {
    const p: Record<string, string> = {}
    if (startDate) p.start_date = startDate
    if (endDate) p.end_date = endDate
    const qs = new URLSearchParams(p).toString()
    const path = qs ? `/planning/timeline?${qs}` : '/planning/timeline'
    return api.get<PlanningTimeline>(path)
  },

  /** Affecte (ou désaffecte) un utilisateur à une réservation (user_id=null pour désaffecter). */
  assign: async (reservationId: number, userId: number | null): Promise<PlanningAssignResponse> => {
    return api.post<PlanningAssignResponse>('/planning/assign', {
      reservation_id: reservationId,
      user_id: userId,
    })
  },
}
