import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { relancesApi } from '../relances'
import type { RelanceSchedulePayload } from '../relances'

export function useRelances(params?: { invoice_id?: number; customer_id?: number }) {
  return useQuery({
    queryKey: queryKeys.relances.list(params),
    queryFn: () => relancesApi.list(params),
    staleTime: 30 * 1000,
  })
}

export function useRelancesByCustomer(customerId: number) {
  return useQuery({
    queryKey: queryKeys.relances.list({ customer_id: customerId }),
    queryFn: () => relancesApi.list({ customer_id: customerId }),
    staleTime: 30 * 1000,
    enabled: customerId > 0,
  })
}

export function useScheduleRelance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: RelanceSchedulePayload) => relancesApi.schedule(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.relances.all })
    },
  })
}

export function useCancelRelance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (relanceId: number) => relancesApi.cancel(relanceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.relances.all })
    },
  })
}

export function useMarkRelanceSent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (relanceId: number) => relancesApi.markSent(relanceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.relances.all })
    },
  })
}
