import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '../../admin'
import { authApi } from '../../auth'

const SESSION_KEY = ['admin', 'sessions'] as const

export function useUserSessions() {
  return useQuery({
    queryKey: SESSION_KEY,
    queryFn: () => adminApi.getUserSessions(),
    staleTime: 30 * 1000,
  })
}

export function useAdminSessions() {
  return useQuery({
    queryKey: ['admin', 'sessions', 'full'],
    queryFn: () => adminApi.getSessions(),
    staleTime: 30 * 1000,
  })
}

export function useTerminateSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) => adminApi.terminateSession(sessionId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: SESSION_KEY }) },
  })
}

export function useTerminateAllSessions() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => adminApi.terminateAllSessions(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: SESSION_KEY }) },
  })
}

export function useLogoutDevice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (deviceId: string) => authApi.logoutDevice(deviceId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: SESSION_KEY }) },
  })
}

export function useAdminTenantSessions(tenantId: number) {
  return useQuery({
    queryKey: ['admin', 'tenant-sessions', tenantId],
    queryFn: () => adminApi.getAdminTenantSessions(tenantId),
    enabled: tenantId > 0,
    staleTime: 30 * 1000,
  })
}

export function useRevokeAdminTenantSession(tenantId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) => adminApi.revokeAdminTenantSession(tenantId, sessionId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'tenant-sessions', tenantId] }) },
  })
}
