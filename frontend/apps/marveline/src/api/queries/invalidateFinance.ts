import type { QueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'

/**
 * Invalide toutes les queries du domaine finance :
 * invoices, deposits (global), treasury, dashboard finances.
 *
 * A appeler dans onSettled de toute mutation qui modifie
 * factures, paiements, cautions ou reservations.
 */
export function invalidateFinance(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.invoices.all })
  qc.invalidateQueries({ queryKey: queryKeys.deposits.all })
  qc.invalidateQueries({ queryKey: queryKeys.treasury.all })
  qc.invalidateQueries({ queryKey: queryKeys.dashboard.all })
}
