// Types ETL Import — Queue factures fournisseur (ADR-25)

export type EtlImportStatut =
  | 'PENDING'
  | 'RUNNING'
  | 'PREVIEW'
  | 'VALIDATED'
  | 'REJECTED'
  | 'SUCCES'
  | 'PARTIEL'
  | 'ECHEC'

export interface EtlImportRead {
  id: number
  fournisseur_id: number | null
  fichier_source: string | null
  statut: EtlImportStatut
  nb_lignes_total: number | null
  nb_lignes_ok: number
  nb_lignes_conflit: number
  nb_lignes_erreur: number
  erreur_detail: string | null
  numero_facture: string | null
  date_facture: string | null
  montant_ht_total: number | null
  montant_tva_total: number | null
  montant_ttc_total: number | null
  vendor_code: string | null
  quality_score: number | null
  ecart_reconciliation: number | null
  created_at: string
  updated_at: string
}

export interface EtlImportListResponse {
  items: EtlImportRead[]
  total: number
}

export interface FactureUploadResponse {
  etl_import_id: number
  statut: string
  nb_lignes: number
  numero_facture: string | null
  vendor_code: string | null
  quality_score: number | null
}

export interface EtlImportUpdateRequest {
  numero_facture?: string
  date_facture?: string
  montant_ht_total?: number
  montant_tva_total?: number
  montant_ttc_total?: number
}
