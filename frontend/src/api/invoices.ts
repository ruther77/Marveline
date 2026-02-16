import apiClient from './client'
import type {
  InvoiceListItem,
  InvoiceDetail,
  InvoiceCreateRequest,
  InvoiceUpdateRequest,
  AddPaymentRequest,
  InvoiceStatus,
} from '../types/invoice'

export const invoicesApi = {
  getInvoices: async (params?: {
    page?: number
    page_size?: number
    status?: InvoiceStatus
    reservation_id?: number
  }): Promise<{
    items: InvoiceListItem[]
    total: number
    page: number
    page_size: number
    total_pages: number
  }> => {
    const page = params?.page || 1
    const pageSize = params?.page_size || 20
    const skip = (page - 1) * pageSize
    const queryParams: Record<string, unknown> = { skip, limit: pageSize }
    if (params?.status) queryParams.status_filter = params.status
    if (params?.reservation_id) queryParams.reservation_id = params.reservation_id

    const { data } = await apiClient.get('/invoices', { params: queryParams })
    const items = Array.isArray(data.items) ? data.items : (Array.isArray(data.data) ? data.data : [])
    const total = data.total ?? 0
    return {
      items,
      total,
      page,
      page_size: pageSize,
      total_pages: Math.ceil(total / pageSize) || 0,
    }
  },

  getInvoice: async (id: number): Promise<InvoiceDetail> => {
    const { data } = await apiClient.get(`/invoices/${id}`)
    return data.data || data
  },

  getOverdueInvoices: async (limit?: number): Promise<InvoiceListItem[]> => {
    const { data } = await apiClient.get('/invoices/overdue', {
      params: limit ? { limit } : undefined,
    })
    return data.data || data
  },

  createInvoice: async (invoice: InvoiceCreateRequest): Promise<InvoiceDetail> => {
    const { data } = await apiClient.post('/invoices', invoice)
    return data.data || data
  },

  updateInvoice: async (id: number, invoice: InvoiceUpdateRequest): Promise<InvoiceDetail> => {
    const { data } = await apiClient.patch(`/invoices/${id}`, invoice)
    return data.data || data
  },

  addPayment: async (id: number, payment: AddPaymentRequest): Promise<InvoiceDetail> => {
    const { data } = await apiClient.post(`/invoices/${id}/add-payment`, payment)
    return data.data || data
  },

  cancelInvoice: async (id: number): Promise<InvoiceDetail> => {
    const { data } = await apiClient.post(`/invoices/${id}/cancel`)
    return data.data || data
  },
}
