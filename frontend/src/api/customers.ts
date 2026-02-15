import apiClient from './client'
import type { CustomerList, PaginatedCustomers } from '../types/customer'

export const customersApi = {
  getCustomers: async (params?: {
    page?: number
    page_size?: number
    search_query?: string
  }): Promise<PaginatedCustomers> => {
    const pageSize = params?.page_size || 20
    const page = params?.page || 1
    const backendParams: Record<string, unknown> = {
      skip: (page - 1) * pageSize,
      limit: pageSize,
    }
    if (params?.search_query) backendParams.search_query = params.search_query

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

  getCustomer: async (id: number): Promise<CustomerList> => {
    const { data } = await apiClient.get(`/customers/${id}`)
    return data.data || data
  },
}
