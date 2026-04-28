import type { CustomerList } from './customer'
import type { Product } from './product'

export type ReservationStatus =
  | 'draft' | 'confirmed'
  | 'confirmed_risk' | 'pre_check' | 'delivered'
  | 'extended' | 'returned' | 'returned_dispute' | 'completed' | 'cancelled'

/**
 * Phase URL-bookmarkable dérivée d'un ReservationStatus + état des dépôts/signature.
 * Utilisée pour router dans /reservations/$id/$phase et pour PHASE_MATRIX.
 */
export type ReservationPhase =
  | 'brouillon'
  | 'brouillon-incomplet'
  | 'confirmee'
  | 'prete'
  | 'risque'
  | 'precheck'
  | 'legal'
  | 'en-cours'
  | 'prolongee'
  | 'retournee'
  | 'litige'
  | 'terminee'
  | 'annulee'

/**
 * Clé d'une section de rendu sur ReservationView.
 * L'ordre et la présence des sections pour chaque phase est défini par PhaseMatrix.
 */
export type SectionKey =
  | 'hero'
  | 'status-alert'
  | 'info-grid'
  | 'field-timeline'
  | 'product-lines'
  | 'deposit'
  | 'pre-check'
  | 'risks'
  | 'invoice'
  | 'assign'
  | 'quick-links'
  | 'extend'
  | 'countdown'
  | 'legal-docs'
  | 'dispute-log'

export type PhaseMatrix = Record<ReservationPhase, SectionKey[]>

export interface ReservationLineVariant {
  id: number
  product_id: number
  label: string
  color?: string
  size?: string
  gamme?: string
  sku: string
  price_per_day?: number
}

export interface BundleItemNested {
  id: number
  bundle_id: number
  product_id: number
  variant_id?: number | null
  quantity: number
  display_order: number
  product: Product
}

export interface BundleNested {
  id: number
  name: string
  slug?: string
  image_url?: string | null
  short_description?: string | null
  bundle_price_cents: number
  items: BundleItemNested[]
  total_items: number
}

export interface ReservationLine {
  id: number
  reservation_id: number
  product_id?: number
  bundle_id?: number
  variant_id?: number
  quantity: number
  unit_price_cents: number
  subtotal_cents: number
  product?: Product
  bundle?: BundleNested
  variant?: ReservationLineVariant
}

export interface ReservationList {
  id: number
  tenant_id: number
  customer_id: number
  assigned_user_id?: number | null
  customer_name?: string
  reference: string
  event_date: string
  delivery_date: string
  return_date: string
  event_location?: string
  status: ReservationStatus
  total_amount_cents: number
  deposit_amount_cents: number
  deposit_paid: boolean
  event_type?: 'mariage' | 'anniversaire' | 'entreprise' | 'autre'
  event_name?: string
  guest_count?: number
  notes?: string
  created_at: string
  updated_at: string
  is_active: boolean
  is_archived: boolean
  // Livraison
  delivery_method?: 'self' | 'carrier' | 'pickup' | null
  delivery_fee_cents?: number
  // Payment tracking
  payment_status?: 'none' | 'unpaid' | 'partial' | 'paid'
  invoice_status?: string | null
  paid_amount_cents?: number
}

export interface ReservationDetail extends ReservationList {
  customer?: CustomerList
  lines: ReservationLine[]
  rental_days: number
  signature_url?: string | null
  devis_id?: number
  advance_payment_amount_cents?: number | null
  advance_payment_amount_euros?: number | null
  balance_due_date?: string | null
  advance_paid_at?: string | null
  // Logistique
  total_weight_grams?: number | null
  total_volume_cm3?: number | null
  total_weight_kg?: number | null
  total_volume_liters?: number | null
  delivery_zone_id?: number | null
  delivery_fee_euros?: number
  delivery_instructions?: string | null
  carrier_name?: string | null
  carrier_code?: string | null
  delivery_address?: string | null
  delivery_city?: string | null
  delivery_postal_code?: string | null
  // Payment tracking (detail)
  invoice_number?: string | null
  remaining_amount_cents?: number
}

export interface ReservationLineCreate {
  product_id?: number
  bundle_id?: number
  quantity: number
  variant_id?: number
}

export interface ReservationCreate {
  customer_id: number
  event_date: string
  delivery_date: string
  return_date: string
  event_location?: string
  event_type?: 'mariage' | 'anniversaire' | 'entreprise' | 'autre'
  event_name?: string
  guest_count?: number
  deposit_amount_cents?: number
  notes?: string
  lines: { product_id?: number; bundle_id?: number; quantity: number; variant_id?: number }[]
  // Livraison
  delivery_zone_id?: number | null
  delivery_method?: 'self' | 'carrier' | 'pickup' | null
  delivery_fee_cents?: number
  delivery_instructions?: string | null
  carrier_name?: string | null
  carrier_code?: string | null
  // Adresse structurée
  delivery_address?: string | null
  delivery_city?: string | null
  delivery_postal_code?: string | null
}

export interface ReservationUpdate {
  event_date?: string
  delivery_date?: string
  return_date?: string
  event_location?: string
  deposit_paid?: boolean
  event_type?: 'mariage' | 'anniversaire' | 'entreprise' | 'autre'
  event_name?: string
  guest_count?: number
  notes?: string | null
  // Livraison
  delivery_zone_id?: number | null
  delivery_method?: 'self' | 'carrier' | 'pickup' | null
  delivery_fee_cents?: number
  delivery_instructions?: string | null
  carrier_name?: string | null
  carrier_code?: string | null
  // Adresse structurée
  delivery_address?: string | null
  delivery_city?: string | null
  delivery_postal_code?: string | null
}

import type { PaginatedResponse } from './index'
export type PaginatedReservations = PaginatedResponse<ReservationList>

export interface ReservationRisk {
  id: number
  tenant_id: number
  reservation_id: number
  type: string
  severity: 'low' | 'medium' | 'high'
  description: string
  blocking: boolean
  resolved_at?: string | null
  created_at?: string | null
}

export interface ReservationRiskCreate {
  type: string
  severity: 'low' | 'medium' | 'high'
  description: string
  blocking?: boolean
}

export interface ReservationRiskUpdate {
  resolved_at?: string | null
}

export interface PreCheckItem {
  id: number
  tenant_id: number
  reservation_id: number
  label: string
  type: string
  checked: boolean
  checked_at?: string | null
  checked_by?: number | null
  sort_order: number
}

export interface PreCheckItemCreate {
  label: string
  type: string
  sort_order?: number
}

export interface ReservationExtension {
  id: number
  tenant_id: number
  reservation_id: number
  original_return_date: string
  new_return_date: string
  reason: string
  extra_charge_cents: number
}

export interface ExtendReservationRequest {
  new_return_date: string
  reason: string
  extra_charge_cents?: number
}

export interface ReservationAmendRequest {
  reason: string
  event_date?: string | null
  delivery_date?: string | null
  return_date?: string | null
  add_lines?: ReservationLineCreate[] | null
  remove_line_ids?: number[] | null
}

export interface ReturnInspectionItemCreate {
  reservation_line_id?: number | null
  label: string
  quantity_expected?: number
  quantity_returned?: number
  quantity_damaged?: number
  quantity_missing?: number
  condition: 'good' | 'damaged' | 'missing' | 'partial'
  damage_description?: string | null
  photo_url?: string | null
  charge_cents?: number
}

export interface ReturnInspectionBulkCreate {
  items: ReturnInspectionItemCreate[]
}

export interface ReturnInspectionItem {
  id: number
  tenant_id: number
  reservation_id: number
  reservation_line_id?: number | null
  label: string
  quantity_expected: number
  quantity_returned: number
  quantity_damaged: number
  quantity_missing: number
  condition: 'good' | 'damaged' | 'missing' | 'partial'
  damage_description?: string | null
  photo_url?: string | null
  charge_cents: number
  inspected_by?: number | null
  inspected_at?: string | null
  created_at?: string | null
}

export type DisputeAction = 'opened' | 'note_added' | 'charge_applied' | 'resolved'

export interface DisputeLogCreate {
  action: DisputeAction
  description: string
  charge_cents?: number
}

export interface DisputeLog {
  id: number
  tenant_id: number
  reservation_id: number
  action: DisputeAction
  description: string
  charge_cents: number
  created_by?: number | null
  created_at: string
}

export interface ReservationDetailFull extends ReservationDetail {
  status: ReservationStatus
  risks: ReservationRisk[]
  pre_check_items: PreCheckItem[]
  extensions: ReservationExtension[]
  signature_url?: string
  devis_id?: number
}
