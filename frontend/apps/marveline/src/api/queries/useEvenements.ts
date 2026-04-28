import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { evenementsApi } from '../evenements'
import type { EventStatus } from '@/types/event'

export function useEvenementsList(params?: {
  skip?: number
  limit?: number
  status?: EventStatus
  date_from?: string
  date_to?: string
  search?: string
}) {
  return useQuery({
    queryKey: queryKeys.evenements.list(params ?? {}),
    queryFn: () => evenementsApi.listEvenements(params),
  })
}

export function useEvenementDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.evenements.detail(id!),
    queryFn: () => evenementsApi.get(id!),
    enabled: id !== null,
  })
}

export function useEvenementIncidents(id: number | null) {
  return useQuery({
    queryKey: queryKeys.evenements.incidents(id!),
    queryFn: () => evenementsApi.listIncidents(id!),
    enabled: id !== null,
  })
}

export function useCreateEvenement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof evenementsApi.create>[0]) =>
      evenementsApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.lists() })
    },
  })
}

export function useUpdateEvenement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof evenementsApi.update>[1] }) =>
      evenementsApi.update(id, payload),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.lists() })
    },
  })
}

export function useMarkReturned(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (notes?: string) => evenementsApi.markReturned(id, notes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.lists() })
    },
  })
}

export function useCloseEvenement(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (notes: string) => evenementsApi.close(id, notes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.lists() })
    },
  })
}

export function useFlagRisk(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => evenementsApi.flagRisk(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(id) })
    },
  })
}

export function useCancelEvenement(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => evenementsApi.cancel(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.lists() })
    },
  })
}

export function useDeclareIncident(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof evenementsApi.declareIncident>[1]) =>
      evenementsApi.declareIncident(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.incidents(id) })
    },
  })
}

export function useAddActionPlan(id: number, incidentId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof evenementsApi.addActionPlan>[2]) =>
      evenementsApi.addActionPlan(id, incidentId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.incidents(id) })
    },
  })
}

// Hook de transition générique : mappe le statut vers le bon endpoint backend
export function useTransitionEvenement(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ status, notes }: { status: EventStatus; notes?: string }) => {
      switch (status) {
        case 'in_progress': return evenementsApi.start(id)
        case 'returned': return evenementsApi.markReturned(id, notes)
        case 'closed': return evenementsApi.close(id, notes ?? '')
        case 'risk': return evenementsApi.flagRisk(id)
        case 'cancelled': return evenementsApi.cancel(id)
        default: return Promise.reject(new Error(`Transition "${status}" non supportée`))
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.lists() })
    },
  })
}

export function useRescheduleEvenement(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ new_date, force }: { new_date: string; force?: boolean }) =>
      evenementsApi.reschedule(id, new_date, force),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.lists() })
    },
  })
}

export function useEventReport(id: number | null) {
  return useQuery({
    queryKey: [...queryKeys.evenements.detail(id!), 'report'],
    queryFn: () => evenementsApi.getReport(id!),
    enabled: id !== null,
  })
}

// Alias de compatibilité pour les pages existantes
export const useUpdateEventStatus = useTransitionEvenement
export const useAddAction = useAddActionPlan

export function useCloseAction(eventId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ incidentId, actionId }: { incidentId: number; actionId: number }) =>
      evenementsApi.closeAction(eventId, incidentId, actionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.evenements.detail(eventId) })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.evenements.incidents(eventId) })
    },
  })
}
