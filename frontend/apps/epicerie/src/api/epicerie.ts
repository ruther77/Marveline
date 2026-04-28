// FC_EPICERIE_POS.md, FC_EPICERIE_INVENTAIRE.md, FC_EPICERIE_FOURNISSEURS.md
// Client API épicerie — suit le même pattern que stockApi / productsApi

import { massacorpApi } from '@/api'
import type {
  EpicerieProduitRead,
  EpicerieStockRead,
  EpicerieStockSummary,
  EpicerieStockMovementRead,
  EncaissementRequest,
  EncaissementResponse,
  AjustementCreate,
  AjustementResponse,
  SeuilAlerteUpdate,
  ComptageRequest,
  ComptageResponse,
  FournisseurRead,
  FournisseurStats,
  FinanceInvoiceRead,
  SupplyOrderRead,
  SupplyOrderCreate,
  ProduitCatalogueRead,
  InternalTransferCreate,
  InternalTransferRead,
  InternalTransferListResponse,
  TransferRequestRead,
  TransferRequestListResponse,
  PreviewResolutionResponse,
  ApproveWithTransferBody,
  ApproveWithTransferResult,
  CaHistoriqueResponse,
  StockMargesResponse,
  AlertesPrixResponse,
  QualiteResponse,
  EpicerieEanRead,
  EpicerieProduitEansResponse,
  PrixHistoriqueItem,
} from '@/types/epicerie-v2'

// ─── Produits ─────────────────────────────────────────────────────────────

export interface EpicerieProduitsParams {
  search?: string
  categorie?: string
  actif_only?: boolean
  limit?: number
  offset?: number
}

function buildQs(params: Record<string, string | number | boolean | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  if (!entries.length) return ''
  return '?' + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
}

export const epicerieApi = {
  // ── Produits ──────────────────────────────────────────────────────────

  listProduits(params?: EpicerieProduitsParams): Promise<EpicerieProduitRead[]> {
    return massacorpApi.get(`/epicerie/produits${buildQs({ ...params })}`)
  },

  getProduitByEan(ean: string): Promise<EpicerieProduitRead> {
    return massacorpApi.get(`/epicerie/produits/ean/${encodeURIComponent(ean)}`)
  },

  getProduitEans(produitId: number): Promise<EpicerieProduitEansResponse> {
    return massacorpApi.get(`/epicerie/produits/${produitId}/eans`)
  },

  addProduitEan(
    produitId: number,
    ean: string,
    sourceFournisseur?: string,
  ): Promise<EpicerieEanRead> {
    return massacorpApi.post(`/epicerie/produits/${produitId}/eans`, {
      ean,
      source_fournisseur: sourceFournisseur ?? null,
    })
  },

  getPrixHistorique(produitId: number): Promise<PrixHistoriqueItem[]> {
    return massacorpApi.get(`/epicerie/stock/${produitId}/prix-historique`)
  },

  async uploadProduitImage(produitId: number, file: File): Promise<EpicerieProduitRead> {
    const formData = new FormData()
    formData.append('file', file)
    const { getMassaCorpApi } = await import('@shared/stores/massacorpAuthStore')
    const api = getMassaCorpApi()
    const headers = api.buildHeaders({ method: 'POST', isFormData: true })
    const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
    const resp = await fetch(`${apiUrl}/epicerie/produits/${produitId}/image`, {
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
  },

  // ── Stock — ADR-14 : lecture directe DB ────────────────────────────────

  listStock(params?: {
    search?: string
    categorie?: string
    fournisseur?: string
    is_low?: boolean
    is_empty?: boolean
    page?: number
    per_page?: number
  }): Promise<{ items: EpicerieStockRead[]; page: number; per_page: number; total: number }> {
    return massacorpApi.get(`/epicerie/stock${buildQs({ ...params })}`)
  },

  getStockStats(): Promise<EpicerieStockSummary> {
    return massacorpApi.get('/epicerie/stock/stats')
  },

  getStockByProduit(produitId: number): Promise<EpicerieStockRead> {
    return massacorpApi.get(`/epicerie/stock/${produitId}`)
  },

  updateSeuil(produitId: number, body: SeuilAlerteUpdate): Promise<EpicerieStockRead> {
    return massacorpApi.put(`/epicerie/stock/${produitId}/seuil`, body)
  },

  ajusterStock(body: AjustementCreate): Promise<AjustementResponse> {
    return massacorpApi.post('/epicerie/stock/ajustement', body)
  },

  validerComptage(body: ComptageRequest): Promise<ComptageResponse> {
    return massacorpApi.post('/epicerie/stock/comptage', body)
  },

  listMouvements(params?: {
    produit_id?: number
    type?: string
    date_debut?: string
    date_fin?: string
    page?: number
    per_page?: number
  }): Promise<{ items: EpicerieStockMovementRead[]; total: number; page: number; per_page: number }> {
    return massacorpApi.get(`/epicerie/stock/mouvements${buildQs({ ...params })}`)
  },

  // ── Catalogue POS (produit + stock, LEFT JOIN, 1 requête) ────────────

  getCatalogue(params?: {
    search?: string
    categorie?: string
    page?: number
    per_page?: number
  }): Promise<{ items: ProduitCatalogueRead[]; total: number; page: number; per_page: number }> {
    return massacorpApi.get(`/epicerie/pos/catalogue${buildQs({ ...params })}`)
  },

  // ── Ventes / Encaissement ─────────────────────────────────────────────

  encaisser(body: EncaissementRequest): Promise<EncaissementResponse> {
    return massacorpApi.post('/epicerie/encaisser', body)
  },

  listVentes(params?: {
    statut?: string
    search?: string
    limit?: number
    offset?: number
  }): Promise<{ items: EncaissementResponse[]; total: number; counts: Record<string, number> }> {
    return massacorpApi.get(`/epicerie/ventes${buildQs({ ...params })}`)
  },

  // ── Fournisseurs ─────────────────────────────────────────────────────

  listFournisseurs(): Promise<{ items: FournisseurRead[] }> {
    return massacorpApi.get('/epicerie/fournisseurs')
  },

  getFournisseurStats(vendorId: string): Promise<FournisseurStats> {
    return massacorpApi.get(`/epicerie/fournisseurs/${encodeURIComponent(vendorId)}/stats`)
  },

  listFacturesFournisseur(vendorId: string): Promise<{ items: FinanceInvoiceRead[] }> {
    return massacorpApi.get(`/epicerie/fournisseurs/${encodeURIComponent(vendorId)}/invoices`)
  },

  listCommandesFournisseur(vendorId: string): Promise<{ items: SupplyOrderRead[] }> {
    return massacorpApi.get(`/epicerie/fournisseurs/${encodeURIComponent(vendorId)}/commandes`)
  },

  getCaHistorique(vendorId: string): Promise<CaHistoriqueResponse> {
    return massacorpApi.get(`/epicerie/fournisseurs/${encodeURIComponent(vendorId)}/ca-historique`)
  },

  getStockMarges(vendorId: string): Promise<StockMargesResponse> {
    return massacorpApi.get(`/epicerie/fournisseurs/${encodeURIComponent(vendorId)}/stock-marges`)
  },

  getAlertesPrix(vendorId: string): Promise<AlertesPrixResponse> {
    return massacorpApi.get(`/epicerie/fournisseurs/${encodeURIComponent(vendorId)}/alertes-prix`)
  },

  getQualite(vendorId: string): Promise<QualiteResponse> {
    return massacorpApi.get(`/epicerie/fournisseurs/${encodeURIComponent(vendorId)}/qualite`)
  },

  creerCommande(body: SupplyOrderCreate): Promise<SupplyOrderRead> {
    return massacorpApi.post('/epicerie/commandes', body)
  },

  // ── Transferts internes ─────────────────────────────────────────────────

  listTransferts(params?: {
    status?: string
    page?: number
    per_page?: number
  }): Promise<InternalTransferListResponse> {
    return massacorpApi.get(`/epicerie/transferts${buildQs({ ...params })}`)
  },

  getTransfert(id: number): Promise<InternalTransferRead> {
    return massacorpApi.get(`/epicerie/transferts/${id}`)
  },

  creerTransfert(body: InternalTransferCreate): Promise<InternalTransferRead> {
    return massacorpApi.post('/epicerie/transferts', body)
  },

  validerTransfert(id: number): Promise<InternalTransferRead> {
    return massacorpApi.post(`/epicerie/transferts/${id}/valider`)
  },

  annulerTransfert(id: number, raison?: string): Promise<InternalTransferRead> {
    return massacorpApi.post(`/epicerie/transferts/${id}/annuler`, { raison: raison || null })
  },

  // ── Demandes restaurant entrantes (BACK-TRANSFER-RESTO-01) ───────────────

  listTransferRequests(params?: {
    page?: number
    per_page?: number
    status?: string
  }): Promise<TransferRequestListResponse> {
    return massacorpApi.get(`/epicerie/transfer-requests${buildQs({ ...params })}`)
  },

  approuverDemande(id: number): Promise<TransferRequestRead> {
    return massacorpApi.post(`/epicerie/transfer-requests/${id}/approuver`)
  },

  rejeterDemande(id: number, raison?: string): Promise<TransferRequestRead> {
    return massacorpApi.post(`/epicerie/transfer-requests/${id}/rejeter`, { raison: raison || null })
  },

  previewResolutionDemande(id: number): Promise<PreviewResolutionResponse> {
    return massacorpApi.post(`/epicerie/transfer-requests/${id}/preview-resolution`)
  },

  approveWithTransfer(
    id: number,
    body: ApproveWithTransferBody,
  ): Promise<ApproveWithTransferResult> {
    return massacorpApi.post(`/epicerie/transfer-requests/${id}/approve-with-transfer`, body)
  },
}
