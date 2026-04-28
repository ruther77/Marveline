import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { authApi, authV2Api } from '../auth'
import type { AccountInfo, LoginRequest, MFAVerifyRequest, User } from '@/types'
import { BRAND } from '@/brand/select'

const TENANT_ID = Number(import.meta.env.VITE_TENANT_ID || BRAND.defaultTenantId)

/** Map AccountInfo (IAM v2) vers User (compat) pour que authStore/composants restent inchanges. */
function mapAccountInfoToUser(info: AccountInfo): User {
  return {
    id: info.account_id,
    email: info.email,
    full_name: `${info.first_name} ${info.last_name}`.trim(),
    role: info.role_name,
    tenant_id: info.tenant_id,
    is_active: info.is_active,
    permissions: info.scopes,
    created_at: null,
    password_change_required: info.password_change_required,
    first_name: info.first_name,
    last_name: info.last_name,
  }
}

export async function fetchAuthMe(): Promise<User> {
  const info = await authV2Api.me()
  return mapAccountInfoToUser(info)
}

export async function fetchAuthCsrfToken() {
  return authApi.getCsrfToken()
}

// ── MFA hooks (restent sur authApi — pas d'equivalent v2) ──────────────────

export function useMfaStatus() {
  return useQuery({
    queryKey: queryKeys.mfa.status(),
    queryFn: () => authApi.mfaStatus(),
  })
}

export function useMfaSetup() {
  return useMutation({
    mutationFn: () => authApi.mfaSetup(),
  })
}

export function useMfaEnable() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => authApi.mfaEnable(code),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.mfa.status() }) },
  })
}

export function useMfaDisable() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => authApi.mfaDisable(code),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.mfa.status() }) },
  })
}

export function useMfaVerify() {
  return useMutation({
    mutationFn: (payload: MFAVerifyRequest) => authApi.mfaVerify(payload),
  })
}

// ── Auth hooks (IAM v2) ────────────────────────────────────────────────────

export function useLogin() {
  return useMutation({
    mutationFn: ({ credentials, captchaToken }: { credentials: LoginRequest; captchaToken?: string }) =>
      authV2Api.login({ email: credentials.email, password: credentials.password, tenant_id: TENANT_ID }, captchaToken),
  })
}

export function useAuthMe(enabled = true) {
  return useQuery({
    queryKey: queryKeys.auth.me(),
    queryFn: fetchAuthMe,
    enabled,
    staleTime: 60 * 1000,
  })
}

export function useAuthRefresh() {
  return useMutation({
    mutationFn: () => authV2Api.refresh(),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => authV2Api.logout(),
    onSettled: () => {
      qc.removeQueries({ queryKey: queryKeys.auth.me() })
      qc.removeQueries({ queryKey: queryKeys.users.me() })
    },
  })
}

export function useLogoutAllSessions() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => authApi.logoutAll(),
    onSettled: () => {
      qc.removeQueries({ queryKey: queryKeys.auth.me() })
      qc.removeQueries({ queryKey: queryKeys.users.me() })
    },
  })
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: (email: string) => authV2Api.forgotPassword(email),
  })
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ token, password }: { token: string; password: string }) =>
      authV2Api.resetPassword(token, password),
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ currentPassword, newPassword }: { currentPassword: string; newPassword: string }) =>
      authV2Api.changePassword(currentPassword, newPassword),
  })
}

// ── MFA backup / step-up (restent sur authApi) ─────────────────────────────

export function useRegenerateBackupCodes() {
  return useMutation({
    mutationFn: (code: string) => authApi.regenerateBackupCodes(code),
  })
}

export function useStepUpVerify() {
  return useMutation({
    mutationFn: (code: string) => authApi.stepUpVerify(code),
  })
}

// ── CSRF / OAuth (restent sur authApi — pas d'equivalent v2) ───────────────

export function useCsrfToken() {
  return useQuery({
    queryKey: queryKeys.auth.csrf(),
    queryFn: () => authApi.getCsrfToken(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useOAuthProviders(enabled = true) {
  return useQuery({
    queryKey: queryKeys.auth.oauthProviders(),
    queryFn: () => authApi.oauthProviders(),
    enabled,
    staleTime: 5 * 60 * 1000,
  })
}

export function useOAuthAuthorize() {
  return useMutation({
    mutationFn: (provider: string) => authApi.oauthAuthorize(provider),
  })
}

export function useOAuthCallback() {
  return useMutation({
    mutationFn: ({ provider, code, state }: { provider: string; code: string; state: string }) =>
      authApi.oauthCallback(provider, code, state),
  })
}
