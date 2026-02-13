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

// Produits
export interface Product {
  id: number
  tenant_id: number
  category_id: number | null
  sku: string
  name: string
  slug: string
  description: string | null
  short_description: string | null
  stock_quantity: number
  stock_status: string
  base_price: number
  featured: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ProductWithRelations extends Product {
  category: Category | null
  variations: ProductVariation[]
  images: ProductImage[]
  prices: ProductPrice[]
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

export interface ProductPrice {
  id: number
  product_id: number
  price_type: string
  amount: number
  valid_from: string | null
  valid_until: string | null
}

// Bundles/Formules
export interface Bundle {
  id: number
  tenant_id: number
  name: string
  slug: string
  description: string | null
  short_description: string | null
  bundle_price: number
  cleaning_fee: number
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

export interface ProductCreate {
  category_id?: number
  sku: string
  name: string
  description?: string
  short_description?: string
  stock_quantity?: number
  base_price: number
  featured?: boolean
  is_active?: boolean
}

export interface ProductUpdate {
  category_id?: number
  sku?: string
  name?: string
  description?: string
  short_description?: string
  stock_quantity?: number
  base_price?: number
  featured?: boolean
  is_active?: boolean
}

export interface BundleCreate {
  name: string
  slug?: string
  description?: string
  short_description?: string
  bundle_price: number
  cleaning_fee?: number
  featured?: boolean
  display_order?: number
  is_active?: boolean
  items: BundleItemCreate[]
}

export interface BundleUpdate {
  name?: string
  slug?: string
  description?: string
  short_description?: string
  bundle_price?: number
  cleaning_fee?: number
  featured?: boolean
  display_order?: number
  is_active?: boolean
}

export interface BundleItemCreate {
  product_id: number
  quantity: number
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
