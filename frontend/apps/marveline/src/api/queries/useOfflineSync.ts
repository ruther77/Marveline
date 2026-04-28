import { useMutation, useQueryClient } from '@tanstack/react-query'
import { offlineApi, type OfflineMutation, type OfflineSyncResponse } from '../offline'
import { queryKeys } from './keys'

/**
 * useOfflineSync — Replay offline mutations quand le réseau revient.
 *
 * Le SW stocke les mutations dans IndexedDB quand offline.
 * Au retour réseau, on appelle sync() avec le batch FIFO.
 * Le backend replay chaque mutation, idempotency via UUID.
 *
 * Après sync réussi, on invalide tous les caches impactés.
 */
export function useOfflineSync() {
  const qc = useQueryClient()

  return useMutation<OfflineSyncResponse, Error, OfflineMutation[]>({
    mutationFn: (mutations) => offlineApi.sync(mutations),
    onSuccess: (data) => {
      if (data.succeeded > 0) {
        qc.invalidateQueries({ queryKey: queryKeys.inventory.all })
        qc.invalidateQueries({ queryKey: queryKeys.stock.all })
        qc.invalidateQueries({ queryKey: queryKeys.invoices.all })
        qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
        qc.invalidateQueries({ queryKey: queryKeys.ventes.all })
        qc.invalidateQueries({ queryKey: queryKeys.orders.all })
      }
    },
  })
}
