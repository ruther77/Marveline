import { api, fetchBlob } from './fetchClient'
import type {
  InvoiceListItem,
  InvoiceDetail,
  InvoiceDetailFull,
  InvoiceCreateRequest,
  InvoiceUpdateRequest,
  AddPaymentRequest,
  InvoiceStatus,
  InvoiceCharge,
  InvoiceChargeCreate,
  CreditNote,
  TvaReportResponse,
} from '../types/invoice'
import type { Payment, PaymentCreate } from '../types/payment'
import type { PaginatedResponse, AuditLog } from '../types'

export const invoicesApi = {
  listInvoices: async (params?: {
    skip?: number
    limit?: number
    status?: InvoiceStatus
    reservation_id?: number
  }): Promise<PaginatedResponse<InvoiceListItem>> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.status) p.status_filter = params.status
    if (params?.reservation_id) p.reservation_id = String(params.reservation_id)
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedResponse<InvoiceListItem>>(`/invoices?${qs}`)
  },

  getInvoice: async (id: number): Promise<InvoiceDetailFull> => {
    return api.get<InvoiceDetailFull>(`/invoices/${id}`)
  },

  getInvoiceFull: async (id: number): Promise<InvoiceDetailFull> => {
    return api.get<InvoiceDetailFull>(`/invoices/${id}/full`)
  },

  getInvoiceAudit: async (id: number, limit = 50): Promise<PaginatedResponse<AuditLog>> => {
    return api.get<PaginatedResponse<AuditLog>>(`/invoices/${id}/audit?limit=${limit}`)
  },

  getOverdueInvoices: async (limit?: number): Promise<InvoiceListItem[]> => {
    const path = limit ? `/invoices/overdue?limit=${limit}` : '/invoices/overdue'
    const res = await api.get<{ items: InvoiceListItem[]; total: number }>(path)
    return res.items
  },

  createInvoice: async (invoice: InvoiceCreateRequest): Promise<InvoiceDetail> => {
    return api.post<InvoiceDetail>('/invoices', invoice)
  },

  updateInvoice: async (id: number, invoice: InvoiceUpdateRequest): Promise<InvoiceDetail> => {
    return api.patch<InvoiceDetail>(`/invoices/${id}`, invoice)
  },

  addPayment: async (id: number, payment: AddPaymentRequest): Promise<InvoiceDetail> => {
    return api.post<InvoiceDetail>(`/invoices/${id}/add-payment`, payment)
  },

  cancelInvoice: async (id: number): Promise<InvoiceDetail> => {
    return api.post<InvoiceDetail>(`/invoices/${id}/cancel`)
  },

  getPdf: async (id: number): Promise<Blob> => {
    return fetchBlob(`/invoices/${id}/pdf`)
  },

  addCharge: async (invoiceId: number, charge: InvoiceChargeCreate): Promise<InvoiceCharge> => {
    return api.post<InvoiceCharge>(`/invoices/${invoiceId}/add-charge`, charge)
  },

  addPaymentRecord: async (invoiceId: number, data: PaymentCreate): Promise<Payment> => {
    return api.post<Payment>(`/invoices/${invoiceId}/payments`, data)
  },

  listPayments: async (invoiceId: number): Promise<PaginatedResponse<Payment>> => {
    return api.get<PaginatedResponse<Payment>>(`/invoices/${invoiceId}/payments`)
  },

  listCreditNotes: async (invoiceId: number): Promise<PaginatedResponse<CreditNote>> => {
    return api.get<PaginatedResponse<CreditNote>>(`/invoices/${invoiceId}/credit-notes`)
  },

  createCreditNote: async (
    invoiceId: number,
    data: { amount_cents: number; reason: string; issue_date: string }
  ): Promise<CreditNote> => {
    return api.post<CreditNote>(`/invoices/${invoiceId}/credit-note`, data)
  },

  applyCreditNote: async (invoiceId: number, cnId: number): Promise<CreditNote> => {
    return api.post<CreditNote>(`/invoices/${invoiceId}/credit-notes/${cnId}/apply`)
  },

  refundCreditNote: async (invoiceId: number, cnId: number): Promise<CreditNote> => {
    return api.post<CreditNote>(`/invoices/${invoiceId}/credit-notes/${cnId}/refund`)
  },

  markSent: async (
    invoiceId: number,
    data?: { sent_at?: string; notes?: string }
  ): Promise<InvoiceDetail> => {
    return api.post<InvoiceDetail>(`/invoices/${invoiceId}/mark-sent`, data ?? {})
  },

  remind: async (
    invoiceId: number,
    data?: { notes?: string }
  ): Promise<InvoiceDetail> => {
    return api.post<InvoiceDetail>(`/invoices/${invoiceId}/remind`, data ?? {})
  },

  createDamageInvoice: async (data: {
    reservation_id: number
    charges: Array<{
      charge_type?: 'DAMAGE' | 'LABOR'
      description: string
      amount_cents?: number
      hours?: number
      day_type?: 'weekday' | 'weekend' | 'night'
      damage_type_id?: number
    }>
    notes?: string
  }): Promise<InvoiceDetail> => {
    return api.post<InvoiceDetail>('/invoices/damage', data)
  },

  getTvaReport: async (month: string): Promise<TvaReportResponse> => {
    return api.get<TvaReportResponse>(`/invoices/tva-report?month=${month}`)
  },

  getAllPayments: async (params?: {
    date_from?: string
    date_to?: string
    payment_method?: string
    limit?: number
    skip?: number
  }): Promise<PaginatedResponse<Payment>> => {
    const query = new URLSearchParams()
    if (params?.date_from) query.set('date_from', params.date_from)
    if (params?.date_to) query.set('date_to', params.date_to)
    if (params?.payment_method) query.set('payment_method', params.payment_method)
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.skip) query.set('skip', String(params.skip))
    const qs = query.toString()
    return api.get<PaginatedResponse<Payment>>(`/invoices/payments${qs ? '?' + qs : ''}`)
  },

  getSequenceGaps: async (year: number): Promise<{ year: number; gaps: number[]; count: number }> => {
    return api.get<{ year: number; gaps: number[]; count: number }>(`/invoices/sequence/gaps?year=${year}`)
  },
}
