export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled'

export type PaymentMethod = 'cash' | 'card' | 'transfer' | 'check'

export interface InvoiceCharge {
  id: number
  invoice_id: number
  charge_type: 'DAMAGE' | 'LABOR'
  amount_cents: number
  description: string
  hours?: number
  day_type?: 'weekday' | 'weekend' | 'night'
  damage_type_id?: number
  created_at: string
}

export interface InvoiceChargeCreate {
  charge_type: 'DAMAGE' | 'LABOR'
  amount_cents?: number
  hours?: number
  day_type?: 'weekday' | 'weekend' | 'night'
  description: string
}

export interface InvoiceListItem {
  id: number
  tenant_id: number
  reservation_id: number
  invoice_number: string
  issue_date: string
  due_date: string
  status: InvoiceStatus
  total_amount_cents: number
  paid_amount_cents: number
  total_amount_euros: number
  paid_amount_euros: number
  is_paid: boolean
  is_overdue: boolean
  customer_name?: string
  advance_rate: number
  advance_due_date?: string
  sent_at?: string | null
  opened_at?: string | null
  first_reminder_sent_at?: string | null
  last_reminder_sent_at?: string | null
  created_at: string
  updated_at: string
}

export interface ReservationSummary {
  id: number
  reference: string
  status: string
  event_date: string
  customer_name?: string
}

export interface InvoiceDetail extends InvoiceListItem {
  payment_method: PaymentMethod | null
  payment_date: string | null
  reservation: ReservationSummary | null
  remaining_amount_cents: number
  remaining_amount_euros: number
  payment_completion_percentage: number
  charges: InvoiceCharge[]
  tva_rate?: number | null
  tva_amount_cents?: number | null
  tva_amount_euros?: number | null
  total_ttc_cents?: number | null
  total_ttc_euros?: number | null
  tva_breakdown?: TvaBreakdownItem[] | null
  // Timeline audit
  sent_at?: string | null
  opened_at?: string | null
  first_reminder_sent_at?: string | null
  last_reminder_sent_at?: string | null
  cancelled_at?: string | null
}

export interface TvaBreakdownItem {
  rate: number
  base_ht_cents: number
  tva_cents: number
  ttc_cents: number
  base_ht_euros: number
  tva_euros: number
  ttc_euros: number
}

export interface TvaReportResponse {
  month: string
  invoice_count: number
  total_base_ht_cents: number
  total_tva_cents: number
  total_ttc_cents: number
  total_base_ht_euros: number
  total_tva_euros: number
  total_ttc_euros: number
  breakdown_by_rate: TvaBreakdownItem[]
}

export interface AddPaymentRequest {
  amount_cents: number
  payment_method: PaymentMethod
  payment_date: string
}

export interface InvoiceCreateRequest {
  reservation_id: number
  issue_date: string
  due_date: string
  invoice_type?: 'full' | 'advance' | 'balance'
}

export interface InvoiceUpdateRequest {
  issue_date?: string
  due_date?: string
  status?: InvoiceStatus
  total_amount_cents?: number
}

export type InvoiceType = 'invoice' | 'credit_note' | 'damage_invoice'

export interface CreditNote {
  id: number
  original_invoice_id: number
  invoice_number: string
  amount_cents: number
  reason: string
  issue_date: string
  status: 'draft' | 'issued' | 'applied' | 'refunded'
}

export interface InvoiceAuditEntry {
  id: number
  invoice_id: number
  action: string
  user: string
  detail?: string
  created_at: string
}

export interface InvoiceDetailFull extends InvoiceDetail {
  invoice_type: InvoiceType
  tva_rate: number
  subtotal_cents: number
  tva_cents: number
  credit_notes: CreditNote[]
  audit_trail: InvoiceAuditEntry[]
  sent_at?: string
  reminder_count: number
}
