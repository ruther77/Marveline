import { useQuery, useMutation } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { dashboardApi } from '../dashboard'
import { useAuthStore } from '@/stores/authStore'

function useIsReady() {
  return useAuthStore((s) => s.isAuthenticated && !!s.user)
}

export function useDashboardStats() {
  const ready = useIsReady()
  return useQuery({
    queryKey: queryKeys.dashboard.stats(),
    queryFn: () => dashboardApi.getStats(),
    enabled: ready,
    staleTime: 2 * 60 * 1000,
    refetchInterval: (query) => (!ready || query.state.status === 'error' ? false : 60_000),
    retry: 1,
  })
}

export function useFinancesStats(year: number) {
  return useQuery({
    queryKey: queryKeys.dashboard.finances(year),
    queryFn: () => dashboardApi.getFinances(year),
    staleTime: 5 * 60 * 1000,
  })
}

export function useDashboardUrgentAlert() {
  const ready = useIsReady()
  return useQuery({
    queryKey: ['dashboard', 'urgent-alert'],
    queryFn: () => dashboardApi.getUrgentAlert(),
    enabled: ready,
    staleTime: 60_000,
    refetchInterval: (query) => (!ready || query.state.status === 'error' ? false : 90_000),
    retry: 1,
  })
}

export function useDashboardToday() {
  const ready = useIsReady()
  return useQuery({
    queryKey: ['dashboard', 'today'],
    queryFn: () => dashboardApi.getTodayPlanning(),
    enabled: ready,
    staleTime: 2 * 60 * 1000,
    refetchInterval: (query) => (!ready || query.state.status === 'error' ? false : 60_000),
    retry: 1,
  })
}

export function useDashboardActivity() {
  const ready = useIsReady()
  return useQuery({
    queryKey: ['dashboard', 'activity'],
    queryFn: () => dashboardApi.getActivityFeed(),
    enabled: ready,
    staleTime: 2 * 60 * 1000,
    refetchInterval: (query) => (!ready || query.state.status === 'error' ? false : 90_000),
    retry: 1,
  })
}

export function useAnalyticsKpis(periodDays = 365) {
  return useQuery({
    queryKey: queryKeys.dashboard.analytics(periodDays),
    queryFn: () => dashboardApi.getAnalytics(periodDays),
    staleTime: 5 * 60 * 1000,
  })
}

export function useDashboardExportCsv() {
  return useMutation({
    mutationFn: (year?: number) => dashboardApi.exportCsv(year),
  })
}
