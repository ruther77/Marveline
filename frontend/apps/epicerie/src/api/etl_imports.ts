// API ETL Imports — Queue factures fournisseur (ADR-25)

import { massacorpApi } from '@/api'
import type {
  CategoriesResponse,
  EtlImportDetail,
  EtlImportListResponse,
  EtlImportRead,
  EtlImportUpdateRequest,
  FactureUploadResponse,
  LigneAddRequest,
  LignesBatchUpdateRequest,
  ValidatedLignesBatchEditRequest,
  ValidatedInvoiceMetaEditRequest,
  ValidatedLignesEditResponse,
} from '@/types/etl_import'

export async function uploadFacture(
  file: File,
  fournisseur: string = 'metro',
  fournisseurId?: number,
): Promise<FactureUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('fournisseur', fournisseur)
  if (fournisseurId !== undefined) {
    formData.append('fournisseur_id', String(fournisseurId))
  }

  // FormData ne doit pas être JSON.stringify — on utilise le niveau bas
  const { getMassaCorpApi } = await import('@shared/stores/massacorpAuthStore')
  const api = getMassaCorpApi()
  const headers = api.buildHeaders({ method: 'POST', isFormData: true })
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'

  const resp = await fetch(`${apiUrl}/admin/etl/upload`, {
    method: 'POST',
    body: formData,
    headers,
    credentials: 'include',
  })

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error(body.detail || `Upload failed: ${resp.status}`)
  }

  return resp.json()
}

export async function listImports(
  statut: string = 'all',
  limit: number = 50,
  offset: number = 0,
): Promise<EtlImportListResponse> {
  return massacorpApi.get(`/admin/etl/imports?statut=${statut}&limit=${limit}&offset=${offset}`)
}

export async function getImportDetail(id: number): Promise<EtlImportDetail> {
  return massacorpApi.get(`/admin/etl/imports/${id}`)
}

export async function updateImportPreview(
  id: number,
  data: EtlImportUpdateRequest,
): Promise<EtlImportRead> {
  return massacorpApi.patch(`/admin/etl/imports/${id}`, data)
}

export async function validateImport(id: number): Promise<EtlImportRead> {
  return massacorpApi.post(`/admin/etl/imports/${id}/validate`)
}

export async function rejectImport(id: number): Promise<EtlImportRead> {
  return massacorpApi.post(`/admin/etl/imports/${id}/reject`)
}

export async function revertImport(id: number): Promise<{ mouvements_annules: number; invoice_annulee: boolean; prix_restaures: number }> {
  return massacorpApi.post(`/admin/etl/imports/${id}/revert`)
}

// ── Lignes CRUD ──────────────────────────────────────────────────────────────

export async function updateLignes(
  importId: number,
  payload: LignesBatchUpdateRequest,
): Promise<EtlImportDetail> {
  return massacorpApi.patch(`/admin/etl/imports/${importId}/lignes`, payload)
}

export async function addLigne(
  importId: number,
  payload: LigneAddRequest,
): Promise<EtlImportDetail> {
  return massacorpApi.post(`/admin/etl/imports/${importId}/lignes`, payload)
}

export async function deleteLigne(
  importId: number,
  idx: number,
): Promise<EtlImportDetail> {
  return massacorpApi.delete(`/admin/etl/imports/${importId}/lignes/${idx}`)
}

// ── Édition post-validation (Option B — P1/P2) ──────────────────────────────

export async function editValidatedLignes(
  importId: number,
  payload: ValidatedLignesBatchEditRequest,
  ifMatch: string,
): Promise<ValidatedLignesEditResponse> {
  return massacorpApi.patch(
    `/admin/etl/imports/${importId}/validated-lignes`,
    payload,
    { headers: { 'If-Match': ifMatch } },
  )
}

export async function editValidatedInvoiceMeta(
  importId: number,
  payload: ValidatedInvoiceMetaEditRequest,
  ifMatch: string,
): Promise<EtlImportRead> {
  return massacorpApi.patch(
    `/admin/etl/imports/${importId}/invoice-meta`,
    payload,
    { headers: { 'If-Match': ifMatch } },
  )
}

// ── Reopen (P7 — sortir du cul-de-sac REJECTED/REVERTED) ──────────────────

export async function reopenImport(
  importId: number,
): Promise<EtlImportRead> {
  return massacorpApi.post(`/admin/etl/imports/${importId}/reopen`)
}

// ── Reclassification KNN ─────────────────────────────────────────────────────

export async function reclassifyImport(importId: number): Promise<EtlImportDetail> {
  return massacorpApi.post(`/admin/etl/imports/${importId}/reclassify`)
}

// ── PDF ──────────────────────────────────────────────────────────────────────

export function getPdfUrl(fichierPath: string | null): string | null {
  if (!fichierPath) return null
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
  // Static files served at /uploads/ — no auth needed for iframe
  const baseUrl = apiUrl.replace('/api/v1', '')
  return `${baseUrl}/uploads/${fichierPath}`
}

// ── Images ───────────────────────────────────────────────────────────────────

export async function fetchImages(): Promise<{ fetched: number; total: number }> {
  return massacorpApi.post('/admin/etl/fetch-images')
}

// ── Categories ───────────────────────────────────────────────────────────────

export async function getCategories(): Promise<CategoriesResponse> {
  return massacorpApi.get('/admin/etl/categories')
}

// ── Suggestions intelligentes (Phase 2) ─────────────────────────────────────

export interface CategorySuggestion {
  code: string
  label: string
  score: number
}

export interface BrandSuggestion {
  name: string
  categories: string[]
  usage_count: number
}

export interface ProductSuggestion {
  candidate_id: number
  designation_norm: string
  designation?: string
  ean?: string | null
  categorie_code?: string | null
  prix_unitaire_cts?: number | null
  score: number
}

export async function suggestCategory(designation: string, limit = 5): Promise<{ suggestions: CategorySuggestion[] }> {
  return massacorpApi.get(`/admin/etl/suggest/category?designation=${encodeURIComponent(designation)}&limit=${limit}`)
}

export async function suggestBrand(q: string, limit = 10): Promise<{ suggestions: BrandSuggestion[] }> {
  return massacorpApi.get(`/admin/etl/suggest/brand?q=${encodeURIComponent(q)}&limit=${limit}`)
}

export async function suggestProduct(designation: string, limit = 5): Promise<{ suggestions: ProductSuggestion[] }> {
  return massacorpApi.get(`/admin/etl/suggest/product?designation=${encodeURIComponent(designation)}&limit=${limit}`)
}

// ── Dashboard (Phase 3) ─────────────────────────────────────────────────────

export interface DashboardQualityTrend {
  id: number
  date: string | null
  quality_score: number | null
  vendor_code: string | null
  nb_lignes_total: number | null
}

export interface DashboardVendorStats {
  vendor_code: string
  total_imports: number
  avg_quality: number | null
  recognition_rate: number | null
}

export interface DashboardData {
  total_imports: number
  by_status: Record<string, number>
  avg_quality_global: number | null
  quality_trend: DashboardQualityTrend[]
  vendor_stats: DashboardVendorStats[]
  pending_conflicts: number
  avg_correction_time_sec: number | null
}

export async function getDashboard(): Promise<DashboardData> {
  return massacorpApi.get('/admin/etl/dashboard')
}

// ── Quality metrics par fournisseur ───────────────────────────────────────

export interface QualityMetricsVendor {
  vendor_code: string
  nb_imports: number
  nb_lignes: number
  avg_quality: number | null
  pct_ean: number
  pct_marque: number
  pct_categorie: number
  pct_conditionnement: number
  pct_volume: number
  pct_prix: number
  pct_tva: number
  pct_confidence_ok: number
}

export interface QualityMetricsData {
  days: number
  vendors: QualityMetricsVendor[]
}

export async function getQualityMetrics(days = 90): Promise<QualityMetricsData> {
  return massacorpApi.get(`/admin/etl/quality-metrics?days=${days}`)
}
