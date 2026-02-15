import apiClient from './client'
import type {
  Category,
  CategoryTreeNode,
  CategoryCreate,
  CategoryUpdate,
} from '../types/product'

export const categoriesApi = {
  // List — Backend retourne PaginatedResponse: { items: [...], total, skip, limit }
  getCategories: async (activeOnly = true): Promise<Category[]> => {
    const { data } = await apiClient.get('/categories', {
      params: { active_only: activeOnly },
    })
    const items = Array.isArray(data.items) ? data.items : (Array.isArray(data) ? data : [])
    return items
  },

  // Tree — Backend retourne list[CategoryTreeNode] (tableau direct)
  getCategoryTree: async (): Promise<CategoryTreeNode[]> => {
    const { data } = await apiClient.get('/categories/tree')
    return Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : [])
  },

  // CRUD
  getCategory: async (id: number): Promise<Category> => {
    const { data } = await apiClient.get(`/categories/${id}`)
    return data.data || data
  },

  createCategory: async (category: CategoryCreate): Promise<Category> => {
    const { data } = await apiClient.post('/categories', category)
    return data.data || data
  },

  updateCategory: async (
    id: number,
    category: CategoryUpdate
  ): Promise<Category> => {
    const { data } = await apiClient.patch(`/categories/${id}`, category)
    return data.data || data
  },

  deleteCategory: async (id: number): Promise<void> => {
    await apiClient.delete(`/categories/${id}`)
  },
}
