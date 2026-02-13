import apiClient from './client'
import type {
  Product,
  ProductWithRelations,
  ProductCreate,
  ProductUpdate,
  ProductVariation,
  ProductVariationCreate,
  ProductImage,
  ProductImageCreate,
  PaginatedProducts,
} from '../types/product'

export const productsApi = {
  // List with filters
  getProducts: async (params?: {
    page?: number
    page_size?: number
    category_id?: number
    search?: string
    featured?: boolean
    active_only?: boolean
  }): Promise<PaginatedProducts> => {
    const { data } = await apiClient.get('/products', { params })
    // Backend retourne { success, data, pagination }
    return {
      items: data.data || [],
      total: data.pagination?.total_items || 0,
      page: data.pagination?.page || 1,
      page_size: data.pagination?.page_size || 20,
      total_pages: data.pagination?.total_pages || 0,
    }
  },

  getFeatured: async (): Promise<Product[]> => {
    const { data } = await apiClient.get('/products/featured')
    return data.data || data || []
  },

  // Statistics
  getStatistics: async (activeOnly = true): Promise<{
    in_stock: number
    low_stock: number
    out_of_stock: number
    total: number
  }> => {
    const { data } = await apiClient.get('/products/statistics', {
      params: { active_only: activeOnly },
    })
    return data.data || data
  },

  // CRUD
  getProduct: async (id: number): Promise<ProductWithRelations> => {
    const { data } = await apiClient.get(`/products/${id}`)
    return data.data || data
  },

  createProduct: async (product: ProductCreate): Promise<Product> => {
    const { data } = await apiClient.post('/products', product)
    return data.data || data
  },

  updateProduct: async (
    id: number,
    product: ProductUpdate
  ): Promise<Product> => {
    const { data } = await apiClient.patch(`/products/${id}`, product)
    return data.data || data
  },

  deleteProduct: async (id: number): Promise<void> => {
    await apiClient.delete(`/products/${id}`)
  },

  // Stock
  updateStock: async (id: number, quantity: number): Promise<Product> => {
    const { data } = await apiClient.patch(`/products/${id}/stock`, {
      stock_quantity: quantity,
    })
    return data.data || data
  },

  // Variations
  getVariations: async (productId: number): Promise<ProductVariation[]> => {
    const { data } = await apiClient.get(`/products/${productId}/variations`)
    return data.data || data || []
  },

  addVariation: async (
    productId: number,
    variation: ProductVariationCreate
  ): Promise<ProductVariation> => {
    const { data } = await apiClient.post(
      `/products/${productId}/variations`,
      variation
    )
    return data.data || data
  },

  updateVariation: async (
    variationId: number,
    variation: Partial<ProductVariationCreate>
  ): Promise<ProductVariation> => {
    const { data } = await apiClient.patch(
      `/products/variations/${variationId}`,
      variation
    )
    return data.data || data
  },

  deleteVariation: async (variationId: number): Promise<void> => {
    await apiClient.delete(`/products/variations/${variationId}`)
  },

  // Images
  getImages: async (productId: number): Promise<ProductImage[]> => {
    const { data } = await apiClient.get(`/products/${productId}/images`)
    return data.data || data || []
  },

  addImage: async (
    productId: number,
    image: ProductImageCreate
  ): Promise<ProductImage> => {
    const { data } = await apiClient.post(
      `/products/${productId}/images`,
      image
    )
    return data.data || data
  },

  setPrimaryImage: async (imageId: number): Promise<ProductImage> => {
    const { data } = await apiClient.patch(
      `/products/images/${imageId}/set-primary`
    )
    return data.data || data
  },

  deleteImage: async (imageId: number): Promise<void> => {
    await apiClient.delete(`/products/images/${imageId}`)
  },
}
