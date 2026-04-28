// Types ETL Import — Queue factures fournisseur (ADR-25)

export type AutoFillSource =
  | 'norm_exact'        // S1 : désignation normalisée identique
  | 'article_four'      // S2 : même code article fournisseur
  | 'correction_history' // S3 : correction manuelle historique
  | 'tfidf_auto'        // S4 : TF-IDF ≥ 0.90 (silencieux)
  | 'tfidf_auto_soft'   // S4 : TF-IDF 0.80-0.90 (badge visible)
  | 'off_import'        // S6 : import catalogue OpenFoodFacts France

export interface AutoAppliedFieldMeta {
  source: AutoFillSource
  score: number
  candidate_id?: number | null
  candidate_designation?: string | null
}

export interface SimilarProduct {
  candidate_id: number
  designation?: string
  ean?: string | null
  categorie_code?: string | null
  marque?: string | null
  conditionnement?: string | null
  volume_unitaire_ml?: number | null
  prix_unitaire_cts?: number | null
  taux_tva_centieme?: number | null
  score: number
}

export type EtlImportStatut =
  | 'PENDING'
  | 'RUNNING'
  | 'PREVIEW'
  | 'VALIDATED'
  | 'REJECTED'
  | 'SUCCES'
  | 'PARTIEL'
  | 'ECHEC'
  | 'REVERTED'

export interface EtlImportRead {
  id: number
  fournisseur_id: number | null
  fichier_source: string | null
  fichier_path: string | null
  statut: EtlImportStatut
  validation_step?: string | null
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
  client_name: string | null
  target_tenant_id: number | null
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

export interface LigneFactureRead {
  idx: number
  designation: string
  designation_raw?: string | null
  ean?: string | null
  article_fournisseur?: string | null
  marque?: string | null
  categorie_code?: string | null
  conditionnement?: string | null
  unite_base: string
  source_fournisseur: string
  quantite?: number | null
  colisage?: number | null
  prix_unitaire_cts?: number | null
  montant_ht_cts?: number | null
  montant_ttc_cts?: number | null
  taux_tva_centieme?: number | null
  degre_alcool?: number | null
  contenant?: string | null
  volume_unitaire_ml?: number | null
  // Coordonnées PDF et confiance (Phase 2)
  page_number?: number | null
  y_position?: number | null
  confidence_score?: number | null
  // Produits similaires et prix catalogue (Phase 2+3)
  similar_products?: SimilarProduct[] | null
  // Auto-fill traçable (S1-S5)
  auto_applied_fields?: Record<string, AutoAppliedFieldMeta> | null
  prix_catalogue_actuel_cts?: number | null
}

export interface EtlImportDetail extends EtlImportRead {
  lignes: LigneFactureRead[]
  montant_ht_calcule: number | null
  montant_ttc_calcule: number | null
}

// ── Ligne mutations ──────────────────────────────────────────────────────────

export interface LigneFactureUpdate {
  idx: number
  designation?: string
  ean?: string
  marque?: string
  conditionnement?: string
  categorie_code?: string
  quantite?: number
  prix_unitaire_cts?: number
  taux_tva_centieme?: number
  auto_applied_fields?: Record<string, AutoAppliedFieldMeta> | null
}

export interface LignesBatchUpdateRequest {
  updates: LigneFactureUpdate[]
}

// ── Édition post-validation (Option B — P1/P2) ─────────────────────────────

export interface ValidatedLigneEdit {
  idx: number
  // Financier (gate PAYEE)
  quantite?: number
  prix_unitaire_cts?: number
  taux_tva_centieme?: number
  // Non-financier (gate PAYEE non applicable)
  marque?: string
  categorie_code?: string
}

export interface ValidatedLignesBatchEditRequest {
  updates: ValidatedLigneEdit[]
}

export interface ValidatedInvoiceMetaEditRequest {
  numero_facture?: string
  date_facture?: string
  vendor_code?: string
}

export interface ValidatedLinesEditWarning {
  code: string
  idx: number
  produit_id?: number
  ean?: string | null
  stock_before?: number
  stock_after?: number
  delta_requested?: number
  delta_applied?: number
  message: string
}

export interface ValidatedLignesEditResponse extends EtlImportDetail {
  warnings: ValidatedLinesEditWarning[]
}

export interface LigneAddRequest {
  designation: string
  unite_base?: string
  source_fournisseur?: string
  ean?: string
  marque?: string
  conditionnement?: string
  categorie_code?: string
  quantite?: number
  prix_unitaire_cts?: number
  taux_tva_centieme?: number
}

// ── Categories ───────────────────────────────────────────────────────────────

export interface CategoryItem {
  code: string
  label: string
}

export interface CategoryGroup {
  group: string
  label: string
  items: CategoryItem[]
}

export interface CategoriesResponse {
  groups: CategoryGroup[]
  total: number
}

// ── Validation helpers ───────────────────────────────────────────────────────

export type LigneValidationStatus = 'valid' | 'warning' | 'error'

/** Niveau de problème par champ : null = OK */
export type FieldAlert = 'error' | 'warning' | null

export interface LigneFieldAlerts {
  ean: FieldAlert
  categorie_code: FieldAlert
  marque: FieldAlert
  quantite: FieldAlert
  prix_unitaire_cts: FieldAlert
}

/** Message court par champ pour guider l'opérateur */
export const FIELD_ACTION_LABELS: Record<keyof LigneFieldAlerts, string> = {
  ean: '+ EAN',
  categorie_code: '+ Cat.',
  marque: '+ Marque',
  quantite: '+ Qte',
  prix_unitaire_cts: '+ Prix',
}

export interface LigneValidation {
  status: LigneValidationStatus
  fields: LigneFieldAlerts
  issueCount: number
}

export function validateLigne(ligne: LigneFactureRead): LigneValidation {
  const fields: LigneFieldAlerts = {
    ean: !ligne.ean ? 'warning' : null,
    categorie_code: (!ligne.categorie_code || ligne.categorie_code === 'AUTRE') ? 'warning' : null,
    marque: !ligne.marque ? 'warning' : null,
    quantite: (!ligne.quantite || ligne.quantite <= 0) ? 'error' : null,
    prix_unitaire_cts: (!ligne.prix_unitaire_cts || ligne.prix_unitaire_cts <= 0) ? 'error' : null,
  }

  const hasError = Object.values(fields).some(v => v === 'error')
  const hasWarning = Object.values(fields).some(v => v === 'warning')
  const issueCount = Object.values(fields).filter(v => v !== null).length

  const status: LigneValidationStatus =
    hasError ? 'error' : hasWarning ? 'warning' : 'valid'

  return { status, fields, issueCount }
}
