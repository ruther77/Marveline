export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled'

export type PaymentMethod = 'cash' | 'card' | 'transfer' | 'check'

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
}

export interface InvoiceUpdateRequest {
  issue_date?: string
  due_date?: string
  status?: InvoiceStatus
}
