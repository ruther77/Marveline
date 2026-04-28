import { api } from './fetchClient'
import type {
  ReservationDetail,
  ReservationDetailFull,
  ReservationCreate,
  ReservationUpdate,
  ReservationStatus,
  ReservationLine,
  ReservationLineCreate,
  PaginatedReservations,
  PreCheckItem,
  PreCheckItemCreate,
  ReservationRisk,
  ReservationRiskCreate,
  ReservationRiskUpdate,
  ReservationExtension,
  ExtendReservationRequest,
  ReservationAmendRequest,
  ReturnInspectionBulkCreate,
  ReturnInspectionItem,
  DisputeLog,
  DisputeLogCreate,
} from '../types/reservation'
import type { Deposit, DepositCreate, DepositUpdate } from '../types/deposit'

export type ReservationStatsMap = Record<string, number>

export const reservationsApi = {
  getStats: async (): Promise<ReservationStatsMap> => {
    return api.get<ReservationStatsMap>('/reservations/stats')
  },

  listReservations: async (params?: {
    skip?: number
    limit?: number
    status?: ReservationStatus
    start_date?: string
    end_date?: string
    customer_id?: number
    assigned_to_me?: boolean
  }): Promise<PaginatedReservations> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.status) p.status_filter = params.status
    if (params?.start_date) p.start_date = params.start_date
    if (params?.end_date) p.end_date = params.end_date
    if (params?.customer_id) p.customer_id = String(params.customer_id)
    if (params?.assigned_to_me) p.assigned_to_me = 'true'
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedReservations>(`/reservations?${qs}`)
  },

  getReservation: async (id: number): Promise<ReservationDetail> => {
    return api.get<ReservationDetail>(`/reservations/${id}`)
  },

  getReservationFull: async (id: number): Promise<ReservationDetailFull> => {
    return api.get<ReservationDetailFull>(`/reservations/${id}/full`)
  },

  createReservation: async (reservation: ReservationCreate): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>('/reservations', reservation)
  },

  updateReservation: async (id: number, reservation: ReservationUpdate): Promise<ReservationDetail> => {
    return api.patch<ReservationDetail>(`/reservations/${id}`, reservation)
  },

  confirmReservation: async (id: number): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>(`/reservations/${id}/confirm`)
  },

  cancelReservation: async (id: number): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>(`/reservations/${id}/cancel`)
  },

  amendReservation: async (
    id: number,
    payload: ReservationAmendRequest,
  ): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>(`/reservations/${id}/amend`, payload)
  },

  deliverReservation: async (id: number): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>(`/reservations/${id}/deliver`)
  },

  listDeposits: async (reservationId: number): Promise<Deposit[]> => {
    const data = await api.get<Deposit[] | Deposit>(`/reservations/${reservationId}/deposits`)
    return Array.isArray(data) ? data : []
  },

  createDeposit: async (reservationId: number, deposit: DepositCreate): Promise<Deposit> => {
    return api.post<Deposit>(`/reservations/${reservationId}/deposits`, deposit)
  },

  updateDeposit: async (reservationId: number, depositId: number, deposit: DepositUpdate): Promise<Deposit> => {
    return api.patch<Deposit>(`/reservations/${reservationId}/deposits/${depositId}`, deposit)
  },

  uploadSignature: async (reservationId: number, signatureData: string): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>(`/reservations/${reservationId}/signature`, { signature_data: signatureData })
  },

  // Pre-check
  listPreCheck: async (reservationId: number): Promise<PreCheckItem[]> => {
    const data = await api.get<PreCheckItem[] | PreCheckItem>(`/reservations/${reservationId}/pre-check`)
    return Array.isArray(data) ? data : []
  },

  createPreCheckItem: async (reservationId: number, item: PreCheckItemCreate): Promise<PreCheckItem> => {
    return api.post<PreCheckItem>(`/reservations/${reservationId}/pre-check`, item)
  },

  updatePreCheckItem: async (reservationId: number, itemId: number, data: { checked: boolean }): Promise<PreCheckItem> => {
    return api.patch<PreCheckItem>(`/reservations/${reservationId}/pre-check/${itemId}`, data)
  },

  completePreCheck: async (reservationId: number): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>(`/reservations/${reservationId}/pre-check/complete`)
  },

  // Extension
  extendReservation: async (reservationId: number, data: ExtendReservationRequest): Promise<ReservationExtension> => {
    return api.post<ReservationExtension>(`/reservations/${reservationId}/extend`, data)
  },

  // Risques
  listRisks: async (reservationId: number): Promise<ReservationRisk[]> => {
    const data = await api.get<ReservationRisk[] | ReservationRisk>(`/reservations/${reservationId}/risks`)
    return Array.isArray(data) ? data : []
  },

  createRisk: async (reservationId: number, risk: ReservationRiskCreate): Promise<ReservationRisk> => {
    return api.post<ReservationRisk>(`/reservations/${reservationId}/risks`, risk)
  },

  updateRisk: async (reservationId: number, riskId: number, data: ReservationRiskUpdate): Promise<ReservationRisk> => {
    return api.patch<ReservationRisk>(`/reservations/${reservationId}/risks/${riskId}`, data)
  },

  deleteRisk: async (reservationId: number, riskId: number): Promise<void> => {
    return api.delete(`/reservations/${reservationId}/risks/${riskId}`)
  },

  // Lignes
  addLine: async (reservationId: number, data: ReservationLineCreate): Promise<ReservationLine> => {
    return api.post<ReservationLine>(`/reservations/${reservationId}/lines`, data)
  },

  removeLine: async (reservationId: number, lineId: number): Promise<void> => {
    return api.delete(`/reservations/${reservationId}/lines/${lineId}`)
  },

  closeDispute: async (id: number, resolutionNotes: string): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>(`/reservations/${id}/close-dispute`, {
      resolution_notes: resolutionNotes,
    })
  },

  assignUser: async (id: number, userId: number | null): Promise<ReservationDetail> => {
    return api.patch<ReservationDetail>(`/reservations/${id}/assign`, { user_id: userId })
  },

  completeReservation: async (id: number): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>(`/reservations/${id}/complete`)
  },

  remindDeposit: async (id: number): Promise<void> => {
    return api.post(`/reservations/${id}/remind-deposit`)
  },

  deleteReservation: async (id: number): Promise<void> => {
    return api.delete(`/reservations/${id}`)
  },

  archiveReservation: async (id: number): Promise<ReservationDetail> => {
    return api.post<ReservationDetail>(`/reservations/${id}/archive`)
  },

  // Return inspection
  listInspection: async (reservationId: number): Promise<ReturnInspectionItem[]> => {
    const data = await api.get<ReturnInspectionItem[] | ReturnInspectionItem>(
      `/reservations/${reservationId}/inspection`,
    )
    return Array.isArray(data) ? data : []
  },

  createInspection: async (
    reservationId: number,
    payload: ReturnInspectionBulkCreate,
  ): Promise<ReturnInspectionItem[]> => {
    return api.post<ReturnInspectionItem[]>(
      `/reservations/${reservationId}/inspection`,
      payload,
    )
  },

  // Dispute logs
  listDisputeLogs: async (reservationId: number): Promise<DisputeLog[]> => {
    const data = await api.get<DisputeLog[] | DisputeLog>(
      `/reservations/${reservationId}/dispute-logs`,
    )
    return Array.isArray(data) ? data : []
  },

  addDisputeLog: async (
    reservationId: number,
    payload: DisputeLogCreate,
  ): Promise<DisputeLog> => {
    return api.post<DisputeLog>(`/reservations/${reservationId}/dispute-logs`, payload)
  },
}
