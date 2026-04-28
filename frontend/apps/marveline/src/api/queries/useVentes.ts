import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { invalidateFinance } from './invalidateFinance'
import { ventesApi } from '../ventes'
import type { VenteStatus } from '@/types/vente'

export function useVentesList(params?: {
  skip?: number
  limit?: number
  status?: VenteStatus
  customer_id?: number
  date_from?: string
  date_to?: string
  search?: string
}, enabled = true) {
  return useQuery({
    queryKey: queryKeys.ventes.list(params ?? {}),
    queryFn: () => ventesApi.listVentes(params),
    enabled,
  })
}

export function useVenteDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.ventes.detail(id!),
    queryFn: () => ventesApi.get(id!),
    enabled: id !== null,
  })
}

export function useVentesOverdue(params?: { skip?: number; limit?: number }, enabled = true) {
  return useQuery({
    queryKey: queryKeys.ventes.overdue(params ?? {}),
    queryFn: () => ventesApi.listOverdue(params),
    enabled,
  })
}

export function useVentePayments(id: number | null) {
  return useQuery({
    queryKey: queryKeys.ventes.payments(id!),
    queryFn: () => ventesApi.listPayments(id!),
    enabled: id !== null,
  })
}

export function useCreateVente() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof ventesApi.create>[0]) => ventesApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.ventes.all }) },
  })
}

export function useUpdateVente() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof ventesApi.update>[1] }) =>
      ventesApi.update(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.ventes.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.ventes.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.ventes.overdueAll() })
    },
  })
}

export function useAddVentePayment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof ventesApi.addPayment>[1] }) =>
      ventesApi.addPayment(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.ventes.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.ventes.payments(id) })
      qc.invalidateQueries({ queryKey: queryKeys.ventes.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.ventes.overdueAll() })
      invalidateFinance(qc)
    },
  })
}

export function useVenteRefund() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof ventesApi.refund>[1] }) =>
      ventesApi.refund(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.ventes.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.ventes.lists() })
      invalidateFinance(qc)
    },
  })
}

export function useCancelVente() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => ventesApi.cancel(id),
    onSuccess: (_r, id) => {
      qc.invalidateQueries({ queryKey: queryKeys.ventes.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.ventes.lists() })
    },
  })
}

export function useVentePdf() {
  return useMutation({
    mutationFn: (id: number) => ventesApi.getPdf(id),
  })
}
