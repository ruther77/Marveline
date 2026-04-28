/**
 * Tests unitaires pour api/auth.ts
 * Vérifie toutes les fonctions d'authentification et MFA
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { authApi, authV2Api } from '../auth'
import { api, fetchFormData } from '../fetchClient'
import type { LoginRequest, LoginResponse, User, MFAVerifyRequest, MFASetupResponse, AccountInfo, LoginV2Request } from '@/types'

// Mock fetchClient
vi.mock('../fetchClient', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  fetchBlob: vi.fn(),
  fetchFormData: vi.fn(),
}))

describe('API Auth - login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envoie les credentials via fetchFormData et retourne les tokens', async () => {
    const mockResponse: LoginResponse = {
      access_token: 'access-token-123',
      refresh_token: 'refresh-token-456',
      token_type: 'bearer',
    }
    vi.mocked(fetchFormData).mockResolvedValue(mockResponse)

    const loginData: LoginRequest = { email: 'user@test.com', password: 'password123' }
    const result = await authApi.login(loginData)

    expect(fetchFormData).toHaveBeenCalledWith('/auth/login', {
      username: 'user@test.com',
      password: 'password123',
    }, {})
    expect(result).toEqual(mockResponse)
  })

  it('convertit email → username dans fetchFormData', async () => {
    const mockResponse: LoginResponse = {
      access_token: 'token',
      refresh_token: 'refresh',
      token_type: 'bearer',
    }
    vi.mocked(fetchFormData).mockResolvedValue(mockResponse)

    const loginData: LoginRequest = { email: 'admin@example.com', password: 'secret' }
    await authApi.login(loginData)

    expect(fetchFormData).toHaveBeenCalledWith('/auth/login', {
      username: 'admin@example.com',
      password: 'secret',
    }, {})
  })

  it('propage les erreurs 401 (credentials invalides)', async () => {
    const error = new Error('Invalid credentials')
    vi.mocked(fetchFormData).mockRejectedValue(error)

    const loginData: LoginRequest = { email: 'wrong@test.com', password: 'wrong' }

    await expect(authApi.login(loginData)).rejects.toThrow('Invalid credentials')
  })

  it('propage les erreurs 422 (validation)', async () => {
    const error = new Error('Validation error')
    vi.mocked(fetchFormData).mockRejectedValue(error)

    const loginData: LoginRequest = { email: 'invalid-email', password: '123' }

    await expect(authApi.login(loginData)).rejects.toThrow('Validation error')
  })
})

describe('API Auth - logout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('appelle POST /auth/logout et ne retourne rien', async () => {
    vi.mocked(api.post).mockResolvedValue(undefined)

    await authApi.logout()

    expect(api.post).toHaveBeenCalledWith('/auth/logout')
  })

  it('propage les erreurs 401 (non authentifié)', async () => {
    const error = new Error('Unauthorized')
    vi.mocked(api.post).mockRejectedValue(error)

    await expect(authApi.logout()).rejects.toThrow('Unauthorized')
  })
})

describe('API Auth - logoutAll', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('appelle DELETE /sessions pour révoquer toutes les sessions', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await authApi.logoutAll()

    expect(api.delete).toHaveBeenCalledWith('/sessions')
  })
})

describe('API Auth - logoutDevice', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('appelle POST /auth/logout/device/{device_id}', async () => {
    vi.mocked(api.post).mockResolvedValue({
      status: 'logged_out',
      device_id: 'device-123',
      sessions_revoked: 2,
    })

    const result = await authApi.logoutDevice('device-123')

    expect(api.post).toHaveBeenCalledWith('/auth/logout/device/device-123')
    expect(result.status).toBe('logged_out')
    expect(result.sessions_revoked).toBe(2)
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
    vi.mocked(api.get).mockResolvedValue(mockUser)

    const result = await authApi.me()

    expect(api.get).toHaveBeenCalledWith('/auth/me')
    expect(result).toEqual(mockUser)
  })

  it('propage les erreurs 401 si non authentifié', async () => {
    const error = new Error('Unauthorized')
    vi.mocked(api.get).mockRejectedValue(error)

    await expect(authApi.me()).rejects.toThrow('Unauthorized')
  })
})

describe('API Auth - refresh', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('appelle POST /auth/refresh et retourne de nouveaux tokens', async () => {
    const mockResponse: LoginResponse = {
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
      token_type: 'bearer',
    }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const result = await authApi.refresh('old-refresh-token')

    expect(api.post).toHaveBeenCalledWith('/auth/refresh')
    expect(result).toEqual(mockResponse)
  })

  it('propage les erreurs 401 si refresh_token invalide', async () => {
    const error = new Error('Invalid refresh token')
    vi.mocked(api.post).mockRejectedValue(error)

    await expect(authApi.refresh('invalid-token')).rejects.toThrow('Invalid refresh token')
  })
})

describe('API Auth - forgotPassword', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envoie email pour reset password', async () => {
    vi.mocked(api.post).mockResolvedValue(undefined)

    await authApi.forgotPassword('user@test.com')

    expect(api.post).toHaveBeenCalledWith('/auth/forgot-password', { email: 'user@test.com' })
  })

  it('propage les erreurs 404 si email non trouvé', async () => {
    const error = new Error('Email not found')
    vi.mocked(api.post).mockRejectedValue(error)

    await expect(authApi.forgotPassword('unknown@test.com')).rejects.toThrow('Email not found')
  })
})

describe('API Auth - resetPassword', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('envoie token + nouveau password pour réinitialiser', async () => {
    vi.mocked(api.post).mockResolvedValue(undefined)

    await authApi.resetPassword('reset-token-123', 'NewPassword123!')

    expect(api.post).toHaveBeenCalledWith('/auth/reset-password', {
      token: 'reset-token-123',
      new_password: 'NewPassword123!',
    })
  })

  it('propage les erreurs 400 si token invalide ou expiré', async () => {
    const error = new Error('Invalid or expired token')
    vi.mocked(api.post).mockRejectedValue(error)

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
      provisioning_uri: 'otpauth://totp/Marveline:user%40test.com?secret=JBSWY3DPEHPK3PXP&issuer=Marveline',
      recovery_codes: ['aaa111', 'bbb222', 'ccc333', 'ddd444', 'eee555', 'fff666', 'ggg777', 'hhh888'],
    }
    vi.mocked(api.post).mockResolvedValue(mockSetup)

    const result = await authApi.mfaSetup()

    expect(api.post).toHaveBeenCalledWith('/mfa/setup')
    expect(result).toEqual(mockSetup)
  })
})

describe('API Auth - MFA Enable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('vérifie le code TOTP et retourne confirmation activation', async () => {
    const mockResponse = {
      enabled: true,
      message: 'MFA enabled successfully',
    }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const result = await authApi.mfaEnable('123456')

    expect(api.post).toHaveBeenCalledWith('/mfa/verify-setup', { totp_code: '123456' })
    expect(result.enabled).toBe(true)
    expect(result.message).toBe('MFA enabled successfully')
  })

  it('propage les erreurs 400 si code TOTP invalide', async () => {
    const error = new Error('Invalid TOTP code')
    vi.mocked(api.post).mockRejectedValue(error)

    await expect(authApi.mfaEnable('000000')).rejects.toThrow('Invalid TOTP code')
  })
})

describe('API Auth - MFA Disable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('désactive MFA', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await authApi.mfaDisable('654321')

    expect(api.delete).toHaveBeenCalledWith('/mfa')
  })

  it('propage les erreurs 400 si code invalide', async () => {
    const error = new Error('Invalid code')
    vi.mocked(api.delete).mockRejectedValue(error)

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
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const mfaData: MFAVerifyRequest = {
      mfa_session_token: 'mfa-session-123',
      code: '123456',
    }
    const result = await authApi.mfaVerify(mfaData)

    expect(api.post).toHaveBeenCalledWith('/mfa/verify', {
      mfa_session_token: 'mfa-session-123',
      totp_code: '123456',
    })
    expect(result).toEqual(mockResponse)
  })

  it('propage les erreurs 401 si code TOTP incorrect', async () => {
    const error = new Error('Invalid TOTP code')
    vi.mocked(api.post).mockRejectedValue(error)

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
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await authApi.mfaStatus()

    expect(api.get).toHaveBeenCalledWith('/mfa/status')
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
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const result = await authApi.regenerateBackupCodes('123456')

    expect(api.post).toHaveBeenCalledWith('/mfa/backup-codes/regenerate', { totp_code: '123456' })
    expect(result.backup_codes).toHaveLength(5)
  })

  it('propage les erreurs 400 si code TOTP invalide', async () => {
    const error = new Error('Invalid code')
    vi.mocked(api.post).mockRejectedValue(error)

    await expect(authApi.regenerateBackupCodes('wrong')).rejects.toThrow('Invalid code')
  })
})

describe('API Auth - Step Up Verify', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('valide un code MFA step-up', async () => {
    vi.mocked(api.post).mockResolvedValue({ status: 'verified', valid_for_seconds: 900 })

    const result = await authApi.stepUpVerify('123456')

    expect(api.post).toHaveBeenCalledWith('/mfa/stepup/verify', { totp_code: '123456' })
    expect(result.status).toBe('verified')
    expect(result.valid_for_seconds).toBe(900)
  })
})

describe('API Auth - Change Password', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('change le password avec ancien + nouveau', async () => {
    vi.mocked(api.post).mockResolvedValue(undefined)

    await authApi.changePassword('OldPassword123!', 'NewPassword456!')

    expect(api.post).toHaveBeenCalledWith('/auth/change-password', {
      current_password: 'OldPassword123!',
      new_password: 'NewPassword456!',
    })
  })

  it('propage les erreurs 401 si ancien password incorrect', async () => {
    const error = new Error('Current password is incorrect')
    vi.mocked(api.post).mockRejectedValue(error)

    await expect(authApi.changePassword('wrong', 'new')).rejects.toThrow('Current password is incorrect')
  })

  it('propage les erreurs 422 si nouveau password faible', async () => {
    const error = new Error('Password too weak')
    vi.mocked(api.post).mockRejectedValue(error)

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
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await authApi.getCsrfToken()

    expect(api.get).toHaveBeenCalledWith('/auth/csrf')
    expect(result).toEqual(mockResponse)
    expect(result.expires_in).toBe(3600)
  })
})

// ── IAM v2 tests ────────────────────────────────────────────────────────────

describe('authV2Api - login', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('envoie JSON avec tenant_id via api.post', async () => {
    const mockResponse: LoginResponse = {
      access_token: 'at-v2',
      token_type: 'bearer',
      expires_in: 900,
    }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const data: LoginV2Request = { email: 'user@example.com', password: 'Secret123!', tenant_id: 42 }
    const result = await authV2Api.login(data)

    expect(api.post).toHaveBeenCalledWith(
      '/auth/v2/login',
      { email: 'user@example.com', password: 'Secret123!', tenant_id: 42 },
      { headers: {} },
    )
    expect(result.access_token).toBe('at-v2')
  })

  it('ajoute X-Captcha-Token si captchaToken fourni', async () => {
    vi.mocked(api.post).mockResolvedValue({ access_token: 'at', token_type: 'bearer' })

    const data: LoginV2Request = { email: 'u@e.com', password: 'P', tenant_id: 1 }
    await authV2Api.login(data, 'captcha-abc')

    expect(api.post).toHaveBeenCalledWith(
      '/auth/v2/login',
      { email: 'u@e.com', password: 'P', tenant_id: 1 },
      { headers: { 'X-Captcha-Token': 'captcha-abc' } },
    )
  })

  it('retourne MFA token si mfa_required', async () => {
    const mfaResponse: LoginResponse = {
      access_token: '',
      token_type: 'mfa_session',
      mfa_required: true,
      mfa_session_token: 'mfa-tok-123',
    }
    vi.mocked(api.post).mockResolvedValue(mfaResponse)

    const data: LoginV2Request = { email: 'u@e.com', password: 'P', tenant_id: 1 }
    const result = await authV2Api.login(data)

    expect(result.mfa_required).toBe(true)
    expect(result.mfa_session_token).toBe('mfa-tok-123')
  })

  it('propage les erreurs 401 (credentials invalides)', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('Unauthorized'))
    await expect(authV2Api.login({ email: 'x', password: 'y', tenant_id: 1 })).rejects.toThrow('Unauthorized')
  })

  it('propage les erreurs 403 (membership révoqué)', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('Membership revoked'))
    await expect(authV2Api.login({ email: 'x', password: 'y', tenant_id: 1 })).rejects.toThrow('Membership revoked')
  })
})

describe('authV2Api - logout', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('appelle POST /auth/v2/logout', async () => {
    vi.mocked(api.post).mockResolvedValue(undefined)
    await authV2Api.logout()
    expect(api.post).toHaveBeenCalledWith('/auth/v2/logout')
  })
})

describe('authV2Api - refresh', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('appelle POST /auth/v2/refresh et retourne de nouveaux tokens', async () => {
    const mockResponse: LoginResponse = { access_token: 'new-at', token_type: 'bearer', expires_in: 900 }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const result = await authV2Api.refresh()

    expect(api.post).toHaveBeenCalledWith('/auth/v2/refresh')
    expect(result.access_token).toBe('new-at')
  })

  it('propage 401 si refresh cookie invalide', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('Invalid refresh token'))
    await expect(authV2Api.refresh()).rejects.toThrow('Invalid refresh token')
  })
})

describe('authV2Api - me', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('retourne AccountInfo depuis GET /auth/v2/me', async () => {
    const mockAccount: AccountInfo = {
      account_id: 7,
      email: 'user@example.com',
      first_name: 'Jean',
      last_name: 'Dupont',
      tenant_id: 3,
      membership_id: 12,
      role_name: 'staff',
      is_active: true,
      password_change_required: false,
      scopes: ['reservations:read', 'products:read'],
    }
    vi.mocked(api.get).mockResolvedValue(mockAccount)

    const result = await authV2Api.me()

    expect(api.get).toHaveBeenCalledWith('/auth/v2/me')
    expect(result.account_id).toBe(7)
    expect(result.membership_id).toBe(12)
    expect(result.role_name).toBe('staff')
    expect(result.scopes).toHaveLength(2)
  })

  it('propage 401 si access token expiré', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Session expirée.'))
    await expect(authV2Api.me()).rejects.toThrow('Session expirée.')
  })
})

describe('authV2Api - oauthAuthorize', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('appelle GET /auth/v2/oauth/{provider}/authorize?tenant_id=N', async () => {
    vi.mocked(api.get).mockResolvedValue({ auth_url: 'https://accounts.google.com/o/oauth2/v2/auth?...' })

    const result = await authV2Api.oauthAuthorize('google', 5)

    expect(api.get).toHaveBeenCalledWith('/auth/v2/oauth/google/authorize?tenant_id=5')
    expect(result.auth_url).toContain('accounts.google.com')
  })

  it('propage 404 si provider inconnu', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Unknown OAuth provider'))
    await expect(authV2Api.oauthAuthorize('twitter', 1)).rejects.toThrow('Unknown OAuth provider')
  })
})

describe('authV2Api - oauthCallback', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('envoie code + state et retourne TokenResponse', async () => {
    const mockResponse: LoginResponse = { access_token: 'oauth-at', token_type: 'bearer', expires_in: 900 }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const result = await authV2Api.oauthCallback('google', 'auth-code', 'state-abc')

    expect(api.post).toHaveBeenCalledWith(
      '/auth/v2/oauth/google/callback',
      { code: 'auth-code', state: 'state-abc' },
    )
    expect(result.access_token).toBe('oauth-at')
  })

  it('propage 400 si state invalide', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('OAuth state invalid'))
    await expect(authV2Api.oauthCallback('google', 'code', 'bad-state')).rejects.toThrow('OAuth state invalid')
  })

  it('propage 403 si pas de membership dans le tenant', async () => {
    vi.mocked(api.post).mockRejectedValue(new Error('No active membership'))
    await expect(authV2Api.oauthCallback('google', 'code', 'state')).rejects.toThrow('No active membership')
  })
})
