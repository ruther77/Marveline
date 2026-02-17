import apiClient from './client'
import type {
  Bundle,
  BundleWithItems,
  BundleCreate,
  BundleUpdate,
  BundleItem,
  BundleItemCreate,
  PaginatedBundles,
  BundlePriceCalc,
} from '../types/product'

export const bundlesApi = {
  // List — Backend retourne PaginatedResponse: { items: [...], total, skip, limit }
  getBundles: async (params?: {
    page?: number
    page_size?: number
    featured?: boolean
    active_only?: boolean
  }): Promise<PaginatedBundles> => {
    const pageSize = params?.page_size || 20
    const page = params?.page || 1
    const backendParams: Record<string, unknown> = {
      skip: (page - 1) * pageSize,
      limit: pageSize,
    }
    if (params?.featured !== undefined) backendParams.featured = params.featured
    if (params?.active_only !== undefined) backendParams.active_only = params.active_only

    const { data } = await apiClient.get('/bundles', { params: backendParams })
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

  getBundle: async (id: number): Promise<BundleWithItems> => {
    const { data } = await apiClient.get(`/bundles/${id}`)
    return data.data || data
  },

  createBundle: async (bundle: BundleCreate): Promise<Bundle> => {
    const { data } = await apiClient.post('/bundles', bundle)
    return data.data || data
  },

  updateBundle: async (id: number, bundle: BundleUpdate): Promise<Bundle> => {
    const { data } = await apiClient.patch(`/bundles/${id}`, bundle)
    return data.data || data
  },

  deleteBundle: async (id: number): Promise<void> => {
    await apiClient.delete(`/bundles/${id}`)
  },

  // Items
  addItem: async (
    bundleId: number,
    item: BundleItemCreate
  ): Promise<BundleItem> => {
    const { data } = await apiClient.post(`/bundles/${bundleId}/items`, item)
    return data.data || data
  },

  updateItem: async (
    bundleId: number,
    itemId: number,
    item: { quantity: number }
  ): Promise<BundleItem> => {
    const { data } = await apiClient.patch(`/bundles/${bundleId}/items/${itemId}`, item)
    return data.data || data
  },

  removeItem: async (bundleId: number, itemId: number): Promise<void> => {
    await apiClient.delete(`/bundles/${bundleId}/items/${itemId}`)
  },

  calculatePrice: async (bundleId: number): Promise<BundlePriceCalc> => {
    const { data } = await apiClient.get(`/bundles/${bundleId}/calculate-price`)
    return data.data || data
  },
}
