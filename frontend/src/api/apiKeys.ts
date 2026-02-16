import apiClient from './client'
import type {
  ApiKey,
  ApiKeyList,
  ApiKeyCreated,
  ApiKeyCreate,
  ApiKeyUpdate,
} from '@/types/apiKey'
import type { PaginatedResponse } from '@/types'

export const apiKeysApi = {
  list: async (
    page = 1,
    perPage = 50,
    includeInactive = false
  ): Promise<PaginatedResponse<ApiKeyList>> => {
    const skip = (page - 1) * perPage
    const response = await apiClient.get('/api-keys', {
      params: { skip, limit: perPage, include_inactive: includeInactive },
    })
    const data = response.data
    const items = Array.isArray(data.items) ? data.items : []
    const total = data.total || 0
    const pages = Math.ceil(total / perPage)
    return { items, total, page, per_page: perPage, pages }
  },

  get: async (id: number): Promise<ApiKey> => {
    const response = await apiClient.get(`/api-keys/${id}`)
    return response.data
  },

  create: async (data: ApiKeyCreate): Promise<ApiKeyCreated> => {
    const response = await apiClient.post('/api-keys', data)
    return response.data
  },

  update: async (id: number, data: ApiKeyUpdate): Promise<ApiKey> => {
    const response = await apiClient.patch(`/api-keys/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<ApiKey> => {
    const response = await apiClient.delete(`/api-keys/${id}`)
    return response.data
  },

  rotate: async (id: number): Promise<ApiKeyCreated> => {
    const response = await apiClient.post(`/api-keys/${id}/rotate`)
    return response.data
  },
}
