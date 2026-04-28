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

import type { PaginatedResponse } from './index'
export type PaginatedCustomers = PaginatedResponse<CustomerList>

export interface CustomerHistoryReservation {
  id: number
  reference: string
  event_date: string
  status: string
  total_amount_cents: number
}

export interface CustomerHistoryInvoice {
  id: number
  invoice_number: string
  status: string
  total_amount_cents: number
  paid_amount_cents: number
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

export interface CustomerImportRowError {
  row: number
  field?: string | null
  message: string
}

export interface CustomerImportReport {
  created: number
  skipped: number
  errors: CustomerImportRowError[]
}
