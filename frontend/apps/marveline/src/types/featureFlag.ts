export interface FeatureFlag {
  id: number
  name: string
  description: string | null
  is_enabled: boolean
  target_tenants: number[] | null
  rollout_pct: number
  metadata_json: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface FeatureFlagList {
  id: number
  name: string
  description: string | null
  is_enabled: boolean
  target_tenants: number[] | null
  rollout_pct: number
  created_at: string
}

export interface FeatureFlagCreate {
  name: string
  description?: string
  is_enabled?: boolean
  target_tenants?: number[] | null
  rollout_pct?: number
  metadata_json?: Record<string, unknown> | null
}

export interface FeatureFlagUpdate {
  description?: string
  is_enabled?: boolean
  target_tenants?: number[] | null
  rollout_pct?: number
  metadata_json?: Record<string, unknown> | null
}

export interface FeatureFlagEvaluated {
  name: string
  enabled: boolean
  reason: string
}
