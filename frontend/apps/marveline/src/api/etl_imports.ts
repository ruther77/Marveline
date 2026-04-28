// API ETL Imports — Queue factures fournisseur (ADR-25)

import { api } from '@/api/fetchClient'
import type {
  EtlImportListResponse,
  EtlImportRead,
  EtlImportUpdateRequest,
  FactureUploadResponse,
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

  const resp = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/v1/admin/etl/upload`, {
    method: 'POST',
    body: formData,
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
  return api.get(`/admin/etl/imports?statut=${statut}&limit=${limit}&offset=${offset}`)
}

export async function getImportDetail(id: number): Promise<EtlImportRead> {
  return api.get(`/admin/etl/imports/${id}`)
}

export async function updateImportPreview(
  id: number,
  data: EtlImportUpdateRequest,
): Promise<EtlImportRead> {
  return api.patch(`/admin/etl/imports/${id}`, data)
}

export async function validateImport(id: number): Promise<EtlImportRead> {
  return api.post(`/admin/etl/imports/${id}/validate`)
}

export async function rejectImport(id: number): Promise<EtlImportRead> {
  return api.post(`/admin/etl/imports/${id}/reject`)
}
