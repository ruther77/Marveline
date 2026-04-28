import { api, fetchBlob } from './fetchClient'
import type { PaginatedResponse } from '../types'
import type {
  DevisListItem,
  DevisDetail,
  DevisDetailFull,
  DevisCreate,
  DevisConvertPayload,
  DevisStatus,
  DevisVersion,
  DevisModule,
  DevisModuleCreate,
  DevisModuleUpdate,
  DevisPhase,
  DevisPhaseCreate,
  DevisPhaseUpdate,
  DevisChangeRequest,
  DevisCoverageItem,
  DevisCoverageItemCreate,
  DevisCoverageItemUpdate,
  DevisCoverageSummary,
} from '../types/devis'

export type DevisStatsMap = Record<string, number>

export const devisApi = {
  getStats: async (): Promise<DevisStatsMap> => {
    return api.get<DevisStatsMap>('/devis/stats')
  },

  listDevis: async (params?: {
    skip?: number
    limit?: number
    status?: DevisStatus
    customer_id?: number
    date_from?: string
    date_to?: string
    search?: string
  }): Promise<PaginatedResponse<DevisListItem>> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.status) p.status = params.status
    if (params?.customer_id) p.customer_id = String(params.customer_id)
    if (params?.date_from) p.date_from = params.date_from
    if (params?.date_to) p.date_to = params.date_to
    if (params?.search) p.search = params.search
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedResponse<DevisListItem>>(`/devis?${qs}`)
  },

  get: async (id: number): Promise<DevisDetailFull> => {
    return api.get<DevisDetailFull>(`/devis/${id}`)
  },

  create: async (payload: DevisCreate): Promise<DevisDetail> => {
    return api.post<DevisDetail>('/devis', payload)
  },

  update: async (id: number, payload: Partial<DevisCreate>): Promise<DevisDetail> => {
    return api.patch<DevisDetail>(`/devis/${id}`, payload)
  },

  send: async (id: number): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/send`)
  },

  accept: async (id: number): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/accept`)
  },

  startNegotiation: async (id: number): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/negotiation/start`)
  },

  markVersionPending: async (id: number): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/version-pending`)
  },

  concludeNegotiation: async (id: number, outcome: 'accepted' | 'refused', reason?: string): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/negotiation/conclude`, { outcome, reason })
  },

  refuse: async (id: number, reason?: string): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/refuse`, { reason })
  },

  cancel: async (id: number): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/cancel`)
  },

  duplicate: async (id: number): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/duplicate`)
  },

  expire: async (id: number): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/expire`)
  },

  renew: async (id: number): Promise<DevisDetail> => {
    return api.post<DevisDetail>(`/devis/${id}/renew`)
  },

  convertToReservation: async (id: number, payload: DevisConvertPayload): Promise<{ reservation_id: number }> => {
    return api.post<{ reservation_id: number }>(`/devis/${id}/convert`, payload)
  },

  getPdf: async (id: number): Promise<Blob> => {
    return fetchBlob(`/devis/${id}/pdf`)
  },

  addNegotiationEntry: async (
    id: number,
    payload: { message: string; proposed_amount_cents?: number }
  ): Promise<void> => {
    await api.post(`/devis/${id}/negotiation`, payload)
  },

  requestChange: async (id: number, description: string): Promise<void> => {
    await api.post(`/devis/${id}/change-request`, { description })
  },

  getVersions: async (id: number): Promise<DevisVersion[]> => {
    return api.get<DevisVersion[]>(`/devis/${id}/versions`)
  },

  listModules: async (devisId: number): Promise<DevisModule[]> => {
    return api.get<DevisModule[]>(`/devis/${devisId}/modules`)
  },

  listPhases: async (devisId: number): Promise<DevisPhase[]> => {
    return api.get<DevisPhase[]>(`/devis/${devisId}/phases`)
  },

  getCoverage: async (devisId: number): Promise<DevisCoverageSummary> => {
    return api.get<DevisCoverageSummary>(`/devis/${devisId}/coverage`)
  },

  uploadSignature: async (id: number, signatureData: string): Promise<{ id: number; signature_url: string; signed_at: string }> => {
    return api.post(`/devis/${id}/signature`, { signature_data: signatureData })
  },

  addModule: async (devisId: number, payload: DevisModuleCreate): Promise<DevisModule> => {
    return api.post<DevisModule>(`/devis/${devisId}/modules`, payload)
  },

  updateModule: async (devisId: number, moduleId: number, payload: DevisModuleUpdate): Promise<DevisModule> => {
    return api.patch<DevisModule>(`/devis/${devisId}/modules/${moduleId}`, payload)
  },

  deleteModule: async (devisId: number, moduleId: number): Promise<void> => {
    return api.delete(`/devis/${devisId}/modules/${moduleId}`)
  },

  addPhase: async (devisId: number, payload: DevisPhaseCreate): Promise<DevisPhase> => {
    return api.post<DevisPhase>(`/devis/${devisId}/phases`, payload)
  },

  updatePhase: async (devisId: number, phaseId: number, payload: DevisPhaseUpdate): Promise<DevisPhase> => {
    return api.patch<DevisPhase>(`/devis/${devisId}/phases/${phaseId}`, payload)
  },

  deletePhase: async (devisId: number, phaseId: number): Promise<void> => {
    return api.delete(`/devis/${devisId}/phases/${phaseId}`)
  },

  listChangeRequests: async (devisId: number): Promise<DevisChangeRequest[]> => {
    return api.get<DevisChangeRequest[]>(`/devis/${devisId}/change-requests`)
  },

  updateChangeRequest: async (devisId: number, crId: number, status: string): Promise<DevisChangeRequest> => {
    return api.patch<DevisChangeRequest>(`/devis/${devisId}/change-request/${crId}`, { status })
  },

  listCoverageItems: async (devisId: number): Promise<DevisCoverageItem[]> => {
    return api.get<DevisCoverageItem[]>(`/devis/${devisId}/coverage-items`)
  },

  addCoverageItem: async (devisId: number, payload: DevisCoverageItemCreate): Promise<DevisCoverageItem> => {
    return api.post<DevisCoverageItem>(`/devis/${devisId}/coverage-items`, payload)
  },

  updateCoverageItem: async (devisId: number, itemId: number, payload: DevisCoverageItemUpdate): Promise<DevisCoverageItem> => {
    return api.patch<DevisCoverageItem>(`/devis/${devisId}/coverage-items/${itemId}`, payload)
  },

  deleteCoverageItem: async (devisId: number, itemId: number): Promise<void> => {
    return api.delete(`/devis/${devisId}/coverage-items/${itemId}`)
  },

  // ── G31 — Bundle preview ─────────────────────────────────────────────────
  previewBundleItems: async (bundleId: number): Promise<import('../types/devis').BundlePreviewResponse> => {
    return api.get(`/devis/bundles/${bundleId}/items-preview`)
  },

  // ── G28 — Historique lignes ──────────────────────────────────────────────
  getLineHistory: async (devisId: number): Promise<import('../types/devis').DevisLineHistoryEntry[]> => {
    return api.get(`/devis/${devisId}/lines/history`)
  },

  // ── G7 — Pieces jointes ─────────────────────────────────────────────────
  listAttachments: async (devisId: number): Promise<import('../types/devis').DevisAttachment[]> => {
    return api.get(`/devis/${devisId}/attachments`)
  },

  uploadAttachment: async (devisId: number, file: File): Promise<import('../types/devis').DevisAttachment> => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/devis/${devisId}/attachments`, formData)
  },

  downloadAttachment: (devisId: number, attachmentId: number): string => {
    return `/api/v1/devis/${devisId}/attachments/${attachmentId}/download`
  },

  deleteAttachment: async (devisId: number, attachmentId: number): Promise<void> => {
    return api.delete(`/devis/${devisId}/attachments/${attachmentId}`)
  },
}
