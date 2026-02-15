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
  // List with filters — Backend utilise skip/limit et category (string)
  getProducts: async (params?: {
    page?: number
    page_size?: number
    category?: string
    available_only?: boolean
    active_only?: boolean
  }): Promise<PaginatedProducts> => {
    const pageSize = params?.page_size || 20
    const page = params?.page || 1
    const backendParams: Record<string, unknown> = {
      skip: (page - 1) * pageSize,
      limit: pageSize,
    }
    if (params?.category) backendParams.category = params.category
    if (params?.available_only) backendParams.available_only = true
    if (params?.active_only !== undefined) backendParams.is_active = params.active_only

    const { data } = await apiClient.get('/products', { params: backendParams })
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

  getFeatured: async (): Promise<Product[]> => {
    const { data } = await apiClient.get('/products/featured')
    const items = Array.isArray(data.items) ? data.items : (Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []))
    return items
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
    return data.data || data || { in_stock: 0, low_stock: 0, out_of_stock: 0, total: 0 }
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
    const items = Array.isArray(data.items) ? data.items : (Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []))
    return items
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
    const items = Array.isArray(data.items) ? data.items : (Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []))
    return items
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
