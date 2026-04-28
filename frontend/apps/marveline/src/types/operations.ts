// Types UI pour les opérations terrain
// Note : les réponses backend utilisent DepartureState/ReturnState (voir api/operations.ts)

export type ItemCondition = 'new' | 'good' | 'fair' | 'damaged' | 'missing'

export type DamageCategory = 'scratch' | 'break' | 'missing' | 'malfunction' | 'other'

export type DamageSeverity = 'minor' | 'moderate' | 'major' | 'total_loss'

export interface DepartureCheckItem {
  line_id: number
  product_id: number
  product_name: string
  quantity_expected: number
  image_url?: string | null
  sku?: string | null
  bundle_id?: number | null
  bundle_name?: string | null
  is_bundle_item: boolean
  // Champs état local UI — initialisés par la page, non retournés par le backend
  quantity_loaded?: number
  condition?: ItemCondition
  qr_scanned?: boolean
  scanned_codes?: string[]
  note?: string
  photo_urls?: string[]
}

export interface DamageDeclaration {
  product_id: number
  product_name: string
  category: DamageCategory
  severity: DamageSeverity
  description: string
  photo_urls: string[]
  estimated_cost_cents?: number
  /** true if already persisted in DB via standalone declaration (POST /return/{id}/damage) */
  persisted?: boolean
}

export interface ReturnCheckItem {
  line_id: number
  product_id: number
  product_name?: string
  quantity_expected: number
  image_url?: string | null
  sku?: string | null
  bundle_id?: number | null
  bundle_name?: string | null
  is_bundle_item: boolean
  // Champs état local UI — initialisés par la page, non retournés par le backend
  quantity_returned?: number
  condition?: ItemCondition
  damages?: DamageDeclaration[]
}

// Types correspondant aux réponses backend réelles
export interface DepartureState {
  reservation_id: number
  reference: string
  status: string
  total_items: number
  checked_items: number
  can_depart: boolean
  departure_blocked_reason?: string  // "pre_check_incomplete" | "deposit_required" | undefined
  customer_name?: string
  items: DepartureCheckItem[]
}

export interface ReturnState {
  reservation_id: number
  reference: string
  status: string
  delivery_date: string | null
  return_date: string | null
  can_return: boolean
  customer_name?: string
  items: ReturnCheckItem[]
  balance_due_cents?: number
}

export interface DamageReportResponse {
  reservation_id: number
  damage_type_id: number
  damage_type_name: string
  description: string
  fee_cents: number
}

export interface QrResult {
  product_id: number
  product_name: string
  stock_item_id: number
  serial_number: string | null
  stock_status: string
}

export interface PhotoUploadResponse {
  url: string
  filename: string
}

// Payload types pour les mutations
export interface DepartureBlockPayload {
  reason: string
}

export interface ReturnDamagePayload {
  description: string
  damage_type_name: string
  fee_cents?: number
  stock_item_id?: number
  // Champs UI supplémentaires (non envoyés au backend)
  product_id?: number
  severity?: DamageSeverity
  estimated_cost_cents?: number
  photo_urls?: string[]
}

// Types enrichis pour les pages UI (stockés localement dans le store Zustand)
// items provient maintenant du backend (DepartureState/ReturnState)
export interface DepartureInventory extends DepartureState {
  all_scanned?: boolean
  ready_to_depart?: boolean
}

export interface ReturnInventory extends ReturnState {
  has_damages?: boolean
  total_damage_cost_cents?: number
}
