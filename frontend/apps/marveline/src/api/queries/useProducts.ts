import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { productsApi } from '../products'
import type { InventorySummary } from '../products'
export type { AuditLogEntry } from '../products'
import type { ProductCreate, ProductUpdate, ProductImage, ProductAvailabilityResponse, Product, PaginatedProducts } from '@/types/product'
import type { MaintenanceCreate, MaintenanceUpdate } from '@/types/maintenance'

export function useInventorySummary() {
  return useQuery<InventorySummary>({
    queryKey: [...queryKeys.products.all, 'inventory-summary'] as const,
    queryFn: () => productsApi.getInventorySummary(),
    staleTime: 60 * 1000,
  })
}

export function useProductsList(
  params?: Parameters<typeof productsApi.listProducts>[0],
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.products.list(params ?? {}),
    queryFn: () => productsApi.listProducts(params),
    enabled,
  })
}

export function useLowStockProducts(params?: { threshold?: number; limit?: number; skip?: number }) {
  return useQuery({
    queryKey: queryKeys.products.lowStock(params ?? {}),
    queryFn: () => productsApi.listLowStock(params),
    staleTime: 60 * 1000,
  })
}

export function useProductMaintenances(productId: number | null) {
  return useQuery({
    queryKey: queryKeys.products.maintenances(productId!),
    queryFn: () => productsApi.listMaintenances(productId!),
    enabled: productId !== null,
  })
}

export function useCreateMaintenance(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: MaintenanceCreate) => productsApi.createMaintenance(productId, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.products.maintenances(productId) }) },
  })
}

export function useUpdateMaintenance(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: MaintenanceUpdate }) =>
      productsApi.updateMaintenance(productId, id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.products.maintenances(productId) }) },
  })
}

export function useDeleteMaintenance(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => productsApi.deleteMaintenance(productId, id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.products.maintenances(productId) }) },
  })
}

export function useProductAudit(id: number | null) {
  return useQuery({
    queryKey: queryKeys.products.audit(id!),
    queryFn: () => productsApi.getProductAudit(id!),
    enabled: id !== null,
  })
}

export function useProductDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.products.detail(id!),
    queryFn: () => productsApi.getProduct(id!),
    enabled: id !== null,
  })
}

// --- Products mutations ---

export function useCreateProduct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ProductCreate) => productsApi.createProduct(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.products.all }) },
  })
}

export function useUpdateProduct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProductUpdate }) => productsApi.updateProduct(id, data),

    onMutate: async ({ id, data }) => {
      await qc.cancelQueries({ queryKey: queryKeys.products.lists() })

      const previousLists = qc.getQueriesData<PaginatedProducts>({
        queryKey: queryKeys.products.lists(),
      })

      qc.setQueriesData<PaginatedProducts>(
        { queryKey: queryKeys.products.lists() },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.map((p: Product) =>
              p.id === id ? { ...p, ...data } : p
            ),
          }
        }
      )

      return { previousLists }
    },

    onError: (_err, _vars, context) => {
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data)
        })
      }
    },

    onSettled: (_r, _e, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.products.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.products.lists() })
    },
  })
}

export function useDeleteProduct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => productsApi.deleteProduct(id),

    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: queryKeys.products.lists() })

      const previousLists = qc.getQueriesData<PaginatedProducts>({
        queryKey: queryKeys.products.lists(),
      })

      qc.setQueriesData<PaginatedProducts>(
        { queryKey: queryKeys.products.lists() },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.filter((p: Product) => p.id !== id),
            total: old.total - 1,
          }
        }
      )

      return { previousLists }
    },

    onError: (_err, _vars, context) => {
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data)
        })
      }
    },

    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.products.all })
    },
  })
}

// --- Images gallery ---

export function useProductImages(productId: number | null) {
  return useQuery({
    queryKey: queryKeys.products.images(productId!),
    queryFn: () => productsApi.listImages(productId!),
    enabled: productId !== null,
  })
}

export function useAddProductImage(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => productsApi.addImage(productId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.products.images(productId) })
      qc.invalidateQueries({ queryKey: queryKeys.products.detail(productId) })
    },
  })
}

export function useDeleteProductImage(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (imageId: number) => productsApi.deleteImage(productId, imageId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.products.images(productId) }) },
  })
}

export function useSetPrimaryImage(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (imageId: number) => productsApi.setPrimaryImage(productId, imageId),
    onSuccess: (_r: ProductImage) => {
      qc.invalidateQueries({ queryKey: queryKeys.products.images(productId) })
      qc.invalidateQueries({ queryKey: queryKeys.products.detail(productId) })
    },
  })
}

export function useProductAvailability(
  productId: number | null,
  dateFrom: string | null,
  dateTo: string | null,
) {
  return useQuery<ProductAvailabilityResponse>({
    queryKey: queryKeys.catalogue.availability(productId!, { dateFrom, dateTo }),
    queryFn: () => productsApi.getAvailability(productId!, dateFrom!, dateTo!),
    enabled: productId !== null && !!dateFrom && !!dateTo,
  })
}

export function useUploadProductImage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ productId, file }: { productId: number; file: File }) =>
      productsApi.uploadProductImage(productId, file),
    onSuccess: (_r, { productId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.products.detail(productId) })
      qc.invalidateQueries({ queryKey: queryKeys.products.images(productId) })
    },
  })
}

export function useImportProductsCsv() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => productsApi.importCsv(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.products.all })
    },
  })
}
