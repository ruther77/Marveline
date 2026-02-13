import apiClient from './client'
import type { LoginRequest, LoginResponse, RegisterRequest, User, MFAVerifyRequest, MFASetupResponse } from '@/types'

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post('/auth/login', data)
    return response.data
  },

  register: async (data: RegisterRequest): Promise<User> => {
    const response = await apiClient.post('/auth/register', data)
    return response.data
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout')
  },

  logoutAll: async (): Promise<void> => {
    await apiClient.post('/auth/logout-all')
  },

  me: async (): Promise<User> => {
    const response = await apiClient.get('/users/me')
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

  mfaEnable: async (code: string): Promise<{ backup_codes: string[] }> => {
    const response = await apiClient.post('/mfa/enable', { code })
    return response.data
  },

  mfaDisable: async (code: string): Promise<void> => {
    await apiClient.post('/mfa/disable', { code })
  },

  mfaVerify: async (data: MFAVerifyRequest): Promise<LoginResponse> => {
    const response = await apiClient.post('/auth/login/mfa', {
      mfa_session_token: data.mfa_session_token,
      totp_code: data.code,
    })
    return response.data
  },

  mfaStatus: async (): Promise<{ enabled: boolean; backup_codes_remaining: number }> => {
    const response = await apiClient.get('/mfa/status')
    return response.data
  },

  regenerateBackupCodes: async (code: string): Promise<{ backup_codes: string[] }> => {
    const response = await apiClient.post('/mfa/backup-codes/regenerate', { code })
    return response.data
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await apiClient.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },
}
