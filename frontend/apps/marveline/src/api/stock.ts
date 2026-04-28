import { api } from './fetchClient'
import type {
  CountingEntry,
  InventaireSessionResponse,
  StockAdjustmentCreate,
  StockAdjustmentResponse,
  StockLevelItem,
  ReorderItem,
  ReorderRequest,
  ReorderResponse,
  StockCoverageResponse,
} from '@/types/stock_management'
import type { PaginatedResponse } from '@/types/index'

export const stockApi = {
  // ── Inventaire physique ─────────────────────────────────────────────────
  getActiveInventaire(): Promise<InventaireSessionResponse> {
    return api.get<InventaireSessionResponse>('/stock/inventaire/active')
  },

  startInventaire(): Promise<InventaireSessionResponse> {
    return api.post<InventaireSessionResponse>('/stock/inventaire')
  },

  getInventaire(sessionId: number): Promise<InventaireSessionResponse> {
    return api.get<InventaireSessionResponse>(`/stock/inventaire/${sessionId}`)
  },

  updateInventaire(sessionId: number, entries: CountingEntry[]): Promise<InventaireSessionResponse> {
    return api.patch<InventaireSessionResponse>(`/stock/inventaire/${sessionId}`, { entries })
  },

  completeInventaire(sessionId: number): Promise<InventaireSessionResponse> {
    return api.post<InventaireSessionResponse>(`/stock/inventaire/${sessionId}/complete`)
  },

  // ── Ajustements manuels ─────────────────────────────────────────────────
  listAdjustments(productId?: number): Promise<PaginatedResponse<StockAdjustmentResponse>> {
    const qs = productId !== undefined ? `?product_id=${productId}` : ''
    return api.get<PaginatedResponse<StockAdjustmentResponse>>(`/stock/adjustments${qs}`)
  },

  createAdjustment(data: StockAdjustmentCreate): Promise<StockAdjustmentResponse> {
    return api.post<StockAdjustmentResponse>('/stock/adjustments', data)
  },

  // ── Niveaux de stock ────────────────────────────────────────────────────
  getLevels(): Promise<PaginatedResponse<StockLevelItem>> {
    return api.get<PaginatedResponse<StockLevelItem>>('/stock/levels')
  },

  // ── Réassort ────────────────────────────────────────────────────────────
  getReorderList(): Promise<PaginatedResponse<ReorderItem>> {
    return api.get<PaginatedResponse<ReorderItem>>('/stock/reorder')
  },

  createReorder(data: ReorderRequest): Promise<ReorderResponse> {
    return api.post<ReorderResponse>('/stock/reorder', data)
  },

  // ── Couverture stock ────────────────────────────────────────────────────
  getCoverage(): Promise<StockCoverageResponse> {
    return api.get<StockCoverageResponse>('/stock/coverage')
  },
}
