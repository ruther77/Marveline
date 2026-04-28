import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { invalidateFinance } from './invalidateFinance'
import { operationsApi } from '../operations'
import type { DepartureInventory, ReturnInventory, ReturnDamagePayload } from '@/types/operations'

export function useDepartureInventory(reservationId: number | null) {
  const validReservationId = Number.isInteger(reservationId) && (reservationId as number) > 0
  return useQuery<DepartureInventory>({
    queryKey: queryKeys.operations.departure(validReservationId ? (reservationId as number) : -1),
    queryFn: () => operationsApi.getDepartureState(reservationId as number),
    enabled: validReservationId,
    staleTime: 0,
    retry: false,
  })
}

export function useReturnInventory(reservationId: number | null) {
  const validReservationId = Number.isInteger(reservationId) && (reservationId as number) > 0
  return useQuery<ReturnInventory>({
    queryKey: queryKeys.operations.return(validReservationId ? (reservationId as number) : -1),
    queryFn: () => operationsApi.getReturnState(reservationId as number),
    enabled: validReservationId,
    staleTime: 0,
    retry: false,
  })
}

export function useSubmitDeparture() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, items, signatureUrl }: { reservationId: number; items?: unknown[]; signatureUrl?: string }) =>
      operationsApi.validateDeparture(reservationId, items, signatureUrl),
    onSuccess: (_r, { reservationId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.operations.departure(reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.detail(reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.full(reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.stats() })
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.lists() })
      invalidateFinance(qc)
    },
  })
}

export function useSubmitReturn() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, items, signatureUrl }: { reservationId: number; items?: unknown[]; signatureUrl?: string }) =>
      operationsApi.validateReturn(reservationId, items, signatureUrl),
    onSuccess: (_r, { reservationId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.operations.return(reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.detail(reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.full(reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.stats() })
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.lists() })
      invalidateFinance(qc)
    },
  })
}

export function useBlockDeparture() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, reason }: { reservationId: number; reason: string }) =>
      operationsApi.blockDeparture(reservationId, { reason }),
    onSuccess: (_r, { reservationId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.operations.departure(reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.detail(reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.full(reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.stats() })
    },
  })
}

export function useDeclareCasse() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      reservationId,
      payload,
    }: {
      reservationId: number
      payload: ReturnDamagePayload
    }) => operationsApi.declareDamage(reservationId, payload),
    onSuccess: (_r, { reservationId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.detail(reservationId) })
      invalidateFinance(qc)
    },
  })
}

export function useResolveQr() {
  return useMutation({
    mutationFn: (code: string) => operationsApi.resolveQr(code),
  })
}

export function useUploadDamagePhoto() {
  return useMutation({
    mutationFn: (file: File) => operationsApi.uploadDamagePhoto(file),
  })
}

export function useOperationsSummary() {
  return useQuery({
    queryKey: ['operations', 'summary'],
    queryFn: () => operationsApi.getSummary(),
    staleTime: 30 * 1000,
  })
}
