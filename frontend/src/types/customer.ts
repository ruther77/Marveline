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
}

export interface PaginatedCustomers {
  items: CustomerList[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
