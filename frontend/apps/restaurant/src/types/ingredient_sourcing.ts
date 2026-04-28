// Types — Mapping ingrédient restaurant → produits épicerie + résolveur cascade
// Aligné sur app/schemas/restaurant/ingredient_epicerie_mapping.py

export interface MappingRead {
  id: number
  tenant_id: number
  ingredient_id: number
  produit_id: number
  ordre: number
  facteur_conv: string            // Decimal sérialisé en string
  notes: string | null
  created_at: string
  updated_at: string
}

export interface MappingWithProduit extends MappingRead {
  produit_designation: string
  produit_unite_vente: string     // U | KG | L
  produit_stock_disponible: string // Decimal string (stock en unité vente)
}

export interface MappingListResponse {
  items: MappingWithProduit[]
}

export interface MappingCreateBody {
  produit_id: number
  ordre?: number                  // défaut 0
  facteur_conv?: number | string  // défaut 1
  notes?: string | null
}

export interface MappingUpdateBody {
  ordre?: number
  facteur_conv?: number | string
  notes?: string | null
}

export interface MappingReorderItem {
  produit_id: number
  ordre: number
}

export interface MappingReorderBody {
  items: MappingReorderItem[]
}

// ── Résolveur cascade ────────────────────────────────────────────────────────

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

export interface ResolveResponse {
  ingredient_id: number
  qte_besoin: string
  qte_couverte_totale: string
  deficit: string
  couverture_complete: boolean
  items: ResolveItem[]
}

export interface ResolveRequestBody {
  qte_besoin: number | string
}

// ── Recherche produits épicerie (picker mapping) ─────────────────────────────

export interface ProduitEpicerieSearchItem {
  id: number
  tenant_id: number
  designation_clean: string
  ean: string | null
  unite_vente: string
  prix_achat_cts: number
  stock_disponible: number
}

export interface ProduitEpicerieSearchResponse {
  items: ProduitEpicerieSearchItem[]
}
