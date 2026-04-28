export interface Collection {
  id: number
  tenant_id: number
  name: string
  description: string | null
  is_active: boolean
}

export interface CollectionWithProducts extends Collection {
  products: { id: number; name: string; reference?: string }[]
}

export interface CollectionCreate {
  name: string
  description?: string
  is_active?: boolean
}

export interface CollectionUpdate {
  name?: string
  description?: string
  is_active?: boolean
}

export interface CollectionListResponse {
  items: Collection[]
  total: number
}
