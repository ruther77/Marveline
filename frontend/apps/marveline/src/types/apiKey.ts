export interface ApiKey {
  id: number
  name: string
  key_prefix: string
  scopes: string[]
  rate_limit: number | null
  expires_at: string | null
  is_active: boolean
  last_used_at: string | null
  last_used_ip: string | null
  usage_count: number
  created_by: number
  created_at: string
  updated_at: string
}

export interface ApiKeyList {
  id: number
  name: string
  key_prefix: string
  scopes: string[]
  is_active: boolean
  last_used_at: string | null
  usage_count: number
  created_at: string
}

export interface ApiKeyCreated extends ApiKey {
  full_key: string
}

export interface ApiKeyCreate {
  name: string
  scopes: string[]
  rate_limit?: number | null
  expires_at?: string | null
}

export interface ApiKeyUpdate {
  name?: string
  scopes?: string[]
  rate_limit?: number | null
  is_active?: boolean
}
