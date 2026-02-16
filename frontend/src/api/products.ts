import apiClient from './client'
import type {
  Product,
  ProductWithRelations,
  ProductCreate,
  ProductUpdate,
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

}
