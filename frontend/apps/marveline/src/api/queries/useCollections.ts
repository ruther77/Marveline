import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { collectionsApi } from '../collections'
import type { CollectionCreate, CollectionUpdate } from '@/types/collection'

export function useCollectionsList(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: queryKeys.collections.list(params),
    queryFn: () => collectionsApi.list(params),
  })
}

export function useCollectionDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.collections.detail(id!),
    queryFn: () => collectionsApi.get(id!),
    enabled: id !== null,
  })
}

export function useCreateCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CollectionCreate) => collectionsApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.collections.all }) },
  })
}

export function useUpdateCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CollectionUpdate }) =>
      collectionsApi.update(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.collections.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.collections.all })
    },
  })
}

export function useDeleteCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => collectionsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.collections.all }) },
  })
}

export function useAddProductsToCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ collectionId, productIds }: { collectionId: number; productIds: number[] }) =>
      collectionsApi.addProducts(collectionId, productIds),
    onSuccess: (_r, { collectionId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.collections.detail(collectionId) })
    },
  })
}

export function useRemoveProductFromCollection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ collectionId, productId }: { collectionId: number; productId: number }) =>
      collectionsApi.removeProduct(collectionId, productId),
    onSuccess: (_r, { collectionId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.collections.detail(collectionId) })
    },
  })
}
