import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { inventoryApi } from '../inventory'

export async function fetchProductStockDetail(productId: number) {
  return inventoryApi.getProductStock(productId)
}

export function useProductsStock(productIds: number[]) {
  return useQuery({
    queryKey: ['inventory', 'products-stock', productIds],
    queryFn: () => inventoryApi.getProductsStock(productIds),
    enabled: productIds.length > 0,
    staleTime: 60 * 1000,
  })
}


export function useMovementsList(params?: Parameters<typeof inventoryApi.listMovements>[0], enabled = true) {
  return useQuery({
    queryKey: queryKeys.inventory.movements.list(params ?? {}),
    queryFn: () => inventoryApi.listMovements(params),
    staleTime: 60 * 1000,
    enabled,
  })
}

export function useMovementDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.inventory.movements.detail(id!),
    queryFn: () => inventoryApi.getMovement(id!),
    enabled: id !== null,
    staleTime: 60 * 1000,
  })
}

export function useInventoryStats(startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: queryKeys.inventory.stats(),
    queryFn: () => inventoryApi.getStatistics(startDate, endDate),
    staleTime: 60 * 1000,
  })
}

export function useProductStock(productId: number | null) {
  return useQuery({
    queryKey: queryKeys.inventory.stockItems(productId!),
    queryFn: () => inventoryApi.getProductStock(productId!),
    enabled: productId !== null,
    staleTime: 60 * 1000,
  })
}

export function useStockItemHistory(productId: number | null, itemId: number | null) {
  return useQuery({
    queryKey: queryKeys.inventory.stockItemHistory(productId!, itemId!),
    queryFn: () => inventoryApi.getStockItemHistory(productId!, itemId!),
    enabled: productId !== null && itemId !== null,
    staleTime: 60 * 1000,
  })
}

export function usePendingInspections() {
  return useQuery({
    queryKey: queryKeys.inventory.pendingInspections(),
    queryFn: () => inventoryApi.getPendingInspections(),
    staleTime: 60 * 1000,
  })
}

export function useLateMovements() {
  return useQuery({
    queryKey: ['inventory', 'movements', 'late'],
    queryFn: () => inventoryApi.getLateMovements(),
    staleTime: 60 * 1000,
  })
}

export function useCreateMovement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof inventoryApi.createMovement>[0]) =>
      inventoryApi.createMovement(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.inventory.all }) },
  })
}

export function useUpdateMovement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof inventoryApi.updateMovement>[1] }) =>
      inventoryApi.updateMovement(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.lists() })
    },
  })
}

export function useDeleteMovement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => inventoryApi.deleteMovement(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.inventory.all }) },
  })
}

export function useCompleteMovement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => inventoryApi.completeMovement(id),
    onSuccess: (_r, id) => {
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.inventory.all })
      qc.invalidateQueries({ queryKey: queryKeys.products.all })
      qc.invalidateQueries({ queryKey: queryKeys.stock.all })
    },
  })
}

export function useAddMovementItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ movementId, item }: { movementId: number; item: Parameters<typeof inventoryApi.addItem>[1] }) =>
      inventoryApi.addItem(movementId, item),
    onSuccess: (_r, { movementId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.detail(movementId) })
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.lists() })
    },
  })
}

export function useUpdateMovementItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ movementId, itemId, item }: { movementId: number; itemId: number; item: Parameters<typeof inventoryApi.updateItem>[2] }) =>
      inventoryApi.updateItem(movementId, itemId, item),
    onSuccess: (_r, { movementId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.detail(movementId) })
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.lists() })
    },
  })
}

export function useRemoveMovementItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ movementId, itemId }: { movementId: number; itemId: number }) =>
      inventoryApi.removeItem(movementId, itemId),
    onSuccess: (_r, { movementId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.detail(movementId) })
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.lists() })
    },
  })
}
