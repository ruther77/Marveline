import apiClient from './client'
import type {
  Category,
  CategoryTreeNode,
  CategoryCreate,
  CategoryUpdate,
} from '../types/product'

export const categoriesApi = {
  // List
  getCategories: async (activeOnly = true): Promise<Category[]> => {
    const { data } = await apiClient.get('/categories', {
      params: { active_only: activeOnly },
    })
    // Backend retourne { categories: [...], total: ... }
    return data.categories || data.data || data || []
  },

  // Tree
  getCategoryTree: async (): Promise<CategoryTreeNode[]> => {
    const { data } = await apiClient.get('/categories/tree')
    // Backend retourne { tree: [...], total: ... }
    return data.tree || data.data || data || []
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
