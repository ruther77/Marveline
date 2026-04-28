import { api } from './fetchClient'
import type {
  ApiKey,
  ApiKeyList,
  ApiKeyCreated,
  ApiKeyCreate,
  ApiKeyUpdate,
} from '@/types/apiKey'
import type { PaginatedResponse } from '@/types'

export const apiKeysApi = {
  listApiKeys: async (params?: {
    skip?: number
    limit?: number
    include_inactive?: boolean
  }): Promise<PaginatedResponse<ApiKeyList>> => {
    const qs = new URLSearchParams({
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 50),
      include_inactive: String(params?.include_inactive ?? false),
    }).toString()
    return api.get<PaginatedResponse<ApiKeyList>>(`/api-keys?${qs}`)
  },

  get: async (id: number): Promise<ApiKey> => {
    return api.get<ApiKey>(`/api-keys/${id}`)
  },

  create: async (data: ApiKeyCreate): Promise<ApiKeyCreated> => {
    return api.post<ApiKeyCreated>('/api-keys', data)
  },

  update: async (id: number, data: ApiKeyUpdate): Promise<ApiKey> => {
    return api.patch<ApiKey>(`/api-keys/${id}`, data)
  },

  delete: async (id: number): Promise<ApiKey> => {
    return api.delete<ApiKey>(`/api-keys/${id}`)
  },

  rotate: async (id: number): Promise<ApiKeyCreated> => {
    return api.post<ApiKeyCreated>(`/api-keys/${id}/rotate`)
  },
}
