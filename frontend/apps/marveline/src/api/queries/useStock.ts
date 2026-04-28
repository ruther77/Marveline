import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { stockApi } from '@/api/stock'
import { inventoryApi } from '@/api/inventory'
import type { StockAdjustmentCreate, CountingEntry, ReorderRequest } from '@/types/stock_management'

// ── Niveaux de stock ──────────────────────────────────────────────────────

export function useStockLevels() {
  return useQuery({
    queryKey: queryKeys.stock.levels(),
    queryFn: () => stockApi.getLevels(),
    staleTime: 2 * 60 * 1000,
  })
}

// ── Réassort ──────────────────────────────────────────────────────────────

export function useReorderList() {
  return useQuery({
    queryKey: queryKeys.stock.reorder(),
    queryFn: () => stockApi.getReorderList(),
    staleTime: 2 * 60 * 1000,
  })
}

export function useCreateReorder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ReorderRequest) => stockApi.createReorder(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.stock.reorder() })
      qc.invalidateQueries({ queryKey: queryKeys.stock.levels() })
    },
  })
}

// ── Ajustements manuels ───────────────────────────────────────────────────

export function useStockAdjustments(productId?: number) {
  return useQuery({
    queryKey: queryKeys.stock.adjustments(productId),
    queryFn: () => stockApi.listAdjustments(productId),
    staleTime: 2 * 60 * 1000,
  })
}

export function useCreateAdjustment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: StockAdjustmentCreate) => stockApi.createAdjustment(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.stock.all })
      qc.invalidateQueries({ queryKey: queryKeys.stock.levels() })
    },
  })
}

// ── Inventaire physique ───────────────────────────────────────────────────

export function useActiveInventaire() {
  return useQuery({
    queryKey: [...queryKeys.stock.all, 'inventaire', 'active'] as const,
    queryFn: () => stockApi.getActiveInventaire(),
    retry: false,
    staleTime: 30 * 1000,
  })
}

export function useInventaireSession(sessionId: number | null) {
  return useQuery({
    queryKey: queryKeys.stock.inventaire(sessionId ?? 0),
    queryFn: () => stockApi.getInventaire(sessionId!),
    enabled: sessionId !== null,
    staleTime: 30 * 1000,
  })
}

export function useInventaireMutations() {
  const qc = useQueryClient()

  const start = useMutation({
    mutationFn: () => stockApi.startInventaire(),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.stock.inventaire(data.id), data)
    },
  })

  const update = useMutation({
    mutationFn: ({ sessionId, entries }: { sessionId: number; entries: CountingEntry[] }) =>
      stockApi.updateInventaire(sessionId, entries),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.stock.inventaire(data.id), data)
    },
  })

  const complete = useMutation({
    mutationFn: (sessionId: number) => stockApi.completeInventaire(sessionId),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.stock.inventaire(data.id), data)
      qc.invalidateQueries({ queryKey: queryKeys.stock.levels() })
    },
  })

  return { start, update, complete }
}

// ── Couverture stock ──────────────────────────────────────────────────────

export function useStockCoverage() {
  return useQuery({
    queryKey: queryKeys.stock.coverage(),
    queryFn: () => stockApi.getCoverage(),
    staleTime: 5 * 60 * 1000,
  })
}

// ── Stock item status ─────────────────────────────────────────────────────

export function useUpdateStockItemStatus(productId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ itemId, status }: { itemId: number; status: string }) =>
      inventoryApi.patchStockItemStatus(productId, itemId, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.inventory.stockItems(productId) })
    },
  })
}
