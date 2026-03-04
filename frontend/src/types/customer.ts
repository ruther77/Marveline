export type CustomerType = 'individual' | 'company' | 'professional' | 'association'

export interface CustomerList {
  id: number
  customer_type: CustomerType
  email: string
  phone?: string
  first_name?: string
  last_name?: string
  company_name?: string
  address?: string
  city?: string
  postal_code?: string
  country: string
  notes?: string
  display_name: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CustomerResponse extends CustomerList {
  tenant_id: number
  address?: string
  postal_code?: string
}

export interface CustomerCreate {
  customer_type: CustomerType
  email: string
  phone?: string
  first_name?: string
  last_name?: string
  company_name?: string
  address?: string
  city?: string
  postal_code?: string
  country?: string
  notes?: string
}

export interface CustomerUpdate {
  customer_type?: CustomerType
  email?: string
  phone?: string
  first_name?: string
  last_name?: string
  company_name?: string
  address?: string
  city?: string
  postal_code?: string
  country?: string
  notes?: string
}

export interface PaginatedCustomers {
  items: CustomerList[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface CustomerHistoryReservation {
  id: number
  reference: string
  event_date: string
  status: string
  total_amount: number
}

export interface CustomerHistoryInvoice {
  id: number
  invoice_number: string
  status: string
  total_amount: number
  paid_amount: number
}

export interface CustomerHistoryStats {
  total_reservations: number
  total_revenue_cents: number
  last_event_date: string | null
}

export interface CustomerHistory {
  customer: CustomerResponse
  reservations: CustomerHistoryReservation[]
  invoices: CustomerHistoryInvoice[]
  stats: CustomerHistoryStats
}


export type RFMSegment = 'Champions' | 'Loyal' | 'Potential' | 'At Risk' | 'Lost' | 'New'

export interface CustomerRFM {
  customer_id: number
  customer_name: string
  recency_days: number
  frequency: number
  monetary_cents: number
  segment: RFMSegment
}

export interface CustomerRFMResponse {
  items: CustomerRFM[]
  total: number
}
