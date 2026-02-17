import apiClient from './client'
import type { LoginRequest, LoginResponse, User, MFAVerifyRequest, MFASetupResponse } from '@/types'

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const formData = new URLSearchParams()
    formData.append('username', data.email)
    formData.append('password', data.password)
    const response = await apiClient.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    return response.data
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout')
  },

  logoutAll: async (): Promise<void> => {
    await apiClient.delete('/sessions')
  },

  me: async (): Promise<User> => {
    const response = await apiClient.get('/auth/me')
    return response.data
  },

  refresh: async (refreshToken: string): Promise<LoginResponse> => {
    const response = await apiClient.post('/auth/refresh', { refresh_token: refreshToken })
    return response.data
  },

  forgotPassword: async (email: string): Promise<void> => {
    await apiClient.post('/auth/forgot-password', { email })
  },

  resetPassword: async (token: string, password: string): Promise<void> => {
    await apiClient.post('/auth/reset-password', { token, password })
  },

  // MFA
  mfaSetup: async (): Promise<MFASetupResponse> => {
    const response = await apiClient.post('/mfa/setup')
    return response.data
  },

  mfaEnable: async (code: string): Promise<{ enabled: boolean; message: string }> => {
    const response = await apiClient.post('/mfa/verify-setup', { totp_code: code })
    return response.data
  },

  mfaDisable: async (code: string): Promise<void> => {
    await apiClient.delete('/mfa')
  },

  mfaVerify: async (data: MFAVerifyRequest): Promise<LoginResponse> => {
    const response = await apiClient.post('/mfa/verify', {
      mfa_session_token: data.mfa_session_token,
      totp_code: data.code,
    })
    return response.data
  },

  mfaStatus: async (): Promise<{ enabled: boolean; recovery_codes_remaining: number }> => {
    const response = await apiClient.get('/mfa/status')
    return {
      enabled: response.data.mfa_enabled,
      recovery_codes_remaining: response.data.recovery_codes_remaining,
    }
  },

  regenerateBackupCodes: async (code: string): Promise<{ backup_codes: string[] }> => {
    const response = await apiClient.post('/mfa/backup-codes/regenerate', { totp_code: code })
    return response.data
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await apiClient.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },

  getCsrfToken: async (): Promise<{ csrf_token: string; expires_in: number }> => {
    const response = await apiClient.get('/auth/csrf')
    return response.data
  },
}
