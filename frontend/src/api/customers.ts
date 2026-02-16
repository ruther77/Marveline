import apiClient from './client'
import type {
  CustomerList,
  CustomerResponse,
  CustomerCreate,
  CustomerUpdate,
  PaginatedCustomers,
  CustomerType,
} from '../types/customer'

export const customersApi = {
  getCustomers: async (params?: {
    page?: number
    page_size?: number
    search_query?: string
    customer_type?: CustomerType
    is_active?: boolean
  }): Promise<PaginatedCustomers> => {
    const pageSize = params?.page_size || 20
    const page = params?.page || 1
    const backendParams: Record<string, unknown> = {
      skip: (page - 1) * pageSize,
      limit: pageSize,
    }
    if (params?.search_query) backendParams.search_query = params.search_query
    if (params?.customer_type) backendParams.customer_type = params.customer_type
    if (params?.is_active !== undefined) backendParams.is_active = params.is_active

    const { data } = await apiClient.get('/customers', { params: backendParams })
    const items = Array.isArray(data.items) ? data.items : []
    const total = data.total ?? 0
    return {
      items,
      total,
      page,
      page_size: pageSize,
      total_pages: Math.ceil(total / pageSize) || 0,
    }
  },

  getCustomer: async (id: number): Promise<CustomerResponse> => {
    const { data } = await apiClient.get(`/customers/${id}`)
    return data.data || data
  },

  createCustomer: async (customer: CustomerCreate): Promise<CustomerResponse> => {
    const { data } = await apiClient.post('/customers', customer)
    return data.data || data
  },

  updateCustomer: async (id: number, customer: CustomerUpdate): Promise<CustomerResponse> => {
    const { data } = await apiClient.patch(`/customers/${id}`, customer)
    return data.data || data
  },

  deleteCustomer: async (id: number): Promise<void> => {
    await apiClient.delete(`/customers/${id}`)
  },
}
