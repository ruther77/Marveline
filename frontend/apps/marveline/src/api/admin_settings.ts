import { api } from './fetchClient'

export interface TenantSettings {
  company_name: string | null
  company_email: string | null
  company_phone: string | null
  company_address: string | null
  origin_postal_code: string | null
  vat_rate: number
  hourly_rate_weekday: number
  hourly_rate_weekend: number
  deposit_rate: number
  default_currency: string
}

export interface TenantSettingsUpdate {
  company_name?: string | null
  company_email?: string | null
  company_phone?: string | null
  company_address?: string | null
  origin_postal_code?: string | null
  vat_rate?: number
  hourly_rate_weekday?: number
  hourly_rate_weekend?: number
  deposit_rate?: number
  default_currency?: string
}

export const adminSettingsApi = {
  get: (): Promise<TenantSettings> =>
    api.get<TenantSettings>('/admin/settings'),

  update: (data: TenantSettingsUpdate): Promise<TenantSettings> =>
    api.patch<TenantSettings>('/admin/settings', data),
}
