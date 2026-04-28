// Types V2 Restaurant — source : V2_API_RESTAURANT.md, V2_ARCHITECTURE_PLAN.md §6.R
// tenant_id=3 — lecture directe DB pour portions_restantes et stock_actuel (ADR-14)

// ─── Dashboard ───────────────────────────────────────────────────────────────

export interface RestaurantDashboardStats {
  date: string
  ca_cts: number                    // centimes — somme commandes SERVIE/PAYEE
  nb_couverts: number
  ticket_moyen_cts: number
  commandes_ouvertes: number
  marmites_actives: number
  ruptures_count: number
}

export type StatutBadge = 'dispo' | 'faible' | 'epuise'
export type StockBadge = 'full' | 'low' | 'out'

export interface ProteineDisponible {
  ingredient_id: number
  nom: string
  stock_actuel_kg: number
  stock_badge: StockBadge
  unite_stock: string
  variante_plat_id: number | null
  variante_nom: string | null
  prix_vente_cts: number | null
}

export interface InstancePreparationRead {
  instance_id: number
  type_preparation_nom: string
  type_preparation_id: number
  date_cuisine: string
  heure_lancement: string          // ISO datetime — created_at de l'instance (R1)
  created_by_nom: string | null    // full_name du créateur (R1)
  portions_initiales: number
  portions_restantes: number
  pourcentage_restant: number      // arrondi entier (R1)
  statut_badge: StatutBadge        // dispo | faible | epuise (R1)
  est_fraiche: boolean             // date_cuisine == today() (R1)
  proteines_disponibles: ProteineDisponible[]
}

export interface RupturesDashboard {
  instances_vides: { instance_id: number; type_preparation_nom: string; portions_restantes: number }[]
  ingredients_epuises: { ingredient_id: number; nom: string; stock_actuel_kg: number; unite_stock: string }[]
}

export interface ActiviteItem {
  commande_id: number
  table_numero: string
  statut: string
  date_ouverture: string
  date_fermeture: string | null
  total_cts: number
}

// ─── Tables & Commandes ───────────────────────────────────────────────────────

export type TableStatut = 'LIBRE' | 'OUVERTE' | 'SERVIE'
export type CommandeStatut = 'OUVERTE' | 'SERVIE' | 'PAYEE' | 'ANNULEE'
export type StatutPlat = 'ENVOYEE' | 'LANCEE' | 'PRETE' | 'SERVIE'

export interface VariantePlatRead {
  id: number
  nom: string
  type: 'plat' | 'boisson' | 'formule'
  prix_vente_cts: number
  taux_tva: number
  image_url: string | null
  type_preparation_id: number | null
  type_preparation_nom: string | null
  ingredient_proteine_id: number | null
  ingredient_proteine_nom: string | null
  quantite_proteine: number | null
  categorie: string | null
  is_active: boolean
}

export interface LignePreviewRead {
  ligne_id: number
  variante_nom: string
  quantite: number
  statut_plat: StatutPlat
}

export interface SideRead {
  id: number
  nom: string
  image_url: string | null
  ingredient_id: number | null
  ingredient_nom: string | null
  quantite_par_portion: number | null
  is_active: boolean
  nb_plats_lies: number
}

export interface TableRead {
  id: number
  numero: string
  capacite: number
  statut: TableStatut
  commande_active: {
    commande_id: number
    nb_couverts: number
    nom_client: string | null
    date_ouverture: string
    nb_plats: number
    nb_plats_servis: number
    total_provisoire_cts: number
    lignes_preview: LignePreviewRead[]
  } | null
}

export interface LigneCommandeRestaurant {
  ligne_id: number
  variante_nom: string
  side_nom: string | null
  instance_preparation_id: number | null
  statut_plat: StatutPlat
  prix_unitaire_cts: number
  quantite: number
  notes: string | null
}

// Shape retournée par POST /commandes (sans lignes — lecture légère)
export interface CommandeCreatedRead {
  id: number
  table_numero: string | null
  statut: CommandeStatut
  date_ouverture: string
  date_fermeture: string | null
  nb_couverts: number
  nom_client: string | null
  total_cts: number | null
  pourboire_cts: number
}

export interface CommandeDetailRead {
  id: number
  table_numero: string | null
  nom_client: string | null
  statut: CommandeStatut
  date_ouverture: string
  nb_couverts: number
  lignes: LigneCommandeRestaurant[]
  sous_total_cts: number
  tva_cts: number
  total_cts: number
}

// ─── Cuisine ──────────────────────────────────────────────────────────────────

export interface TypePreparationRead {
  id: number
  nom: string
  portions_par_batch: number
  temps_cuisson_min: number
  image_url: string | null
  notes: string | null
  is_active: boolean
}

export interface RecetteLigneRead {
  id: number
  ingredient_id: number
  nom: string
  quantite_par_batch: number
  unite: string
  notes: string | null
}

export interface IngredientStockRequis {
  ingredient_id: number
  nom: string
  quantite_par_batch: number
  unite: string
  stock_actuel: number
  suffisant: boolean
}

export interface StockRequisRead {
  type_preparation_id: number
  nom: string
  portions_par_batch: number
  ingredients_requis: IngredientStockRequis[]
}

/** @deprecated Shape plate — conservé pour compatibilité interne. Utiliser TicketCuisineTicket. */
export interface TicketCuisineItem {
  ligne_id: number
  commande_id: number
  table_numero: string
  statut_plat: StatutPlat
  variante_nom: string
  side_nom: string | null
  notes: string | null
  heure_commande: string
}

// Tickets cuisine groupés — R2 (shape retournée par GET /commandes/tickets-cuisine)

export interface TicketCuisineLigne {
  ligne_id: number
  variante_nom: string
  side_nom: string | null
  statut_plat: StatutPlat
  instance_preparation_id: number | null
  stock_disponible: boolean        // portions_restantes > 0 ou pas d'instance (ADR-14)
  notes: string | null
}

export interface TicketCuisineTicket {
  ticket_id: string                // "T{commande_id}"
  commande_id: number
  table_numero: string | null
  heure_envoi: string | null       // ISO datetime
  lignes: TicketCuisineLigne[]
}

export interface TicketCuisineResponse {
  items: TicketCuisineTicket[]
}

// ─── Ingrédients & Stock ──────────────────────────────────────────────────────

export type TypeMouvementStock = 'entree' | 'consommation' | 'transfert_entrant' | 'inventaire' | 'perte'

export interface CategorieIngredientRead {
  id: number
  tenant_id: number
  nom: string
  image_url: string | null
  is_proteine: boolean
}

export interface CategorieIngredientCreateBody {
  nom: string
  image_url?: string | null
  is_proteine?: boolean
}

export interface CategorieIngredientUpdateBody {
  nom?: string
  image_url?: string | null
  is_proteine?: boolean
}

export interface IngredientCreateBody {
  nom: string
  unite_stock: string
  categorie_id?: number | null
  stock_actuel?: number
  stock_alerte?: number
  cout_unitaire_cts?: number
}

export interface IngredientUpdateBody {
  nom?: string
  unite_stock?: string
  categorie_id?: number | null
  stock_alerte?: number
  cout_unitaire_cts?: number
}

export interface IngredientRead {
  id: number
  nom: string
  image_url: string | null
  categorie: string | null
  categorie_id: number | null
  stock_actuel: number            // NUMERIC(10,3) — ex: kg
  stock_alerte: number            // seuil bas
  unite_stock: string             // T1: aligné backend (was "unite")
  cout_unitaire_cts: number       // T2: coût achat en centimes
  statut: 'ok' | 'bas' | 'rupture'
  derniere_entree: string | null  // ISO date
}

export interface MouvementStockRead {
  id: number
  tenant_id: number               // T7
  ingredient_id: number
  ingredient_nom: string
  ingredient_unite: string        // B2: unité pour affichage "+2.0 kg"
  type_mouvement: TypeMouvementStock  // T4: aligné backend (was "type")
  quantite: number                // signé
  stock_apres: number             // T5: snapshot post-mouvement
  date_mouvement: string          // T6: ISO datetime
  notes: string | null
  created_by_name: string | null
  created_at: string
}

// ─── Menu — Liaison plat ↔ side ───────────────────────────────────────────────

export interface VarianteSideRead {
  id: number
  side_id: number
  side_nom: string
  side_image_url: string | null
  supplement_cts: number
  is_active: boolean
}

// ─── Bar ──────────────────────────────────────────────────────────────────────

export interface BoissonsTicketLigne {
  ligne_id: number
  variante_nom: string
  quantite: number
  prix_unitaire_cts: number
  statut_plat: StatutPlat
  notes: string | null
  heure_commande: string
  suggestion_formule: SuggestionFormule | null
}

export interface SuggestionFormule {
  variante_formule_id: number
  label: string
  economies_cts: number
  boissons_concernees_ids: number[]
}

export interface BoissonsTicket {
  commande_id: number
  table_numero: string
  date_ouverture: string
  suggestion_formule: SuggestionFormule | null
  lignes: BoissonsTicketLigne[]
}

export interface CatalogueBoisson {
  variante_plat_id: number
  nom: string
  categorie: string
  prix_vente_cts: number
}

// ─── Historique ───────────────────────────────────────────────────────────────

export interface CommandeHistoriqueRead {
  id: number
  table_numero: string
  statut: CommandeStatut
  date_ouverture: string
  date_fermeture: string | null
  nb_couverts: number
  total_cts: number
  pourboire_cts: number
}

export interface LigneHistoriqueRead {
  ligne_id: number
  type: 'plat' | 'boisson'
  description: string
  side: string | null
  quantite: number
  prix_unitaire_cts: number
  montant_cts: number
}

export interface CommandeHistoriqueDetail {
  id: number
  table_numero: string
  statut: CommandeStatut
  date_ouverture: string
  date_fermeture: string | null
  nb_couverts: number
  lignes: LigneHistoriqueRead[]
  sous_total_cts: number
  tva_cts: number
  total_ttc_cts: number
  pourboire_cts: number
  mode_paiement: string | null
}

// ─── BACK-TRANSFER-RESTO-01 — Demandes de transfert restaurant → épicerie ───

export type TransferRequestStatus =
  | 'PENDING' | 'APPROVED' | 'FULFILLED' | 'REJECTED' | 'CANCELLED'

export interface TransferRequestLineCreateBody {
  designation: string
  quantity: number
  unit?: string
  ingredient_restaurant_id?: number | null
  notes?: string | null
}

export interface TransferRequestCreateBody {
  target_tenant_id: number
  notes?: string | null
  lignes: TransferRequestLineCreateBody[]
}

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
