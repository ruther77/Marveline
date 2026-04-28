import { api } from './fetchClient'
import type {
  FeatureFlag,
  FeatureFlagList,
  FeatureFlagCreate,
  FeatureFlagUpdate,
  FeatureFlagEvaluated,
} from '@/types/featureFlag'
import type { PaginatedResponse } from '@/types'

export const featureFlagsApi = {
  listFeatureFlags: async (params?: { skip?: number; limit?: number }): Promise<PaginatedResponse<FeatureFlagList>> => {
    const qs = new URLSearchParams({
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 50),
    }).toString()
    return api.get<PaginatedResponse<FeatureFlagList>>(`/features?${qs}`)
  },

  get: async (id: number): Promise<FeatureFlag> => {
    return api.get<FeatureFlag>(`/features/${id}`)
  },

  create: async (data: FeatureFlagCreate): Promise<FeatureFlag> => {
    return api.post<FeatureFlag>('/features', data)
  },

  update: async (id: number, data: FeatureFlagUpdate): Promise<FeatureFlag> => {
    return api.patch<FeatureFlag>(`/features/${id}`, data)
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/features/${id}`)
  },

  toggle: async (id: number, is_enabled: boolean): Promise<FeatureFlag> => {
    return api.patch<FeatureFlag>(`/features/${id}`, { is_enabled })
  },

  check: async (flagName: string, tenantId: number): Promise<FeatureFlagEvaluated> => {
    const encodedFlag = encodeURIComponent(flagName)
    return api.get<FeatureFlagEvaluated>(`/features/check/${encodedFlag}?tenant_id=${tenantId}`)
  },
}
