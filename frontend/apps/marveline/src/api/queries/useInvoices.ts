import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { invalidateFinance } from './invalidateFinance'
import { invoicesApi } from '../invoices'
import type { InvoiceStatus, InvoiceListItem, InvoiceCreateRequest, InvoiceUpdateRequest, InvoiceChargeCreate } from '@/types/invoice'
import type { PaginatedResponse } from '@/types/index'
import type { PaymentCreate } from '@/types/payment'

export function useInvoicesList(params?: {
  skip?: number
  limit?: number
  status?: InvoiceStatus
  customer_id?: number
  reservation_id?: number
  date_from?: string
  date_to?: string
  overdue_only?: boolean
  search?: string
}, enabled = true) {
  return useQuery({
    queryKey: queryKeys.invoices.list(params ?? {}),
    queryFn: () =>
      invoicesApi.listInvoices({
        skip: params?.skip,
        limit: params?.limit,
        status: params?.status,
        reservation_id: params?.reservation_id,
      }),
    enabled,
  })
}

export function useInvoiceDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.invoices.detail(id!),
    queryFn: () => invoicesApi.getInvoice(id!),
    enabled: id !== null,
  })
}

export function useInvoiceFull(id: number | null) {
  return useQuery({
    queryKey: queryKeys.invoices.full(id!),
    queryFn: () => invoicesApi.getInvoiceFull(id!),
    enabled: id !== null,
  })
}

export function useInvoiceAudit(id: number | null, limit = 50) {
  return useQuery({
    queryKey: queryKeys.invoices.audit(id!, limit),
    queryFn: () => invoicesApi.getInvoiceAudit(id!, limit),
    enabled: id !== null,
    select: (data) => data.items,
  })
}

export function useOverdueInvoices(limit?: number) {
  return useQuery({
    queryKey: queryKeys.invoices.overdue(),
    queryFn: () => invoicesApi.getOverdueInvoices(limit),
    staleTime: 2 * 60 * 1000,
  })
}

export function useInvoicePayments(invoiceId: number | null) {
  return useQuery({
    queryKey: queryKeys.invoices.payments(invoiceId!),
    queryFn: () => invoicesApi.listPayments(invoiceId!),
    enabled: invoiceId !== null,
    staleTime: 2 * 60 * 1000,
    select: (data) => data.items,
  })
}

export function useCreateInvoice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: InvoiceCreateRequest) => invoicesApi.createInvoice(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.invoices.all })
      invalidateFinance(qc)
    },
  })
}

export function useUpdateInvoice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: InvoiceUpdateRequest }) =>
      invoicesApi.updateInvoice(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.invoices.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.lists() })
      invalidateFinance(qc)
    },
  })
}

export function useCancelInvoice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => invoicesApi.cancelInvoice(id),

    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: queryKeys.invoices.lists() })
      const previousLists = qc.getQueriesData<PaginatedResponse<InvoiceListItem>>({
        queryKey: queryKeys.invoices.lists(),
      })
      qc.setQueriesData<PaginatedResponse<InvoiceListItem>>(
        { queryKey: queryKeys.invoices.lists() },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.map((inv: InvoiceListItem) =>
              inv.id === id ? { ...inv, status: 'cancelled' as InvoiceStatus } : inv
            ),
          }
        }
      )
      return { previousLists }
    },

    onError: (_err, _vars, context) => {
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data)
        })
      }
    },

    onSettled: (_r, _e, id) => {
      qc.invalidateQueries({ queryKey: queryKeys.invoices.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })
}

export function useInvoicePdf() {
  return useMutation({
    mutationFn: (id: number) => invoicesApi.getPdf(id),
  })
}

export function useAddCharge() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ invoiceId, charge }: { invoiceId: number; charge: InvoiceChargeCreate }) =>
      invoicesApi.addCharge(invoiceId, charge),
    onSuccess: (_r, { invoiceId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.invoices.detail(invoiceId) })
      invalidateFinance(qc)
    },
  })
}

export function useAddPaymentRecord() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ invoiceId, data }: { invoiceId: number; data: PaymentCreate }) =>
      invoicesApi.addPaymentRecord(invoiceId, data),
    onSuccess: (_r, { invoiceId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.invoices.detail(invoiceId) })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      invalidateFinance(qc)
    },
  })
}



export function useInvoiceCreditNotes(invoiceId: number | null) {
  return useQuery({
    queryKey: queryKeys.invoices.creditNotes(invoiceId!),
    queryFn: () => invoicesApi.listCreditNotes(invoiceId!),
    enabled: invoiceId !== null,
    select: (data) => data.items,
  })
}

export function useMarkInvoiceSent(invoiceId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data?: { sent_at?: string; notes?: string }) =>
      invoicesApi.markSent(invoiceId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.invoices.detail(invoiceId) })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.lists() })
    },
  })
}

export function useRemindInvoice(invoiceId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data?: { notes?: string }) => invoicesApi.remind(invoiceId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.invoices.detail(invoiceId) })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.full(invoiceId) })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.audit(invoiceId, 50) })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.lists() })
    },
  })
}

export function useInvoiceSequenceGaps(year: number) {
  return useQuery({
    queryKey: ['invoices', 'sequence-gaps', year],
    queryFn: () => invoicesApi.getSequenceGaps(year),
    staleTime: 5 * 60 * 1000,
  })
}

export function useInvoiceTvaReport(month: string | null) {
  return useQuery({
    queryKey: ['invoices', 'tva-report', month],
    queryFn: () => invoicesApi.getTvaReport(month!),
    enabled: month !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useAllInvoicePayments(
  params?: Parameters<typeof invoicesApi.getAllPayments>[0],
  enabled = true
) {
  return useQuery({
    queryKey: ['invoices', 'payments', 'all', params ?? {}],
    queryFn: () => invoicesApi.getAllPayments(params),
    enabled,
    staleTime: 2 * 60 * 1000,
    select: (data) => data.items,
  })
}

export function useCreateCreditNote(invoiceId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { amount_cents: number; reason: string; issue_date: string }) =>
      invoicesApi.createCreditNote(invoiceId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['invoices', invoiceId, 'credit-notes'] })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.detail(invoiceId) })
    },
  })
}

export function useApplyCreditNote(invoiceId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (cnId: number) => invoicesApi.applyCreditNote(invoiceId, cnId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['invoices', invoiceId, 'credit-notes'] })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.detail(invoiceId) })
    },
  })
}

export function useRefundCreditNote(invoiceId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (cnId: number) => invoicesApi.refundCreditNote(invoiceId, cnId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['invoices', invoiceId, 'credit-notes'] })
      qc.invalidateQueries({ queryKey: queryKeys.invoices.detail(invoiceId) })
    },
  })
}

export function useCreateDamageInvoice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof invoicesApi.createDamageInvoice>[0]) =>
      invoicesApi.createDamageInvoice(data),
    onSuccess: () => {
      invalidateFinance(qc)
    },
  })
}
