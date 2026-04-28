import { api } from './fetchClient'
import type {
  CustomerResponse,
  CustomerCreate,
  CustomerUpdate,
  PaginatedCustomers,
  CustomerType,
  CustomerHistory,
  CustomerRFM,
  CustomerRFMResponse,
  CustomerImportReport,
} from '../types/customer'

export const customersApi = {
  listCustomers: async (params?: {
    skip?: number
    limit?: number
    search_query?: string
    customer_type?: CustomerType
    is_active?: boolean
    has_scheduled_relances?: boolean
  }): Promise<PaginatedCustomers> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.search_query) p.search_query = params.search_query
    if (params?.customer_type) p.customer_type = params.customer_type
    if (params?.is_active !== undefined) p.is_active = String(params.is_active)
    if (params?.has_scheduled_relances) p.has_scheduled_relances = 'true'
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedCustomers>(`/customers?${qs}`)
  },

  getCustomer: async (id: number): Promise<CustomerResponse> => {
    return api.get<CustomerResponse>(`/customers/${id}`)
  },

  createCustomer: async (customer: CustomerCreate): Promise<CustomerResponse> => {
    return api.post<CustomerResponse>('/customers', customer)
  },

  updateCustomer: async (id: number, customer: CustomerUpdate): Promise<CustomerResponse> => {
    return api.patch<CustomerResponse>(`/customers/${id}`, customer)
  },

  deleteCustomer: async (id: number): Promise<void> => {
    await api.delete(`/customers/${id}`)
  },

  getCustomerHistory: async (id: number): Promise<CustomerHistory> => {
    return api.get<CustomerHistory>(`/customers/${id}/history`)
  },

  getRFM: async (): Promise<CustomerRFMResponse> => {
    return api.get<CustomerRFMResponse>('/customers/rfm')
  },

  getCustomerRFMProfile: async (id: number): Promise<CustomerRFM> => {
    return api.get<CustomerRFM>(`/customers/${id}/rfm-profile`)
  },

  sendRfmCampaign: async (payload: {
    segment: string
    subject: string
    message: string
  }): Promise<{ segment: string; recipients_count: number; sent_count: number; failed_count: number }> => {
    return api.post('/customers/rfm/campaign', payload)
  },

  importCsv: async (file: File): Promise<CustomerImportReport> => {
    const form = new FormData()
    form.append('file', file)
    return api.post<CustomerImportReport>('/customers/import', form)
  },
}
