import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { productVariantsApi } from '../product_variants'
import type { ProductVariantCreate, ProductVariantUpdate } from '@/types/product_variant'

export function useProductVariantsList(productId: number | null) {
  return useQuery({
    queryKey: queryKeys.productVariants.list(productId!),
    queryFn: () => productVariantsApi.getVariants(productId!),
    enabled: productId !== null && !isNaN(productId),
  })
}

export function useProductVariantDetail(productId: number | null, variantId: number | null) {
  return useQuery({
    queryKey: ['product-variants', productId, 'detail', variantId],
    queryFn: () => productVariantsApi.getVariant(productId!, variantId!),
    enabled: productId !== null && variantId !== null,
  })
}

export function useCreateProductVariant(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ProductVariantCreate) =>
      productVariantsApi.createVariant(productId, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.productVariants.list(productId) }) },
  })
}

export function useUpdateProductVariant(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProductVariantUpdate }) =>
      productVariantsApi.updateVariant(productId, id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.productVariants.list(productId) }) },
  })
}

export function useDeleteProductVariant(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (variantId: number) =>
      productVariantsApi.deleteVariant(productId, variantId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.productVariants.list(productId) }) },
  })
}
