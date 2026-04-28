import { api } from './fetchClient'
import type {
  Category,
  CategoryTreeNode,
  CategoryCreate,
  CategoryUpdate,
} from '../types/product'

export const categoriesApi = {
  getCategories: async (activeOnly = true): Promise<Category[]> => {
    const qs = new URLSearchParams({
      active_only: String(activeOnly),
      limit: '1000',
    }).toString()
    const data = await api.get<{ items: Category[] }>(`/categories?${qs}`)
    return data.items
  },

  getCategoryTree: async (): Promise<CategoryTreeNode[]> => {
    return api.get<CategoryTreeNode[]>('/categories/tree')
  },

  // CRUD
  getCategory: async (id: number): Promise<Category> => {
    return api.get<Category>(`/categories/${id}`)
  },

  createCategory: async (category: CategoryCreate): Promise<Category> => {
    return api.post<Category>('/categories', category)
  },

  updateCategory: async (id: number, category: CategoryUpdate): Promise<Category> => {
    return api.patch<Category>(`/categories/${id}`, category)
  },

  deleteCategory: async (id: number): Promise<void> => {
    await api.delete(`/categories/${id}`)
  },
}
