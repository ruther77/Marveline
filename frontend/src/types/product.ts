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
  is_active: boolean
  created_at: string
  updated_at: string
  // Computed fields (backend)
  price_per_day_euros: number
  is_available: boolean
}

// Correspond au schema backend ProductResponse (detail)
export interface ProductWithRelations extends Product {
  deposit_amount_cents: number
  deposit_amount_euros: number
  image_url: string | null
  is_out_of_stock: boolean
}

export interface ProductVariation {
  id: number
  product_id: number
  sku: string
  attributes: Record<string, string>
  stock_quantity: number
  price_adjustment: number
  is_active: boolean
}

export interface ProductImage {
  id: number
  product_id: number
  url: string
  alt_text: string | null
  display_order: number
  is_primary: boolean
}

// Bundles/Formules
export interface Bundle {
  id: number
  tenant_id: number
  name: string
  slug: string
  description: string | null
  short_description: string | null
  bundle_price: number // En centimes (DB storage)
  bundle_price_euros: number // Computed field backend
  cleaning_fee: number // En centimes (DB storage)
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
  individual_price: number | null
  savings: number | null
}

export interface BundleItem {
  id: number
  bundle_id: number
  product_id: number
  quantity: number
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
  items: Array<{
    product_id: number
    product_name: string
    quantity: number
    unit_price_cents: number
    line_total_cents: number
  }>
}

export interface ProductVariationCreate {
  sku: string
  attributes: Record<string, string>
  stock_quantity?: number
  price_adjustment?: number
  is_active?: boolean
}

export interface ProductImageCreate {
  url: string
  alt_text?: string
  display_order?: number
  is_primary?: boolean
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

// Pagination response
export interface PaginatedProducts {
  items: Product[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PaginatedBundles {
  items: Bundle[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
