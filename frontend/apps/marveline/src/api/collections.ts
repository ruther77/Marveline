import { api } from './fetchClient'
import type {
  Collection,
  CollectionCreate,
  CollectionUpdate,
  CollectionWithProducts,
  CollectionListResponse,
} from '@/types/collection'

export const collectionsApi = {
  list: async (params?: { skip?: number; limit?: number }): Promise<CollectionListResponse> => {
    const qs = new URLSearchParams()
    if (params?.skip !== undefined) qs.set('skip', String(params.skip))
    if (params?.limit !== undefined) qs.set('limit', String(params.limit))
    const suffix = qs.toString() ? `?${qs}` : ''
    return api.get<CollectionListResponse>(`/collections${suffix}`)
  },

  get: async (id: number): Promise<CollectionWithProducts> => {
    return api.get<CollectionWithProducts>(`/collections/${id}`)
  },

  create: async (data: CollectionCreate): Promise<Collection> => {
    return api.post<Collection>('/collections', data)
  },

  update: async (id: number, data: CollectionUpdate): Promise<Collection> => {
    return api.patch<Collection>(`/collections/${id}`, data)
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/collections/${id}`)
  },

  addProducts: async (id: number, productIds: number[]): Promise<CollectionWithProducts> => {
    return api.post<CollectionWithProducts>(`/collections/${id}/products`, { product_ids: productIds })
  },

  removeProduct: async (collectionId: number, productId: number): Promise<CollectionWithProducts> => {
    return api.delete<CollectionWithProducts>(`/collections/${collectionId}/products/${productId}`)
  },
}
