/**
 * Tests unitaires pour api/auth.ts
 * Vérifie toutes les fonctions d'authentification et MFA
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { authApi } from '../auth'
import apiClient from '../client'
import type { LoginRequest, LoginResponse, User, MFAVerifyRequest, MFASetupResponse } from '@/types'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('API Auth - login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envoie les credentials en form-urlencoded et retourne les tokens', async () => {
    const mockResponse: LoginResponse = {
      access_token: 'access-token-123',
      refresh_token: 'refresh-token-456',
      token_type: 'bearer',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const loginData: LoginRequest = { email: 'user@test.com', password: 'password123' }
    const result = await authApi.login(loginData)

    expect(apiClient.post).toHaveBeenCalledWith(
      '/auth/login',
      expect.any(URLSearchParams),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    )
    expect(result).toEqual(mockResponse)
  })

  it('convertit email → username dans le form data', async () => {
    const mockResponse: LoginResponse = {
      access_token: 'token',
      refresh_token: 'refresh',
      token_type: 'bearer',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const loginData: LoginRequest = { email: 'admin@example.com', password: 'secret' }
    await authApi.login(loginData)

    const formData = vi.mocked(apiClient.post).mock.calls[0][1] as URLSearchParams
    expect(formData.get('username')).toBe('admin@example.com')
    expect(formData.get('password')).toBe('secret')
  })

  it('propage les erreurs 401 (credentials invalides)', async () => {
    const error = new Error('Invalid credentials')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    const loginData: LoginRequest = { email: 'wrong@test.com', password: 'wrong' }

    await expect(authApi.login(loginData)).rejects.toThrow('Invalid credentials')
  })

  it('propage les erreurs 422 (validation)', async () => {
    const error = new Error('Validation error')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    const loginData: LoginRequest = { email: 'invalid-email', password: '123' }

    await expect(authApi.login(loginData)).rejects.toThrow('Validation error')
  })
})

describe('API Auth - logout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('appelle POST /auth/logout et ne retourne rien', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({})

    await authApi.logout()

    expect(apiClient.post).toHaveBeenCalledWith('/auth/logout')
  })

  it('propage les erreurs 401 (non authentifié)', async () => {
    const error = new Error('Unauthorized')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    await expect(authApi.logout()).rejects.toThrow('Unauthorized')
  })
})

describe('API Auth - logoutAll', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('appelle DELETE /sessions pour révoquer toutes les sessions', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await authApi.logoutAll()

    expect(apiClient.delete).toHaveBeenCalledWith('/sessions')
  })
})

describe('API Auth - me', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère les infos utilisateur courant', async () => {
    const mockUser: User = {
      id: 1,
      email: 'user@test.com',
      tenant_id: 1,
      role: 'admin',
      is_active: true,
      mfa_enabled: false,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockUser })

    const result = await authApi.me()

    expect(apiClient.get).toHaveBeenCalledWith('/auth/me')
    expect(result).toEqual(mockUser)
  })

  it('propage les erreurs 401 si non authentifié', async () => {
    const error = new Error('Unauthorized')
    vi.mocked(apiClient.get).mockRejectedValue(error)

    await expect(authApi.me()).rejects.toThrow('Unauthorized')
  })
})

describe('API Auth - refresh', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envoie le refresh_token et retourne de nouveaux tokens', async () => {
    const mockResponse: LoginResponse = {
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
      token_type: 'bearer',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await authApi.refresh('old-refresh-token')

    expect(apiClient.post).toHaveBeenCalledWith('/auth/refresh', { refresh_token: 'old-refresh-token' })
    expect(result).toEqual(mockResponse)
  })

  it('propage les erreurs 401 si refresh_token invalide', async () => {
    const error = new Error('Invalid refresh token')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    await expect(authApi.refresh('invalid-token')).rejects.toThrow('Invalid refresh token')
  })
})

describe('API Auth - forgotPassword', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envoie email pour reset password', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({})

    await authApi.forgotPassword('user@test.com')

    expect(apiClient.post).toHaveBeenCalledWith('/auth/forgot-password', { email: 'user@test.com' })
  })

  it('propage les erreurs 404 si email non trouvé', async () => {
    const error = new Error('Email not found')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    await expect(authApi.forgotPassword('unknown@test.com')).rejects.toThrow('Email not found')
  })
})

describe('API Auth - resetPassword', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envoie token + nouveau password pour réinitialiser', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({})

    await authApi.resetPassword('reset-token-123', 'NewPassword123!')

    expect(apiClient.post).toHaveBeenCalledWith('/auth/reset-password', {
      token: 'reset-token-123',
      password: 'NewPassword123!',
    })
  })

  it('propage les erreurs 400 si token invalide ou expiré', async () => {
    const error = new Error('Invalid or expired token')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    await expect(authApi.resetPassword('bad-token', 'password')).rejects.toThrow('Invalid or expired token')
  })
})

describe('API Auth - MFA Setup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('génère un QR code et secret pour MFA setup', async () => {
    const mockSetup: MFASetupResponse = {
      secret: 'JBSWY3DPEHPK3PXP',
      qr_code: 'data:image/png;base64,iVBORw0KGgo...',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockSetup })

    const result = await authApi.mfaSetup()

    expect(apiClient.post).toHaveBeenCalledWith('/mfa/setup')
    expect(result).toEqual(mockSetup)
  })
})

describe('API Auth - MFA Enable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('vérifie le code TOTP et retourne backup codes', async () => {
    const mockResponse = {
      backup_codes: ['code1', 'code2', 'code3'],
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await authApi.mfaEnable('123456')

    expect(apiClient.post).toHaveBeenCalledWith('/mfa/verify-setup', { totp_code: '123456' })
    expect(result.backup_codes).toHaveLength(3)
  })

  it('propage les erreurs 400 si code TOTP invalide', async () => {
    const error = new Error('Invalid TOTP code')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    await expect(authApi.mfaEnable('000000')).rejects.toThrow('Invalid TOTP code')
  })
})

describe('API Auth - MFA Disable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('désactive MFA avec code TOTP de confirmation', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await authApi.mfaDisable('654321')

    expect(apiClient.delete).toHaveBeenCalledWith('/mfa')
  })

  it('propage les erreurs 400 si code invalide', async () => {
    const error = new Error('Invalid code')
    vi.mocked(apiClient.delete).mockRejectedValue(error)

    await expect(authApi.mfaDisable('wrong')).rejects.toThrow('Invalid code')
  })
})

describe('API Auth - MFA Verify', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('vérifie code TOTP avec mfa_session_token et retourne tokens finaux', async () => {
    const mockResponse: LoginResponse = {
      access_token: 'final-access-token',
      refresh_token: 'final-refresh-token',
      token_type: 'bearer',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const mfaData: MFAVerifyRequest = {
      mfa_session_token: 'mfa-session-123',
      code: '123456',
    }
    const result = await authApi.mfaVerify(mfaData)

    expect(apiClient.post).toHaveBeenCalledWith('/mfa/verify', {
      mfa_session_token: 'mfa-session-123',
      totp_code: '123456',
    })
    expect(result).toEqual(mockResponse)
  })

  it('propage les erreurs 401 si code TOTP incorrect', async () => {
    const error = new Error('Invalid TOTP code')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    const mfaData: MFAVerifyRequest = {
      mfa_session_token: 'mfa-session-123',
      code: '000000',
    }

    await expect(authApi.mfaVerify(mfaData)).rejects.toThrow('Invalid TOTP code')
  })
})

describe('API Auth - MFA Status', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère le statut MFA et nombre de codes recovery restants', async () => {
    const mockResponse = {
      mfa_enabled: true,
      recovery_codes_remaining: 5,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await authApi.mfaStatus()

    expect(apiClient.get).toHaveBeenCalledWith('/mfa/status')
    expect(result).toEqual({
      enabled: true,
      recovery_codes_remaining: 5,
    })
  })
})

describe('API Auth - Regenerate Backup Codes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('regénère les backup codes avec code TOTP de confirmation', async () => {
    const mockResponse = {
      backup_codes: ['new1', 'new2', 'new3', 'new4', 'new5'],
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await authApi.regenerateBackupCodes('123456')

    expect(apiClient.post).toHaveBeenCalledWith('/mfa/backup-codes/regenerate', { totp_code: '123456' })
    expect(result.backup_codes).toHaveLength(5)
  })

  it('propage les erreurs 400 si code TOTP invalide', async () => {
    const error = new Error('Invalid code')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    await expect(authApi.regenerateBackupCodes('wrong')).rejects.toThrow('Invalid code')
  })
})

describe('API Auth - Change Password', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('change le password avec ancien + nouveau', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({})

    await authApi.changePassword('OldPassword123!', 'NewPassword456!')

    expect(apiClient.post).toHaveBeenCalledWith('/auth/change-password', {
      current_password: 'OldPassword123!',
      new_password: 'NewPassword456!',
    })
  })

  it('propage les erreurs 401 si ancien password incorrect', async () => {
    const error = new Error('Current password is incorrect')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    await expect(authApi.changePassword('wrong', 'new')).rejects.toThrow('Current password is incorrect')
  })

  it('propage les erreurs 422 si nouveau password faible', async () => {
    const error = new Error('Password too weak')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    await expect(authApi.changePassword('old', '123')).rejects.toThrow('Password too weak')
  })
})

describe('API Auth - CSRF Token', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère un token CSRF avec expires_in', async () => {
    const mockResponse = {
      csrf_token: 'csrf-token-abc123',
      expires_in: 3600,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await authApi.getCsrfToken()

    expect(apiClient.get).toHaveBeenCalledWith('/auth/csrf')
    expect(result).toEqual(mockResponse)
    expect(result.expires_in).toBe(3600)
  })
})
