export type DevisStatus =
  | 'draft' | 'sent' | 'negotiation' | 'accepted' | 'refused'
  | 'expired' | 'converted' | 'cancelled' | 'version_pending'
// ⚠️ 'sent' (pas 'submitted'), 'converted' (pas 'archived')

export type DevisModuleType = 'socle' | 'stock' | 'facturation' | 'securite' | 'services'

export interface DevisLigne {
  id: number
  product_id?: number
  bundle_id?: number
  variant_id?: number
  label: string
  quantity: number
  unit_price_cents: number
  subtotal_cents: number
  variant_label?: string
  weight_grams?: number | null
  volume_cm3?: number | null
}

export interface DevisListItem {
  id: number
  reference: string
  customer_id: number
  customer_name: string
  status: DevisStatus
  event_date: string
  total_cents: number
  valid_until: string
  created_at: string
}

export type DevisDeliveryMethod = 'self' | 'carrier' | 'pickup'

export interface DevisDetail extends DevisListItem {
  event_location?: string
  notes?: string
  lines: DevisLigne[]
  caution_required?: boolean
  caution_amount_cents?: number
  delivery_date?: string
  return_date?: string
  converted_reservation_id?: number | null
  converted_reservation_reference?: string | null
  // Livraison
  delivery_method?: DevisDeliveryMethod | null
  delivery_fee_cents?: number
  carrier_name?: string | null
  carrier_code?: string | null
  delivery_address?: string | null
  delivery_city?: string | null
  delivery_postal_code?: string | null
  delivery_zone_id?: number | null
  delivery_instructions?: string | null
}

export interface DevisConvertPayload {
  event_date: string
  delivery_date: string
  return_date: string
  event_location: string
  // Livraison (override du devis si fourni)
  delivery_method?: DevisDeliveryMethod | null
  delivery_fee_cents?: number
  carrier_name?: string | null
  carrier_code?: string | null
  delivery_address?: string | null
  delivery_city?: string | null
  delivery_postal_code?: string | null
  delivery_zone_id?: number | null
  delivery_instructions?: string | null
}

export interface DevisCreate {
  customer_id: number
  event_date: string
  valid_until: string
  event_location?: string
  notes?: string
  conditions_paiement?: string
  message_accompagnement?: string
  lines: { product_id?: number; bundle_id?: number; variant_id?: number; label: string; quantity: number; unit_price_cents: number }[]
  // Livraison
  delivery_method?: DevisDeliveryMethod | null
  delivery_fee_cents?: number
  carrier_name?: string | null
  carrier_code?: string | null
  delivery_address?: string | null
  delivery_city?: string | null
  delivery_postal_code?: string | null
  delivery_zone_id?: number | null
  delivery_instructions?: string | null
  // Options
  tva_rate?: number
  discount_pct?: number
  caution_required?: boolean
  caution_amount_cents?: number
  delivery_date?: string
  return_date?: string
}

export type DeliveryStatus = 'a_cadrer' | 'en_cours' | 'livre'

export interface DevisModule {
  id: number
  devis_id: number
  module_type: DevisModuleType
  label: string
  content_json: Record<string, unknown>
  delivery_status: DeliveryStatus
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DevisCoverageItem {
  id: number
  devis_id: number
  tenant_id: number
  title: string
  description?: string
  status: DeliveryStatus
  sort_order: number
  created_at: string
  updated_at: string
}

export interface DevisCoverageItemCreate {
  title: string
  description?: string
  status?: DeliveryStatus
  sort_order?: number
}

export interface DevisCoverageItemUpdate {
  title?: string
  description?: string
  status?: DeliveryStatus
  sort_order?: number
}

export interface DevisCoverageSummary {
  devis_id: number
  reference: string
  status: DevisStatus
  total_modules: number
  active_modules: number
  module_types: string[]
  total_phases: number
  phases_past: number
  phases_current: number
  phases_future: number
  phase_completion_pct: number
  total_lines: number
  subtotal_cents: number
}

export interface DevisPhase {
  id: number
  devis_id: number
  label: string
  date_start: string
  date_end: string
  lines: DevisLigne[]
}

export interface DevisModuleCreate {
  module_type: DevisModuleType
  label: string
  content_json?: Record<string, unknown>
}

export interface DevisModuleUpdate {
  label?: string
  content_json?: Record<string, unknown>
  delivery_status?: DeliveryStatus
}

export interface DevisPhaseCreate {
  label: string
  date_start: string
  date_end: string
}

export interface DevisPhaseUpdate {
  label?: string
  date_start?: string
  date_end?: string
}

export interface DevisVersion {
  id: number
  devis_id: number
  version_number: number
  snapshot_json: Record<string, unknown>
  created_at: string
  created_by: number
  created_by_name?: string | null
}

export interface DevisNegotiationEntry {
  id: number
  devis_id: number
  author: string
  message: string
  proposed_amount_cents?: number
  created_at: string
}

export interface DevisChangeRequest {
  id: number
  devis_id: number
  author: string
  description: string
  status: 'pending' | 'accepted' | 'refused'
  created_at: string
}

export interface DevisDetailFull extends DevisDetail {
  status: DevisStatus
  modules: DevisModule[]
  phases: DevisPhase[]
  versions: DevisVersion[]
  negotiations: DevisNegotiationEntry[]
  caution_required: boolean
  caution_amount_cents?: number
  change_requests: DevisChangeRequest[]
  tva_rate: number
  subtotal_cents: number
  tva_cents: number
  total_cents: number
  discount_pct?: number
  signature_url?: string
  signed_at?: string
  total_weight_grams?: number
  total_volume_cm3?: number
  total_weight_kg?: number
  total_volume_liters?: number
  conditions_paiement?: string
  message_accompagnement?: string
}

// ── G31 — Bundle preview ─────────────────────────────────────────────────────

export interface BundleItemPreview {
  product_id: number
  product_name: string
  product_image_url?: string | null
  variant_id?: number
  variant_label?: string
  quantity: number
  display_order: number
}

export interface BundlePreviewResponse {
  bundle_id: number
  bundle_name: string
  bundle_image_url?: string | null
  bundle_price_cents: number
  items: BundleItemPreview[]
}

// ── G28 — Historique lignes ──────────────────────────────────────────────────

export interface DevisLineHistoryEntry {
  id: number
  devis_id: number
  devis_line_id?: number
  action: 'create' | 'update' | 'delete'
  old_values?: Record<string, unknown>
  new_values?: Record<string, unknown>
  changed_by?: number
  created_at: string
}

// ── G7 — Pieces jointes ─────────────────────────────────────────────────────

export interface DevisAttachment {
  id: number
  devis_id: number
  filename: string
  mime_type: string
  file_size: number
  uploaded_by?: number
  sort_order: number
  created_at: string
}
