import { api } from './fetchClient'
import type {
  DepartureState,
  ReturnState,
  DamageReportResponse,
  DepartureBlockPayload,
  ReturnDamagePayload,
  QrResult,
  PhotoUploadResponse,
} from '../types/operations'

function assertReservationId(id: number): void {
  if (!Number.isInteger(id) || id <= 0) {
    throw new Error(`Identifiant de reservation invalide: ${id}`)
  }
}

export const operationsApi = {
  // ── Départ ──────────────────────────────────────────────────────────────────

  getDepartureState: async (reservationId: number): Promise<DepartureState> => {
    assertReservationId(reservationId)
    return api.get<DepartureState>(`/operations/departure/${reservationId}`)
  },

  validateDeparture: async (reservationId: number, items?: unknown[], signatureUrl?: string): Promise<DepartureState> => {
    assertReservationId(reservationId)
    return api.post<DepartureState>(`/operations/departure/${reservationId}`, {
      signature_url: signatureUrl ?? null,
      items: items ?? [],
    })
  },

  blockDeparture: async (reservationId: number, payload: DepartureBlockPayload): Promise<DepartureState> => {
    assertReservationId(reservationId)
    return api.post<DepartureState>(`/operations/departure/${reservationId}/block`, payload)
  },

  // ── Retour ───────────────────────────────────────────────────────────────────

  getReturnState: async (reservationId: number): Promise<ReturnState> => {
    assertReservationId(reservationId)
    return api.get<ReturnState>(`/operations/return/${reservationId}`)
  },

  validateReturn: async (reservationId: number, items?: unknown[], signatureUrl?: string): Promise<ReturnState> => {
    assertReservationId(reservationId)
    return api.post<ReturnState>(`/operations/return/${reservationId}`, {
      signature_url: signatureUrl ?? null,
      items: items ?? [],
    })
  },

  declareDamage: async (reservationId: number, payload: ReturnDamagePayload): Promise<DamageReportResponse> => {
    assertReservationId(reservationId)
    return api.post<DamageReportResponse>(`/operations/return/${reservationId}/damage`, payload)
  },

  // ── QR ───────────────────────────────────────────────────────────────────────

  resolveQr: async (code: string): Promise<QrResult> => {
    return api.get<QrResult>(`/operations/qr/${encodeURIComponent(code)}`)
  },

  // ── Photos ───────────────────────────────────────────────────────────────────

  uploadDamagePhoto: async (file: File): Promise<PhotoUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<PhotoUploadResponse>(`/operations/damage/photo`, formData)
  },

  // ── Dashboard opérationnel ──────────────────────────────────────────────────

  getSummary: async (): Promise<OperationsSummary> => {
    return api.get<OperationsSummary>('/operations/summary')
  },
}

export interface OperationsSummaryItem {
  id: number
  reference: string
  status: string
  customer_name: string | null
  delivery_date: string | null
  return_date: string | null
  event_date: string | null
}

export interface OperationsSummary {
  departures: OperationsSummaryItem[]
  returns_pending: OperationsSummaryItem[]
  returns_overdue: OperationsSummaryItem[]
}
