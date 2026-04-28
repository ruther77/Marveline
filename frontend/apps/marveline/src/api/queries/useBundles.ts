import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { bundlesApi } from '../bundles'
import type { BundleCreate, BundleUpdate, BundleItemCreate } from '@/types/product'

export function useBundlesList(
  params?: Parameters<typeof bundlesApi.listBundles>[0],
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.bundles.list(params ?? {}),
    queryFn: () => bundlesApi.listBundles(params),
    enabled,
  })
}

export function useBundleDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.bundles.detail(id!),
    queryFn: () => bundlesApi.getBundle(id!),
    enabled: id !== null,
  })
}

export function useBundlePrice(id: number | null) {
  return useQuery({
    queryKey: [...queryKeys.bundles.detail(id!), 'price'],
    queryFn: () => bundlesApi.calculatePrice(id!),
    enabled: id !== null,
  })
}

export function useCreateBundle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: BundleCreate) => bundlesApi.createBundle(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.bundles.all }) },
  })
}

export function useUpdateBundle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: BundleUpdate }) => bundlesApi.updateBundle(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.bundles.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.bundles.lists() })
    },
  })
}

export function useDeleteBundle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => bundlesApi.deleteBundle(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.bundles.all }) },
  })
}

export function useAddBundleItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ bundleId, item }: { bundleId: number; item: BundleItemCreate }) =>
      bundlesApi.addItem(bundleId, item),
    onSuccess: (_r, { bundleId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.bundles.detail(bundleId) })
      qc.invalidateQueries({ queryKey: [...queryKeys.bundles.detail(bundleId), 'price'] })
    },
  })
}

export function useUpdateBundleItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ bundleId, itemId, quantity }: { bundleId: number; itemId: number; quantity: number }) =>
      bundlesApi.updateItem(bundleId, itemId, { quantity }),
    onSuccess: (_r, { bundleId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.bundles.detail(bundleId) })
      qc.invalidateQueries({ queryKey: [...queryKeys.bundles.detail(bundleId), 'price'] })
    },
  })
}

export function useRemoveBundleItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ bundleId, itemId }: { bundleId: number; itemId: number }) =>
      bundlesApi.removeItem(bundleId, itemId),
    onSuccess: (_r, { bundleId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.bundles.detail(bundleId) })
      qc.invalidateQueries({ queryKey: [...queryKeys.bundles.detail(bundleId), 'price'] })
    },
  })
}
