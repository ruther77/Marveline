import { api, fetchFormData } from './fetchClient'
import type { LoginRequest, LoginResponse, User, MFAVerifyRequest, MFASetupResponse, AccountInfo, LoginV2Request } from '@/types'

export interface OAuthProvider {
  provider: string
  name: string
  icon: string
  color: string
  enabled: boolean
}

export const authApi = {
  login: async (data: LoginRequest, captchaToken?: string): Promise<LoginResponse> => {
    const extraHeaders: Record<string, string> = {}
    if (captchaToken) extraHeaders['X-Captcha-Token'] = captchaToken
    return fetchFormData<LoginResponse>(
      '/auth/login',
      { username: data.email, password: data.password },
      extraHeaders,
    )
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout')
  },

  logoutAll: async (): Promise<void> => {
    await api.delete('/sessions')
  },

  logoutDevice: async (deviceId: string): Promise<{ status: string; device_id: string; sessions_revoked: number }> => {
    return api.post<{ status: string; device_id: string; sessions_revoked: number }>(`/auth/logout/device/${encodeURIComponent(deviceId)}`)
  },

  me: async (): Promise<User> => {
    return api.get<User>('/auth/me')
  },

  refresh: async (_refreshToken?: string): Promise<LoginResponse> => {
    return api.post<LoginResponse>('/auth/refresh')
  },

  forgotPassword: async (email: string): Promise<void> => {
    await api.post('/auth/forgot-password', { email })
  },

  resetPassword: async (token: string, password: string): Promise<void> => {
    await api.post('/auth/reset-password', { token, new_password: password })
  },

  // MFA
  mfaSetup: async (): Promise<MFASetupResponse> => {
    return api.post<MFASetupResponse>('/mfa/setup')
  },

  mfaEnable: async (code: string): Promise<{ enabled: boolean; message: string }> => {
    return api.post<{ enabled: boolean; message: string }>('/mfa/verify-setup', { totp_code: code })
  },

  mfaDisable: async (_code: string): Promise<void> => {
    await api.delete('/mfa')
  },

  mfaVerify: async (data: MFAVerifyRequest): Promise<LoginResponse> => {
    return api.post<LoginResponse>('/mfa/verify', {
      mfa_session_token: data.mfa_session_token,
      totp_code: data.code,
    })
  },

  mfaStatus: async (): Promise<{ enabled: boolean; recovery_codes_remaining: number }> => {
    const data = await api.get<{ mfa_enabled: boolean; recovery_codes_remaining: number }>('/mfa/status')
    return {
      enabled: data.mfa_enabled,
      recovery_codes_remaining: data.recovery_codes_remaining,
    }
  },

  regenerateBackupCodes: async (code: string): Promise<{ backup_codes: string[] }> => {
    return api.post<{ backup_codes: string[] }>('/mfa/backup-codes/regenerate', { totp_code: code })
  },

  stepUpVerify: async (code: string): Promise<{ status: string; valid_for_seconds: number }> => {
    return api.post<{ status: string; valid_for_seconds: number }>('/mfa/stepup/verify', { totp_code: code })
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },

  getCsrfToken: async (): Promise<{ csrf_token: string; expires_in: number }> => {
    return api.get<{ csrf_token: string; expires_in: number }>('/auth/csrf')
  },

  // OAuth v1 (legacy)
  oauthProviders: async (): Promise<{ providers: OAuthProvider[] }> => {
    return api.get<{ providers: OAuthProvider[] }>('/oauth/providers')
  },

  oauthAuthorize: async (provider: string): Promise<{ auth_url: string }> => {
    return api.get<{ auth_url: string }>(`/oauth/${provider}/authorize`)
  },

  oauthCallback: async (provider: string, code: string, state: string): Promise<LoginResponse> => {
    return api.post<LoginResponse>(`/oauth/${provider}/callback`, { code, state })
  },
}

/** Client IAM v2 — JSON body, Account global + TenantMembership. */
export const authV2Api = {
  login: async (data: LoginV2Request, captchaToken?: string): Promise<LoginResponse> => {
    const extraHeaders: Record<string, string> = {}
    if (captchaToken) extraHeaders['X-Captcha-Token'] = captchaToken
    return api.post<LoginResponse>(
      '/auth/v2/login',
      { email: data.email, password: data.password, tenant_id: data.tenant_id },
      { headers: extraHeaders },
    )
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/v2/logout')
  },

  refresh: async (): Promise<LoginResponse> => {
    return api.post<LoginResponse>('/auth/v2/refresh')
  },

  me: async (): Promise<AccountInfo> => {
    return api.get<AccountInfo>('/auth/v2/me')
  },

  oauthAuthorize: async (provider: string, tenantId: number): Promise<{ auth_url: string }> => {
    const params = new URLSearchParams({ tenant_id: String(tenantId) })
    return api.get<{ auth_url: string }>(`/auth/v2/oauth/${provider}/authorize?${params}`)
  },

  oauthCallback: async (provider: string, code: string, state: string): Promise<LoginResponse> => {
    return api.post<LoginResponse>(`/auth/v2/oauth/${provider}/callback`, { code, state })
  },

  forgotPassword: async (email: string): Promise<void> => {
    await api.post('/auth/v2/forgot-password', { email })
  },

  resetPassword: async (token: string, password: string): Promise<void> => {
    await api.post('/auth/v2/reset-password', { token, new_password: password })
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await api.post('/auth/v2/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },
}
