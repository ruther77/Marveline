import apiClient from './client'
import type {
  Bundle,
  BundleWithItems,
  BundleCreate,
  BundleUpdate,
  BundleItem,
  BundleItemCreate,
  PaginatedBundles,
} from '../types/product'

export const bundlesApi = {
  getBundles: async (params?: {
    page?: number
    page_size?: number
    featured?: boolean
    active_only?: boolean
  }): Promise<PaginatedBundles> => {
    const { data } = await apiClient.get('/bundles', { params })
    // Backend retourne { success, data, pagination }
    return {
      items: data.data || [],
      total: data.pagination?.total_items || 0,
      page: data.pagination?.page || 1,
      page_size: data.pagination?.page_size || 20,
      total_pages: data.pagination?.total_pages || 0,
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
    itemId: number,
    item: { quantity: number }
  ): Promise<BundleItem> => {
    const { data } = await apiClient.patch(`/bundles/items/${itemId}`, item)
    return data.data || data
  },

  removeItem: async (itemId: number): Promise<void> => {
    await apiClient.delete(`/bundles/items/${itemId}`)
  },

  calculatePrice: async (bundleId: number): Promise<{
    total_price: number
    discount_amount: number
    final_price: number
  }> => {
    const { data } = await apiClient.get(`/bundles/${bundleId}/calculate-price`)
    return data.data || data
  },
}
