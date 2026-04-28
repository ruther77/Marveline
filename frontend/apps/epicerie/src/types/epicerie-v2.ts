// Types V2 Épicerie — source : FC_EPICERIE_POS.md, FC_EPICERIE_INVENTAIRE.md, FC_EPICERIE_FOURNISSEURS.md

// ─── Catalogue & Stock ────────────────────────────────────────────────────

export interface EpicerieProduitRead {
  id: number
  ean: string | null
  designation_clean: string
  nom_court: string | null
  description: string | null
  categorie: string | null
  unite_vente: string
  prix_unitaire_cts: number    // centimes TTC — ex : 350 = 3,50 EUR
  taux_tva: number             // centimes-pour-mille — ex : 2000 = 20%
  vendor_id: number | null
  image_url: string | null
  actif: boolean
}

export interface EpicerieStockRead {
  id: number | null                    // null si produit sans ligne stock (LEFT JOIN)
  produit_id: number
  designation: string
  categorie: string | null
  fournisseur_source: string | null
  image_url: string | null
  quantite: number
  seuil_alerte: number
  prix_achat_cts: number               // centimes HT (facture fournisseur)
  prix_unitaire_cts: number            // centimes TTC (prix de vente)
  unite_vente: string                  // unité caisse (ex: U, KG, L)
  unite_base: string | null            // unité physique (piece, kg, L, g, cL, mL, colis)
  colisage: number | null              // nombre d'unite_base par unite_vente
  volume_unitaire_ml: number | null    // volume unitaire en mL (750 = 75cL)
  conditionnement: string | null       // description texte (ex: "lot de 150")
  statut_badge: 'ok' | 'bas' | 'rupture'
  derniere_mise_a_jour: string | null  // null si pas encore de mouvement
  actif: boolean
}

export interface EpicerieStockSummary {
  total_articles: number
  nb_ruptures: number
  nb_stock_bas: number
  valeur_stock_cts: number     // centimes
}

// ─── Catalogue POS — produit + stock fusionnés (LEFT JOIN, 1 requête) ────

export interface ProduitCatalogueRead {
  id: number
  ean: string | null
  designation_clean: string
  nom_court: string | null
  categorie: string | null
  unite_vente: string
  prix_unitaire_cts: number
  taux_tva: number
  image_url: string | null
  actif: boolean
  quantite: number
  seuil_alerte: number
  statut_badge: 'ok' | 'bas' | 'rupture'
}

// ─── POS & Ventes — FC_EPICERIE_POS.md §3 ────────────────────────────────

export type ModePaiement = 'ESPECES' | 'CB' | 'VIREMENT'

export interface LigneEncaissement {
  produit_id: number
  quantite: number
  prix_unitaire_ttc: number    // centimes
}

export interface EncaissementRequest {
  lignes: LigneEncaissement[]
  mode_paiement: ModePaiement
  montant_especes: number      // centimes
  montant_cb: number           // centimes
  montant_virement: number     // centimes
  remise_centimes: number      // 0 si pas de remise
  remise_motif: string | null
  client_nom: string | null
}

export interface EncaissementResponse {
  id: number
  numero_ticket: string        // format VTE-YYYYMMDD-NNNN
  statut: 'VALIDEE'
  total_ht_brut: number
  total_tva_brut: number
  total_ttc_brut: number
  remise_centimes: number
  remise_motif: string | null
  total_ttc_remise: number
  total_ht_remise: number
  total_tva_remise: number
  monnaie_rendue: number
  created_at: string
}

// ─── Inventaire — FC_EPICERIE_INVENTAIRE.md §3 ────────────────────────────

export type TypeAjustement =
  | 'ENTREE'
  | 'SORTIE'
  | 'AJUSTEMENT'
  | 'PERTE'
  | 'VENTE'
  | 'TRANSFERT_RESTAURANT'

export interface AjustementCreate {
  produit_id: number
  type_ajustement: TypeAjustement
  quantite: number
  raison: string | null
}

export interface AjustementResponse {
  success: boolean
  mouvement_id: number
  produit_id: number
  ancien_stock: number
  nouveau_stock: number
  quantite_ajustee: number
}

export interface SeuilAlerteUpdate {
  seuil: number
}

export interface LigneComptage {
  produit_id: number
  quantite_comptee: number
  notes: string | null
}

export interface ComptageRequest {
  lignes: LigneComptage[]
  notes: string   // obligatoire — identifie la session d'inventaire
}

export interface LigneComptageResult {
  produit_id: number
  designation: string
  ancien_stock: number
  nouveau_stock: number
  ecart: number
  ecart_pct: number | null
  ajustement_cree: boolean
}

export interface ComptageResponse {
  nb_lignes: number
  nb_ajustements: number
  message: string
  lignes: LigneComptageResult[]
}

export interface EpicerieStockMovementRead {
  id: number
  produit_id: number
  produit_designation: string
  type: TypeAjustement
  quantite: number
  signed_quantite: number
  date_mouvement: string
  reference: string | null
  created_by_name: string | null
  notes: string | null
}

// ─── Fournisseurs — FC_EPICERIE_FOURNISSEURS.md §3 ────────────────────────

export type BadgeStatutFournisseur = 'a_jour' | 'en_attente' | 'en_retard'

export interface FournisseurRead {
  vendor_id: string
  nom: string
  code: string
  nb_articles: number
  ca_mensuel_cts: number
  dette_cts: number
  badge_statut: BadgeStatutFournisseur
}

export interface DistributionCategorie {
  categorie_nom: string
  pct: number
}

export interface FournisseurStats {
  vendor_id: string
  livraisons_mois: number
  achats_mois_cts: number
  delai_paiement_moyen_jours: number
  distribution_categories: DistributionCategorie[]
}

export type StatutFacture = 'EN_ATTENTE' | 'PAYEE' | 'EN_RETARD'

export interface FinanceInvoiceRead {
  id: number
  numero: string
  date_facture: string
  date_echeance: string | null
  montant_cts: number
  statut: StatutFacture
  supply_order_id: number | null
}

export type StatutCommande = 'en_attente' | 'confirmee' | 'expediee' | 'livree' | 'annulee'

export interface LigneCommandeRead {
  produit_id: number
  designation: string
  quantite: number
  prix_unitaire_cts: number
  total_ligne_cts: number
}

export interface SupplyOrderRead {
  id: number
  vendor_id: string
  vendor_nom: string
  statut: StatutCommande
  total_cts: number
  date_commande: string
  date_livraison_prevue: string | null
  date_livraison_reelle: string | null
  notes: string | null
  lignes: LigneCommandeRead[]
}

export interface LigneCommandeCreate {
  produit_id: number
  quantite: number
  prix_unitaire_cts: number
}

export interface SupplyOrderCreate {
  vendor_id: string
  lignes: LigneCommandeCreate[]
  notes: string | null
}

// ─── Enrichissements fournisseur (UX steps 2-5) ──────────────────────────────

export interface CaHistoriqueItem {
  mois: string        // 'YYYY-MM'
  montant_cts: number
}

export interface CaHistoriqueResponse {
  items: CaHistoriqueItem[]
  variation_pct: number | null
}

export interface StockMargesResponse {
  marge_moy_pct: number
  marge_catalogue_moy_pct: number
  nb_articles: number
}

export interface AlertePrixItem {
  designation: string
  ean: string | null
  prix_precedent_cts: number
  prix_actuel_cts: number
  variation_pct: number
}

export interface AlertesPrixResponse {
  alertes: AlertePrixItem[]
  date_import_precedente: string | null
  date_import_actuelle: string | null
}

export interface QualiteResponse {
  taux_livraison_temps_pct: number | null
  taux_factures_retard_pct: number | null
  nb_commandes_evaluees: number
  nb_factures_total: number
}

// ─── État UI panier (local uniquement — pas de persistance Zustand) ────────

export interface CartItem {
  produit: EpicerieProduitRead
  quantite: number
}

// ─── Transferts internes epicerie -> restaurant ──────────────────────────────

export interface TransferLineCreate {
  produit_id: number
  ingredient_id?: number | null
  quantite: number
  unite?: string
  prix_unitaire: number          // centimes HT
  tva_pct?: number               // default 2000 = 20%
}

export interface InternalTransferCreate {
  dest_tenant_id: number
  reference?: string | null
  notes?: string | null
  lignes: TransferLineCreate[]
}

export interface InternalTransferLineRead {
  id: number
  transfer_id: number
  produit_id: number
  designation: string
  ingredient_id: number | null
  quantite: number
  unite: string
  prix_unitaire: number
  tva_pct: number
  montant_ht: number
  montant_ttc: number
  mouvement_epicerie_id: number | null
  mouvement_restaurant_id: number | null
}

export type TransferStatus = 'PENDING' | 'VALIDATED' | 'CANCELLED'

export interface InternalTransferRead {
  id: number
  tenant_id: number
  dest_tenant_id: number
  reference: string | null
  status: TransferStatus
  notes: string | null
  montant_ht: number
  montant_ttc: number
  invoice_id: number | null
  invoice_numero?: string | null
  invoice_statut?: StatutFacture | null
  created_by: number | null
  validated_at: string | null
  validated_by: number | null
  cancelled_at: string | null
  raison_annulation: string | null
  created_at: string
  lignes: InternalTransferLineRead[]
}

export interface InternalTransferListResponse {
  items: InternalTransferRead[]
  total: number
  page: number
  per_page: number
}

// ─── BACK-TRANSFER-RESTO-01 — Demandes restaurant entrantes ──────────────────

export type TransferRequestStatus =
  | 'PENDING' | 'APPROVED' | 'FULFILLED' | 'REJECTED' | 'CANCELLED'

export interface TransferRequestLineRead {
  id: number
  request_id: number
  designation: string
  quantity: number
  unit: string
  ingredient_restaurant_id: number | null
  notes: string | null
}

export interface TransferRequestRead {
  id: number
  tenant_id: number
  target_tenant_id: number
  status: TransferRequestStatus
  notes: string | null
  created_by: number
  fulfilled_transfer_id: number | null
  rejection_reason: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  lignes: TransferRequestLineRead[]
}

export interface TransferRequestListResponse {
  items: TransferRequestRead[]
  total: number
  page: number
  per_page: number
}

// ─── Résolveur cascade (preview + approve-with-transfer) ─────────────────────

export interface ResolveItem {
  produit_id: number
  produit_designation: string
  produit_unite_vente: string
  ordre: number
  facteur_conv: string
  stock_disponible: string
  qte_prelevee_unites_vente: string
  qte_couverte_besoin: string
}

export interface RequestLineResolution {
  request_line_id: number
  ingredient_restaurant_id: number
  ingredient_nom: string
  qte_besoin: string
  items: ResolveItem[]
  couverture_complete: boolean
  deficit: string
}

export interface PreviewResolutionResponse {
  request_id: number
  lines: RequestLineResolution[]
  unresolvable_line_ids: number[]
  any_deficit: boolean
}

export interface ApproveOverrideLine {
  produit_id: number
  ingredient_id?: number | null
  quantite: number | string
  unite?: string
  prix_unitaire: number
  tva_pct?: number
}

export interface ApproveWithTransferBody {
  overrides?: ApproveOverrideLine[] | null
  reference?: string | null
  notes?: string | null
}

export interface ApproveWithTransferResult {
  transfer_id: number
  warnings: string[]
}

// ─── Multi-EAN & historique prix (modal détail produit) ─────────────────────

export interface EpicerieEanRead {
  id: number
  produit_id: number
  ean: string
  source_fournisseur: string | null
}

export interface EpicerieProduitEansResponse {
  produit_id: number
  ean_principal: string | null
  eans_secondaires: EpicerieEanRead[]
}

export interface PrixHistoriqueItem {
  prix_achat_cts: number
  prix_vente_cts: number
  taux_marge_pct: number | null
  source: string | null         // 'etl' | 'manual' | 'recalcul'
  reference: string | null
  source_fournisseur: string | null  // METRO, TAIYAT, ETHAN, EUROCIEL
  etl_import_id: number | null
  date: string                  // ISO date — effective_date si dispo (date facture), sinon date d'enregistrement
  recorded_at: string | null    // ISO timestamp — moment d'enregistrement (différent si import a posteriori)
}
