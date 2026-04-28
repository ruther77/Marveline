// Client API Restaurant — source : V2_API_RESTAURANT.md
// Base URL : /restaurant/* — tenant_id=3 implicite via JWT
// ADR-14 : portions_restantes + stock_actuel jamais depuis cache Redis

import { massacorpApi as api } from '@/api'
import type {
  RestaurantDashboardStats,
  InstancePreparationRead,
  RupturesDashboard,
  ActiviteItem,
  TableRead,
  CommandeCreatedRead,
  CommandeDetailRead,
  TypePreparationRead,
  StockRequisRead,
  TicketCuisineResponse,
  CategorieIngredientRead,
  CategorieIngredientCreateBody,
  CategorieIngredientUpdateBody,
  IngredientRead,
  IngredientCreateBody,
  IngredientUpdateBody,
  MouvementStockRead,
  BoissonsTicket,
  CatalogueBoisson,
  CommandeHistoriqueRead,
  CommandeHistoriqueDetail,
  TypeMouvementStock,
  SideRead,
  VariantePlatRead,
  VarianteSideRead,
  RecetteLigneRead,
  LigneCommandeRestaurant,
  SuggestionFormule,
  TransferRequestRead,
  TransferRequestListResponse,
  TransferRequestCreateBody,
} from '@/types/restaurant-v2'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
  return entries.length ? '?' + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&') : ''
}

/** Upload multipart/form-data — api.post() JSON.stringify le body, donc on passe par fetch natif */
async function postFile<T>(path: string, file: File): Promise<T> {
  const formData = new FormData()
  formData.append('file', file)
  const headers = api.buildHeaders({ method: 'POST', isFormData: true })
  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
  const resp = await fetch(`${apiUrl}${path}`, {
    method: 'POST',
    headers,
    body: formData,
    credentials: 'include',
  })
  if (!resp.ok) {
    const json = await resp.json().catch(() => ({}))
    throw new Error((json as { detail?: string }).detail || `Erreur ${resp.status}`)
  }
  if (resp.status === 204) return undefined as T
  const json = await resp.json()
  return ((json as { data?: T }).data ?? json) as T
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export const restaurantApi = {
  getDashboardStats(date?: string): Promise<RestaurantDashboardStats> {
    return api.get(`/restaurant/dashboard/stats${qs({ date })}`)
  },

  getMarmites(date?: string): Promise<{ items: InstancePreparationRead[] }> {
    return api.get(`/restaurant/dashboard/marmites${qs({ date })}`)
  },

  getRuptures(): Promise<RupturesDashboard> {
    return api.get('/restaurant/dashboard/ruptures')
  },

  getActiviteRecente(limit = 10): Promise<{ items: ActiviteItem[] }> {
    return api.get(`/restaurant/dashboard/activite${qs({ limit })}`)
  },

  // ── Tables & Commandes ────────────────────────────────────────────────────

  listTables(): Promise<{ items: TableRead[] }> {
    return api.get('/restaurant/tables')
  },

  getCommande(id: number): Promise<CommandeDetailRead> {
    return api.get(`/restaurant/commandes/${id}`)
  },

  ouvrirCommande(body: { table_id?: number | null; nb_couverts: number; nom_client?: string | null }): Promise<CommandeCreatedRead> {
    return api.post('/restaurant/commandes', body)
  },

  // ── CRUD Tables ──────────────────────────────────────────────────────────

  createTable(body: { numero: string; capacite: number }): Promise<TableRead> {
    return api.post('/restaurant/tables', body)
  },

  updateTable(id: number, body: { numero?: string; capacite?: number; is_active?: boolean }): Promise<TableRead> {
    return api.patch(`/restaurant/tables/${id}`, body)
  },

  deleteTable(id: number): Promise<void> {
    return api.delete(`/restaurant/tables/${id}`)
  },

  ajouterLigne(commandeId: number, body: {
    variante_plat_id: number
    instance_preparation_id: number | null
    side_id: number | null
    quantite: number
    notes: string | null
  }): Promise<{ ligne: LigneCommandeRestaurant; suggestion_formule: SuggestionFormule | null }> {
    return api.post(`/restaurant/commandes/${commandeId}/lignes`, body)
  },

  supprimerLigne(commandeId: number, ligneId: number): Promise<void> {
    return api.delete(`/restaurant/commandes/${commandeId}/lignes/${ligneId}`)
  },

  annulerCommande(commandeId: number): Promise<void> {
    return api.delete(`/restaurant/commandes/${commandeId}`)
  },

  payerCommande(commandeId: number, body: {
    mode_paiement: string
    montant_encaisse_cts: number
    pourboire_cts: number
    fractions: null | { label: string; montant_cts: number; mode: string }[]
  }): Promise<CommandeHistoriqueDetail> {
    return api.post(`/restaurant/commandes/${commandeId}/payer`, body)
  },

  getSides(includeInactive?: boolean): Promise<SideRead[]> {
    return api.get(`/restaurant/sides${qs({ include_inactive: includeInactive || undefined })}`)
  },

  createSide(body: { nom: string; image_url?: string | null; ingredient_id?: number | null; quantite_par_portion?: number | null }): Promise<SideRead> {
    return api.post('/restaurant/sides', body)
  },

  updateSide(id: number, body: { nom?: string; image_url?: string | null; ingredient_id?: number | null; quantite_par_portion?: number | null; is_active?: boolean }): Promise<SideRead> {
    return api.patch(`/restaurant/sides/${id}`, body)
  },

  getVariantesPlat(type?: 'plat' | 'boisson' | 'formule', includeInactive?: boolean): Promise<VariantePlatRead[]> {
    return api.get(`/restaurant/variantes-plat${qs({ type, include_inactive: includeInactive || undefined })}`)
  },

  createVariantePlat(body: {
    nom: string
    type: 'plat' | 'boisson' | 'formule'
    prix_vente_cts: number
    taux_tva: number
    categorie?: string | null
    image_url?: string | null
    type_preparation_id?: number | null
    ingredient_proteine_id?: number | null
    quantite_proteine?: number
  }): Promise<VariantePlatRead> {
    return api.post('/restaurant/variantes-plat', body)
  },

  updateVariantePlat(id: number, body: {
    nom?: string
    prix_vente_cts?: number
    taux_tva?: number
    categorie?: string | null
    image_url?: string | null
    type_preparation_id?: number | null
    ingredient_proteine_id?: number | null
    quantite_proteine?: number | null
    is_active?: boolean
  }): Promise<VariantePlatRead> {
    return api.patch(`/restaurant/variantes-plat/${id}`, body)
  },

  uploadRestaurantImage(file: File): Promise<{ url: string }> {
    return postFile<{ url: string }>('/restaurant/uploads/image', file)
  },

  // ── Sides par plat (liaisons avec supplément) ────────────────────────────

  listVarianteSides(varianteId: number): Promise<VarianteSideRead[]> {
    return api.get(`/restaurant/variantes-plat/${varianteId}/sides`)
  },

  addVarianteSide(varianteId: number, body: { side_id: number; supplement_cts: number }): Promise<VarianteSideRead> {
    return api.post(`/restaurant/variantes-plat/${varianteId}/sides`, body)
  },

  updateVarianteSide(varianteId: number, sideId: number, body: { supplement_cts?: number; is_active?: boolean }): Promise<VarianteSideRead> {
    return api.patch(`/restaurant/variantes-plat/${varianteId}/sides/${sideId}`, body)
  },

  removeVarianteSide(varianteId: number, sideId: number): Promise<void> {
    return api.delete(`/restaurant/variantes-plat/${varianteId}/sides/${sideId}`)
  },

  // ── Cuisine ───────────────────────────────────────────────────────────────

  createTypePreparation(body: {
    nom: string
    portions_par_batch: number
    notes?: string | null
  }): Promise<TypePreparationRead> {
    return api.post('/restaurant/types-preparation', body)
  },

  listTypesPreparation(): Promise<TypePreparationRead[]> {
    return api.get('/restaurant/types-preparation')
  },

  updateTypePreparation(typeId: number, body: {
    nom?: string
    portions_par_batch?: number
    notes?: string | null
  }): Promise<TypePreparationRead> {
    return api.patch(`/restaurant/types-preparation/${typeId}`, body)
  },

  deleteTypePreparation(typeId: number): Promise<void> {
    return api.delete(`/restaurant/types-preparation/${typeId}`)
  },

  getStockRequis(typeId: number): Promise<StockRequisRead> {
    return api.get(`/restaurant/types-preparation/${typeId}/stock-requis`)
  },

  listRecette(typeId: number): Promise<RecetteLigneRead[]> {
    return api.get(`/restaurant/types-preparation/${typeId}/recette`)
  },

  addRecetteLigne(typeId: number, body: {
    ingredient_id: number
    quantite_par_batch: number
    notes?: string | null
  }): Promise<RecetteLigneRead> {
    return api.post(`/restaurant/types-preparation/${typeId}/recette`, body)
  },

  removeRecetteLigne(typeId: number, ligneId: number): Promise<void> {
    return api.delete(`/restaurant/types-preparation/${typeId}/recette/${ligneId}`)
  },

  listInstances(date?: string): Promise<{ items: InstancePreparationRead[] }> {
    return api.get(`/restaurant/instances-preparation${qs({ date_cuisine: date })}`)
  },

  lancerMarmite(body: {
    type_preparation_id: number
    portions_initiales: number
    date_cuisine: string
    notes: string | null
  }): Promise<InstancePreparationRead> {
    return api.post('/restaurant/instances-preparation', body)
  },

  ajusterPortions(instanceId: number, ajustement: number): Promise<InstancePreparationRead> {
    return api.patch(`/restaurant/instances-preparation/${instanceId}/portions`, { ajustement })
  },

  getTicketsCuisine(): Promise<TicketCuisineResponse> {
    return api.get('/restaurant/commandes/tickets-cuisine')
  },

  updateStatutPlat(ligneId: number, statut: string): Promise<void> {
    return api.patch(`/restaurant/lignes-commande/${ligneId}/statut`, { statut })
  },

  marquerPret(commandeId: number, ligne_ids?: number[]): Promise<void> {
    return api.post(`/restaurant/commandes/${commandeId}/marquer-pret`, { ligne_ids: ligne_ids ?? null })
  },

  marquerServi(commandeId: number, ligne_ids?: number[]): Promise<void> {
    return api.post(`/restaurant/commandes/${commandeId}/marquer-servi`, { ligne_ids: ligne_ids ?? null })
  },

  // ── Ingrédients & Stock ───────────────────────────────────────────────────

  listCategoriesIngredient(): Promise<CategorieIngredientRead[]> {
    return api.get('/restaurant/categories-ingredient')
  },

  createCategorieIngredient(body: CategorieIngredientCreateBody): Promise<CategorieIngredientRead> {
    return api.post('/restaurant/categories-ingredient', body)
  },

  updateCategorieIngredient(id: number, body: CategorieIngredientUpdateBody): Promise<CategorieIngredientRead> {
    return api.patch(`/restaurant/categories-ingredient/${id}`, body)
  },

  deleteCategorieIngredient(id: number): Promise<void> {
    return api.delete(`/restaurant/categories-ingredient/${id}`)
  },

  getCategorieUsages(id: number): Promise<{ count: number }> {
    return api.get(`/restaurant/categories-ingredient/${id}/usages`)
  },

  listIngredients(params?: {
    search?: string
    categorie_id?: number
    statut?: string
    page?: number
    per_page?: number
  }): Promise<{ items: IngredientRead[]; total: number; page: number; per_page: number; ruptures_count: number }> {
    return api.get(`/restaurant/ingredients${qs({ ...params })}`)
  },

  getIngredient(id: number): Promise<IngredientRead> {
    return api.get(`/restaurant/ingredients/${id}`)
  },

  createIngredient(body: IngredientCreateBody): Promise<IngredientRead> {
    return api.post('/restaurant/ingredients', body)
  },

  updateIngredient(id: number, body: IngredientUpdateBody): Promise<IngredientRead> {
    return api.put(`/restaurant/ingredients/${id}`, body)
  },

  deleteIngredient(id: number): Promise<void> {
    return api.delete(`/restaurant/ingredients/${id}`)
  },

  listEpuises(): Promise<IngredientRead[]> {
    return api.get('/restaurant/ingredients/epuises')
  },

  ajusterStockIngredient(ingredientId: number, body: {
    type_mouvement: TypeMouvementStock
    quantite: number
    notes: string | null
  }): Promise<MouvementStockRead> {
    return api.post(`/restaurant/ingredients/${ingredientId}/mouvements`, body)
  },

  listMouvementsIngredient(params?: {
    ingredient_id?: number
    type_mouvement?: string
    date_debut?: string
    date_fin?: string
    page?: number
    per_page?: number
  }): Promise<{ items: MouvementStockRead[]; total: number; page: number; per_page: number }> {
    return api.get(`/restaurant/mouvements-stock${qs({ ...params })}`)
  },

  // ── Bar ───────────────────────────────────────────────────────────────────

  getBoissonsEnAttente(): Promise<{ items: BoissonsTicket[] }> {
    return api.get('/restaurant/commandes/tickets-bar')
  },

  getCatalogueBoissons(): Promise<{ items: CatalogueBoisson[] }> {
    return api.get('/restaurant/boissons/catalogue')
  },

  appliquerFormule(commandeId: number, varianteFormuleId: number): Promise<CommandeDetailRead> {
    return api.post(`/restaurant/commandes/${commandeId}/appliquer-formule`, { variante_formule_id: varianteFormuleId })
  },

  // ── Historique ────────────────────────────────────────────────────────────

  listHistorique(params?: {
    statut?: string
    date_debut?: string
    date_fin?: string
    page?: number
    per_page?: number
  }): Promise<{ items: CommandeHistoriqueRead[]; total: number; ca_periode_cts: number }> {
    return api.get(`/restaurant/historique/commandes${qs({ ...params })}`)
  },

  getCommandeDetail(id: number): Promise<CommandeHistoriqueDetail> {
    return api.get(`/restaurant/historique/commandes/${id}`)
  },

  // ── Demandes de transfert (BACK-TRANSFER-RESTO-01) ───────────────────────

  listTransferRequests(params?: {
    page?: number
    per_page?: number
    status?: string
  }): Promise<TransferRequestListResponse> {
    return api.get(`/restaurant/transferts${qs({ ...params })}`)
  },

  demanderTransfert(body: TransferRequestCreateBody): Promise<TransferRequestRead> {
    return api.post('/restaurant/transferts/demander', body)
  },

  annulerDemandeTransfert(id: number, raison?: string): Promise<TransferRequestRead> {
    return api.post(`/restaurant/transferts/${id}/annuler`, { raison: raison || null })
  },
}
