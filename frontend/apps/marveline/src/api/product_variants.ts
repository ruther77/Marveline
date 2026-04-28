import { api } from './fetchClient'
import type { ProductVariant, ProductVariantCreate, ProductVariantUpdate } from '../types/product_variant'

export const productVariantsApi = {
  getVariants: async (productId: number): Promise<ProductVariant[]> => {
    const data = await api.get<ProductVariant[] | { items?: ProductVariant[] }>(`/products/${productId}/variants`)
    if (Array.isArray(data)) return data
    const obj = data as { items?: ProductVariant[] }
    return obj.items || []
  },

  getVariant: async (productId: number, variantId: number): Promise<ProductVariant> => {
    return api.get<ProductVariant>(`/products/${productId}/variants/${variantId}`)
  },

  createVariant: async (productId: number, variant: ProductVariantCreate): Promise<ProductVariant> => {
    return api.post<ProductVariant>(`/products/${productId}/variants`, variant)
  },

  updateVariant: async (
    productId: number,
    variantId: number,
    variant: ProductVariantUpdate
  ): Promise<ProductVariant> => {
    return api.patch<ProductVariant>(`/products/${productId}/variants/${variantId}`, variant)
  },

  deleteVariant: async (productId: number, variantId: number): Promise<void> => {
    await api.delete(`/products/${productId}/variants/${variantId}`)
  },
}
