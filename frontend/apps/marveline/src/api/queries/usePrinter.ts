import { useMutation } from '@tanstack/react-query'
import { printerApi, type PrintTicketRequest, type PrintTicketResponse } from '../printer'

/**
 * usePrintTicket — Envoie un ticket vers l'imprimante ESC/POS du tenant.
 *
 * L'impression est asynchrone (Celery) — retourne 202 immédiatement.
 * Pas d'invalidation cache nécessaire.
 */
export function usePrintTicket() {
  return useMutation<PrintTicketResponse, Error, PrintTicketRequest>({
    mutationFn: (data) => printerApi.printTicket(data),
  })
}
