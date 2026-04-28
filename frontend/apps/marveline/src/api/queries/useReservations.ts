import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { invalidateFinance } from './invalidateFinance'
import { reservationsApi } from '../reservations'
import type { ReservationStatsMap } from '../reservations'
import type {
  ReservationCreate,
  ReservationUpdate,
  ReservationLineCreate,
  ReservationList,
  PaginatedReservations,
  PreCheckItem,
  PreCheckItemCreate,
  ReservationRiskCreate,
  ReservationRiskUpdate,
  ExtendReservationRequest,
} from '@/types/reservation'
import type { DepositCreate, DepositUpdate } from '@/types/deposit'

export function useReservationsStats() {
  return useQuery<ReservationStatsMap>({
    queryKey: queryKeys.reservations.stats(),
    queryFn: () => reservationsApi.getStats(),
    staleTime: 60 * 1000,
  })
}

export function useReservationsList(params?: Parameters<typeof reservationsApi.listReservations>[0]) {
  return useQuery({
    queryKey: queryKeys.reservations.list(params ?? {}),
    queryFn: () => reservationsApi.listReservations(params),
  })
}

export function useReservationDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.reservations.detail(id!),
    queryFn: () => reservationsApi.getReservation(id!),
    enabled: id !== null,
  })
}

export function useReservationFull(id: number | null) {
  return useQuery({
    queryKey: queryKeys.reservations.full(id!),
    queryFn: () => reservationsApi.getReservationFull(id!),
    enabled: id !== null,
  })
}

export function useReservationDeposits(resaId: number | null) {
  return useQuery({
    queryKey: queryKeys.reservations.deposits(resaId!),
    queryFn: () => reservationsApi.listDeposits(resaId!),
    enabled: resaId !== null,
    staleTime: 3 * 60 * 1000,
  })
}

export function useCreateReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ReservationCreate) => reservationsApi.createReservation(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      qc.invalidateQueries({ queryKey: ['planning'] })
    },
  })
}

export function useUpdateReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ReservationUpdate }) =>
      reservationsApi.updateReservation(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      qc.invalidateQueries({ queryKey: ['planning'] })
    },
  })
}

export function useConfirmReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => reservationsApi.confirmReservation(id),

    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: queryKeys.reservations.lists() })
      const previousLists = qc.getQueriesData<PaginatedReservations>({
        queryKey: queryKeys.reservations.lists(),
      })
      qc.setQueriesData<PaginatedReservations>(
        { queryKey: queryKeys.reservations.lists() },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.map((r: ReservationList) =>
              r.id === id ? { ...r, status: 'confirmed' as const } : r
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

    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      // Confirmation génère une facture côté backend
      invalidateFinance(qc)
    },
  })
}

export function useCancelReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => reservationsApi.cancelReservation(id),

    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: queryKeys.reservations.lists() })
      const previousLists = qc.getQueriesData<PaginatedReservations>({
        queryKey: queryKeys.reservations.lists(),
      })
      qc.setQueriesData<PaginatedReservations>(
        { queryKey: queryKeys.reservations.lists() },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.map((r: ReservationList) =>
              r.id === id ? { ...r, status: 'cancelled' as const } : r
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

    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.lists() })
      // Invalider toutes les queries finance (factures + devis)
      invalidateFinance(qc)
      qc.invalidateQueries({ queryKey: queryKeys.devis.all })
    },
  })
}

export function useAmendReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { id: number; payload: import('../../types/reservation').ReservationAmendRequest }) =>
      reservationsApi.amendReservation(params.id, params.payload),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.detail(vars.id) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.lists() })
      qc.invalidateQueries({ queryKey: queryKeys.devis.all })
      invalidateFinance(qc)
    },
  })
}

export function useDeliverReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => reservationsApi.deliverReservation(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      qc.invalidateQueries({ queryKey: queryKeys.inventory.movements.lists() })
      invalidateFinance(qc)
    },
  })
}

export function useCreateDeposit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, data }: { reservationId: number; data: DepositCreate }) =>
      reservationsApi.createDeposit(reservationId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      invalidateFinance(qc)
    },
  })
}

export function useUpdateDeposit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, depositId, data }: { reservationId: number; depositId: number; data: DepositUpdate }) =>
      reservationsApi.updateDeposit(reservationId, depositId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      invalidateFinance(qc)
    },
  })
}

// ── Pre-check ──────────────────────────────────────────────────────────────

export function usePreCheckItems(reservationId: number | null) {
  return useQuery({
    queryKey: queryKeys.reservations.preCheck(reservationId!),
    queryFn: () => reservationsApi.listPreCheck(reservationId!),
    enabled: reservationId !== null,
  })
}

export function useCreatePreCheckItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, data }: { reservationId: number; data: PreCheckItemCreate }) =>
      reservationsApi.createPreCheckItem(reservationId, data),
    onSuccess: (_r, { reservationId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.preCheck(reservationId) })
    },
  })
}

export function useUpdatePreCheckItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, itemId, checked }: { reservationId: number; itemId: number; checked: boolean }) =>
      reservationsApi.updatePreCheckItem(reservationId, itemId, { checked }),

    onMutate: async ({ reservationId, itemId, checked }) => {
      const key = queryKeys.reservations.preCheck(reservationId)
      await qc.cancelQueries({ queryKey: key })
      const previous = qc.getQueryData<PreCheckItem[]>(key)
      qc.setQueryData<PreCheckItem[]>(key, (old) =>
        old?.map((item) => item.id === itemId ? { ...item, checked } : item),
      )
      return { previous, key }
    },

    onError: (_err, _vars, context) => {
      if (context?.previous) {
        qc.setQueryData(context.key, context.previous)
      }
    },

    onSettled: (_r, _e, { reservationId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.preCheck(reservationId) })
    },
  })
}

export function useCompletePreCheck() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reservationId: number) => reservationsApi.completePreCheck(reservationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })
}

// ── Extension ─────────────────────────────────────────────────────────────

export function useExtendReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, data }: { reservationId: number; data: ExtendReservationRequest }) =>
      reservationsApi.extendReservation(reservationId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      // Extension peut impacter la facturation (durée, montant)
      invalidateFinance(qc)
    },
  })
}

// ── Risques ───────────────────────────────────────────────────────────────

export function useReservationRisks(reservationId: number | null) {
  return useQuery({
    queryKey: queryKeys.reservations.risks(reservationId!),
    queryFn: () => reservationsApi.listRisks(reservationId!),
    enabled: reservationId !== null,
  })
}

export function useCreateRisk() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, data }: { reservationId: number; data: ReservationRiskCreate }) =>
      reservationsApi.createRisk(reservationId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })
}

export function useUpdateRisk() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, riskId, data }: { reservationId: number; riskId: number; data: ReservationRiskUpdate }) =>
      reservationsApi.updateRisk(reservationId, riskId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })
}

export function useDeleteRisk() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, riskId }: { reservationId: number; riskId: number }) =>
      reservationsApi.deleteRisk(reservationId, riskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })
}


export function useAddReservationLine() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, data }: { reservationId: number; data: ReservationLineCreate }) =>
      reservationsApi.addLine(reservationId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      qc.invalidateQueries({ queryKey: ['planning'] })
    },
  })
}

export function useRemoveReservationLine() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, lineId }: { reservationId: number; lineId: number }) =>
      reservationsApi.removeLine(reservationId, lineId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      qc.invalidateQueries({ queryKey: ['planning'] })
    },
  })
}

export function useUploadReservationSignature() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, signatureData }: { reservationId: number; signatureData: string }) =>
      reservationsApi.uploadSignature(reservationId, signatureData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })
}

export function useCloseReservationDispute() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, resolutionNotes }: { reservationId: number; resolutionNotes: string }) =>
      reservationsApi.closeDispute(reservationId, resolutionNotes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      // Fermeture litige peut déclencher facturation dommages
      invalidateFinance(qc)
    },
  })
}

export function useAssignReservationUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reservationId, userId }: { reservationId: number; userId: number | null }) =>
      reservationsApi.assignUser(reservationId, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      qc.invalidateQueries({ queryKey: ['planning'] })
    },
  })
}

export function useCompleteReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reservationId: number) => reservationsApi.completeReservation(reservationId),
    onSuccess: (_r, reservationId) => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      qc.invalidateQueries({ queryKey: ['audit', 'Reservation', reservationId] })
      invalidateFinance(qc)
      qc.invalidateQueries({ queryKey: queryKeys.devis.all })
    },
  })
}

export function useRemindReservationDeposit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reservationId: number) => reservationsApi.remindDeposit(reservationId),
    onSuccess: (_r, reservationId) => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      qc.invalidateQueries({ queryKey: ['audit', 'Reservation', reservationId] })
    },
  })
}

export function useDeleteReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reservationId: number) => reservationsApi.deleteReservation(reservationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
      invalidateFinance(qc)
      qc.invalidateQueries({ queryKey: queryKeys.devis.all })
      qc.invalidateQueries({ queryKey: ['planning'] })
    },
  })
}

export function useArchiveReservation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reservationId: number) => reservationsApi.archiveReservation(reservationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.reservations.all })
    },
  })
}

// Alias legacy pour compatibilité avec d'anciens imports.
export const useRemindDeposit = useRemindReservationDeposit

// ── Return inspection ──────────────────────────────────────────────────────

export function useInspection(reservationId: number | null) {
  return useQuery({
    queryKey: queryKeys.reservations.inspection(reservationId!),
    queryFn: () => reservationsApi.listInspection(reservationId!),
    enabled: reservationId !== null,
  })
}

export function useCreateInspection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      reservationId: number
      payload: import('../../types/reservation').ReturnInspectionBulkCreate
    }) => reservationsApi.createInspection(params.reservationId, params.payload),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({
        queryKey: queryKeys.reservations.inspection(vars.reservationId),
      })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.detail(vars.reservationId) })
      qc.invalidateQueries({ queryKey: queryKeys.reservations.full(vars.reservationId) })
      qc.invalidateQueries({
        queryKey: queryKeys.reservations.disputeLogs(vars.reservationId),
      })
    },
  })
}

// ── Dispute logs ───────────────────────────────────────────────────────────

export function useDisputeLogs(reservationId: number | null) {
  return useQuery({
    queryKey: queryKeys.reservations.disputeLogs(reservationId!),
    queryFn: () => reservationsApi.listDisputeLogs(reservationId!),
    enabled: reservationId !== null,
  })
}

export function useAddDisputeLog() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      reservationId: number
      payload: import('../../types/reservation').DisputeLogCreate
    }) => reservationsApi.addDisputeLog(params.reservationId, params.payload),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({
        queryKey: queryKeys.reservations.disputeLogs(vars.reservationId),
      })
    },
  })
}
