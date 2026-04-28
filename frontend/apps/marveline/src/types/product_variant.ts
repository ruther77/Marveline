// ProductVariant types — aligned with backend ProductVariantResponse (multi-dimensions)

export type ProductColor =
  | 'blanc'
  | 'ivoire'
  | 'bordeaux'
  | 'noir'
  | 'rouge'
  | 'vert_amande'
  | 'vert_sapin'
  | 'taupe'

export const PRODUCT_COLORS: { value: ProductColor; label: string }[] = [
  { value: 'blanc', label: 'Blanc' },
  { value: 'ivoire', label: 'Ivoire' },
  { value: 'bordeaux', label: 'Bordeaux' },
  { value: 'noir', label: 'Noir' },
  { value: 'rouge', label: 'Rouge' },
  { value: 'vert_amande', label: 'Vert amande' },
  { value: 'vert_sapin', label: 'Vert sapin' },
  { value: 'taupe', label: 'Taupe' },
]

export type ProductGamme =
  | 'classique'
  | 'elegance'
  | 'open_up'
  | 'prestige'
  | 'vintage'
  | 'bois'

export const PRODUCT_GAMMES: { value: ProductGamme; label: string }[] = [
  { value: 'classique', label: 'Classique' },
  { value: 'elegance', label: 'Élégance' },
  { value: 'open_up', label: "Open'Up" },
  { value: 'prestige', label: 'Prestige' },
  { value: 'vintage', label: 'Vintage' },
  { value: 'bois', label: 'Bois' },
]

export interface ProductVariant {
  id: number
  tenant_id: number
  product_id: number
  color?: string        // nullable — dimension optionnelle
  size?: string         // nullable — taille/format (ex: 21cm, 240cm)
  gamme?: string        // nullable — gamme/finition (ex: classique, elegance)
  label: string         // requis — clé d'unicité par produit, affiché partout
  price_per_day?: number // override prix parent en centimes (null = hérite parent)
  image_url?: string | null // override image (null = hérite parent)
  sku: string
  stock_quantity: number
  available_quantity: number
  weight_grams?: number | null
  volume_cm3?: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ProductVariantCreate {
  color?: ProductColor  // optionnel
  size?: string         // optionnel
  gamme?: string        // optionnel
  label: string         // requis
  price_per_day?: number
  image_url?: string | null
  sku: string
  stock_quantity?: number
  available_quantity?: number
  weight_grams?: number | null
  volume_cm3?: number | null
}

export interface ProductVariantUpdate {
  color?: ProductColor
  size?: string
  gamme?: string
  label?: string
  price_per_day?: number
  image_url?: string | null
  stock_quantity?: number
  available_quantity?: number
  weight_grams?: number | null
  volume_cm3?: number | null
  is_active?: boolean
}
