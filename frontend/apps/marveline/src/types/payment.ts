export interface Payment {
  id: number
  invoice_id: number
  amount_cents: number
  payment_method: 'cash' | 'card' | 'transfer' | 'check'
  payment_date: string
  notes?: string
  created_at: string
}

export interface PaymentCreate {
  amount_cents: number
  payment_method: 'cash' | 'card' | 'transfer' | 'check'
  payment_date: string
  notes?: string
}
