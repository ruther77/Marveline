import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { planningApi } from '../planning'

export function usePlanningDay(date: string) {
  return useQuery({
    queryKey: queryKeys.planning.day(date),
    queryFn: () => planningApi.day(date),
  })
}

export function usePlanningWeek(date: string) {
  return useQuery({
    queryKey: queryKeys.planning.week(date),
    queryFn: () => planningApi.week(date),
  })
}

export function usePlanningMonth(date: string) {
  return useQuery({
    queryKey: queryKeys.planning.month(date),
    queryFn: () => planningApi.month(date),
  })
}

export function usePlanningResources(date: string) {
  return useQuery({
    queryKey: queryKeys.planning.resources(date),
    queryFn: () => planningApi.resources(date),
  })
}

export function usePlanningTimeline(startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: queryKeys.planning.timeline({ startDate, endDate }),
    queryFn: () => planningApi.timeline(startDate, endDate),
    staleTime: 60_000,
  })
}

export function usePlanningToday() {
  return useQuery({
    queryKey: queryKeys.planning.today(),
    queryFn: () => planningApi.today(),
    refetchInterval: 60_000,
  })
}

/**
 * Affecte ou désaffecte un utilisateur à une réservation (POST /planning/assign).
 * Invalide toutes les vues planning après mutation.
 */
export function useAssignUser(weekStr?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, userId }: { reservationId: number; userId: number | null }) =>
      planningApi.assign(reservationId, userId),
    onSuccess: () => {
      // Invalider toutes les vues planning pour refléter le nouvel assigné
      qc.invalidateQueries({ queryKey: ['planning'] })
      if (weekStr) {
        qc.invalidateQueries({ queryKey: queryKeys.planning.week(weekStr) })
      }
    },
  })
}
