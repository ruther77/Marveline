import apiClient from './client'
import type {
  FeatureFlag,
  FeatureFlagList,
  FeatureFlagCreate,
  FeatureFlagUpdate,
} from '@/types/featureFlag'
import type { PaginatedResponse } from '@/types'

export const featureFlagsApi = {
  list: async (page = 1, perPage = 50): Promise<PaginatedResponse<FeatureFlagList>> => {
    const skip = (page - 1) * perPage
    const response = await apiClient.get('/features', {
      params: { skip, limit: perPage },
    })
    const data = response.data
    const items = Array.isArray(data.items) ? data.items : []
    const total = data.total || 0
    const pages = Math.ceil(total / perPage)
    return { items, total, page, per_page: perPage, pages }
  },

  get: async (id: number): Promise<FeatureFlag> => {
    const response = await apiClient.get(`/features/${id}`)
    return response.data
  },

  create: async (data: FeatureFlagCreate): Promise<FeatureFlag> => {
    const response = await apiClient.post('/features', data)
    return response.data
  },

  update: async (id: number, data: FeatureFlagUpdate): Promise<FeatureFlag> => {
    const response = await apiClient.patch(`/features/${id}`, data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/features/${id}`)
  },

  toggle: async (id: number, is_enabled: boolean): Promise<FeatureFlag> => {
    const response = await apiClient.patch(`/features/${id}`, { is_enabled })
    return response.data
  },
}
