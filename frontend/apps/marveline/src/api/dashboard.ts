import { api, fetchBlob } from './fetchClient'
import type { DashboardStats, FinancesStats, UrgentAlert, TodayPlanning, ActivityFeed, AnalyticsKpis } from '@/types/dashboard'

export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    return api.get<DashboardStats>('/dashboard/stats')
  },

  getFinances: async (year?: number): Promise<FinancesStats> => {
    const path = year ? `/dashboard/finances?year=${year}` : '/dashboard/finances'
    return api.get<FinancesStats>(path)
  },

  getUrgentAlert: async (): Promise<UrgentAlert | null> => {
    return api.get<UrgentAlert | null>('/dashboard/urgent-alert')
  },

  getTodayPlanning: async (): Promise<TodayPlanning> => {
    return api.get<TodayPlanning>('/dashboard/today')
  },

  getActivityFeed: async (): Promise<ActivityFeed> => {
    return api.get<ActivityFeed>('/dashboard/activity')
  },

  getAnalytics: async (periodDays = 365): Promise<AnalyticsKpis> => {
    return api.get<AnalyticsKpis>(`/dashboard/analytics?period_days=${periodDays}`)
  },

  exportCsv: async (year?: number): Promise<Blob> => {
    const path = year ? `/dashboard/finances/export?year=${year}` : '/dashboard/finances/export'
    return fetchBlob(path, { headers: { Accept: 'text/csv' } })
  },
}
