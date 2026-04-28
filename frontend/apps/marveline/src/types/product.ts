// Catégories
export interface Category {
  id: number
  tenant_id: number
  parent_id: number | null
  name: string
  slug: string
  description: string | null
  image_url: string | null
  display_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CategoryTreeNode extends Category {
  children: CategoryTreeNode[]
}

// Produits — Correspond au schema backend ProductList
export interface Product {
  id: number
  tenant_id: number
  name: string
  sku: string
  category: string
  price_per_day_cents: number
  stock_quantity: number
  available_quantity: number
  condition: string
  image_url: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  tva_rate: number
  weight_grams?: number | null
  volume_cm3?: number | null
  // Computed fields (backend)
  price_per_day_euros: number
  is_available: boolean
}

export interface ProductImage {
  id: number
  tenant_id: number
  product_id: number
  url: string
  sort_order: number
  is_primary: boolean
  created_at: string
  updated_at: string
}

// Correspond au schema backend ProductResponse (detail)
export interface ProductWithRelations extends Product {
  description: string | null
  short_description: string | null
  deposit_amount_cents: number
  deposit_amount_euros: number
  cleaning_fee_cents: number
  cleaning_fee_euros: number
  requires_advance_booking_days: number
  qty_reserved: number
  qty_on_location: number
  qty_damaged: number
  qty_in_repair: number
  image_url: string | null
  is_out_of_stock: boolean
  weight_grams?: number | null
  volume_cm3?: number | null
}

// ProductVariation legacy supprime — utiliser ProductVariant de types/product_variant.ts
// ProductImage duplique supprime — la definition canonique est plus haut (L41-50)

// Bundles/Formules
export interface Bundle {
  id: number
  tenant_id: number
  name: string
  slug: string
  description: string | null
  short_description: string | null
  image_url: string | null
  bundle_price_cents: number // En centimes (DB storage)
  bundle_price_euros: number // Computed field backend
  cleaning_fee_cents: number // En centimes (DB storage)
  cleaning_fee_euros: number // Computed field backend
  featured: boolean
  display_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface BundleWithItems extends Bundle {
  items: BundleItem[]
  total_items: number
  individual_price_cents: number
  savings_cents: number
  individual_price_euros: number
  savings_euros: number
}

export interface BundleItem {
  id: number
  bundle_id: number
  product_id: number
  quantity: number
  display_order: number
  product: Product
}

// Create/Update DTOs
export interface CategoryCreate {
  name: string
  parent_id?: number | null
  description?: string
  image_url?: string
  display_order?: number
  is_active?: boolean
}

export interface CategoryUpdate {
  name?: string
  parent_id?: number | null
  description?: string
  image_url?: string
  display_order?: number
  is_active?: boolean
}

// Correspond au schema backend ProductCreate
export interface ProductCreate {
  name: string
  sku: string
  category: string
  price_per_day_cents: number
  deposit_amount_cents?: number
  stock_quantity?: number
  available_quantity?: number
  condition?: string
  image_url?: string
  weight_grams?: number | null
  volume_cm3?: number | null
}

// Correspond au schema backend ProductUpdate
export interface ProductUpdate {
  name?: string
  category?: string
  price_per_day_cents?: number
  deposit_amount_cents?: number
  stock_quantity?: number
  available_quantity?: number
  condition?: string
  image_url?: string
  is_active?: boolean
  weight_grams?: number | null
  volume_cm3?: number | null
}

export interface BundleCreate {
  name: string
  slug?: string
  description?: string
  short_description?: string
  bundle_price_cents: number // Prix en centimes
  cleaning_fee_cents?: number // Frais en centimes
  featured?: boolean
  display_order?: number
  is_active?: boolean
  items?: BundleItemCreate[] // Optionnel car peut être ajouté après création
}

export interface BundleUpdate {
  name?: string
  slug?: string
  description?: string
  short_description?: string
  bundle_price_cents?: number // Prix en centimes
  cleaning_fee_cents?: number // Frais en centimes
  featured?: boolean
  display_order?: number
  is_active?: boolean
}

export interface BundleItemCreate {
  product_id: number
  quantity: number
}

export interface BundlePriceCalc {
  bundle_price_cents: number
  individual_price_cents: number
  savings_cents: number
  savings_percent: number
  items: Array<Record<string, unknown>>
}

// ProductVariationCreate legacy supprime — utiliser ProductVariantCreate de types/product_variant.ts
// ProductImageCreate supprime — upload via FormData (pas de body JSON)

// Availability (P2-22)
export interface ProductAvailabilitySlot {
  date_from: string   // YYYY-MM-DD
  date_to: string     // YYYY-MM-DD
  reserved_quantity: number
  reservation_id: number
  reservation_ref: string
}

export interface ProductAvailabilityResponse {
  product_id: number
  total_quantity: number
  date_from: string
  date_to: string
  busy_slots: ProductAvailabilitySlot[]
}

export interface ProductImportRowError {
  row: number
  field?: string | null
  message: string
}

export interface ProductImportReport {
  created: number
  skipped: number
  errors: ProductImportRowError[]
}

// Labels humains pour les 20 categories enum backend (ProductCategory)
export const CATEGORY_LABELS: Record<string, string> = {
  assiettes: 'Assiettes',
  verres: 'Verres',
  couverts: 'Couverts',
  nappes: 'Nappes',
  serviettes: 'Serviettes',
  nappages: 'Nappages',
  tables: 'Tables',
  chaises: 'Chaises',
  bancs: 'Bancs',
  mobilier: 'Mobilier',
  machines: 'Machines',
  candy_bar: 'Candy Bar',
  mange_debout: 'Mange-debout',
  decorations: 'Décorations',
  housses: 'Housses',
  accessoires_transport: 'Transport',
  vaisselle: 'Vaisselle',
  vaisselle_service: 'Service',
  vaisselle_enfants: 'Enfants',
  porcelaine: 'Porcelaine',
}

// Stock statuses
export type StockStatus = 'in_stock' | 'low_stock' | 'out_of_stock'

/** Derive stock status from product quantities (backend ne retourne pas stock_status) */
export function getStockStatus(product: { available_quantity: number; stock_quantity: number }): StockStatus {
  if (product.available_quantity === 0) return 'out_of_stock'
  if (product.available_quantity <= Math.max(product.stock_quantity * 0.2, 3)) return 'low_stock'
  return 'in_stock'
}

export function getStockStatusColor(product: { available_quantity: number; stock_quantity: number }): string {
  const status = getStockStatus(product)
  switch (status) {
    case 'in_stock': return 'text-green-500'
    case 'low_stock': return 'text-yellow-500'
    case 'out_of_stock': return 'text-red-500'
  }
}

export function getStockStatusLabel(product: { available_quantity: number; stock_quantity: number }): string {
  const status = getStockStatus(product)
  switch (status) {
    case 'in_stock': return 'En stock'
    case 'low_stock': return 'Stock faible'
    case 'out_of_stock': return 'Rupture'
  }
}

export function getStockBarColor(product: { available_quantity: number; stock_quantity: number }): string {
  const status = getStockStatus(product)
  switch (status) {
    case 'in_stock': return 'bg-green-500'
    case 'low_stock': return 'bg-yellow-500'
    case 'out_of_stock': return 'bg-red-500'
  }
}

export function getStockPercent(product: { available_quantity: number; stock_quantity: number }): number {
  if (product.stock_quantity === 0) return 0
  return Math.round((product.available_quantity / product.stock_quantity) * 100)
}

// Pagination response — alias vers PaginatedResponse<T> standard
import type { PaginatedResponse } from './index'
export type PaginatedProducts = PaginatedResponse<Product>
export type PaginatedBundles = PaginatedResponse<Bundle>
