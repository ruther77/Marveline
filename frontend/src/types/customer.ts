export type CustomerType = 'individual' | 'company'

export interface CustomerList {
  id: number
  customer_type: CustomerType
  email: string
  phone?: string
  first_name?: string
  last_name?: string
  company_name?: string
  city?: string
  country: string
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
}

export interface PaginatedCustomers {
  items: CustomerList[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
