import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { categoriesApi } from '../categories'
import type { CategoryCreate, CategoryUpdate } from '@/types/product'

export function useCategoriesList(activeOnly = true, enabled = true) {
  return useQuery({
    queryKey: queryKeys.categories.list(activeOnly),
    queryFn: () => categoriesApi.getCategories(activeOnly),
    enabled,
    staleTime: 5 * 60 * 1000,
  })
}

export function useCategoryTree() {
  return useQuery({
    queryKey: queryKeys.categories.tree(),
    queryFn: () => categoriesApi.getCategoryTree(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useCategoryDetail(id: number | null) {
  return useQuery({
    queryKey: ['categories', 'detail', id],
    queryFn: () => categoriesApi.getCategory(id!),
    enabled: id !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CategoryCreate) => categoriesApi.createCategory(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories.all })
    },
  })
}

export function useUpdateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CategoryUpdate }) =>
      categoriesApi.updateCategory(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories.all })
    },
  })
}

export function useDeleteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => categoriesApi.deleteCategory(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories.all })
    },
  })
}
