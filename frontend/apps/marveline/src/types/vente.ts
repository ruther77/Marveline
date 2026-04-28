export type VenteStatus = 'draft' | 'pending' | 'deposit_paid' | 'fully_paid' | 'overdue' | 'refunded' | 'cancelled'

export interface VenteLigne {
  id: number
  product_name: string
  quantity: number
  unit_price_cents: number
  subtotal_cents: number
}

export interface VenteListItem {
  id: number
  reference: string
  customer_id: number
  customer_name?: string | null
  status: VenteStatus
  created_at: string
  total_cents: number
  paid_cents: number
  balance_cents: number
}

export interface VentePayment {
  id: number
  vente_id: number
  amount_cents: number
  payment_method: string
  payment_date: string
  is_deposit: boolean
  notes?: string
}

export interface VenteDetail extends VenteListItem {
  notes?: string
  lines: VenteLigne[]
  payments: VentePayment[]
}

export interface VenteDetailFull extends VenteDetail {
  subtotal_cents: number
  tva_cents: number
  total_cents: number
  paid_cents: number
  remaining_cents: number
  deposit_pct?: number
  payment_due_date?: string
  invoice_id?: number
  reservation_id?: number
  overdue_days?: number
}
