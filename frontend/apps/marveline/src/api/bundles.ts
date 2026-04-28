import { api } from './fetchClient'
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
  listBundles: async (params?: {
    skip?: number
    limit?: number
    featured?: boolean
    active_only?: boolean
  }): Promise<PaginatedBundles> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.featured !== undefined) p.featured = String(params.featured)
    if (params?.active_only !== undefined) p.active_only = String(params.active_only)
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedBundles>(`/bundles?${qs}`)
  },

  getBundle: async (id: number): Promise<BundleWithItems> => {
    return api.get<BundleWithItems>(`/bundles/${id}`)
  },

  createBundle: async (bundle: BundleCreate): Promise<Bundle> => {
    return api.post<Bundle>('/bundles', bundle)
  },

  updateBundle: async (id: number, bundle: BundleUpdate): Promise<Bundle> => {
    return api.patch<Bundle>(`/bundles/${id}`, bundle)
  },

  deleteBundle: async (id: number): Promise<void> => {
    await api.delete(`/bundles/${id}`)
  },

  // Items
  addItem: async (bundleId: number, item: BundleItemCreate): Promise<BundleItem> => {
    return api.post<BundleItem>(`/bundles/${bundleId}/items`, item)
  },

  updateItem: async (
    bundleId: number,
    itemId: number,
    item: { quantity: number }
  ): Promise<BundleItem> => {
    return api.patch<BundleItem>(`/bundles/${bundleId}/items/${itemId}`, item)
  },

  removeItem: async (bundleId: number, itemId: number): Promise<void> => {
    await api.delete(`/bundles/${bundleId}/items/${itemId}`)
  },

  calculatePrice: async (bundleId: number): Promise<BundlePriceCalc> => {
    return api.get<BundlePriceCalc>(`/bundles/${bundleId}/calculate-price`)
  },
}
