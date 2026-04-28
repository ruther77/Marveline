import { api } from './fetchClient'
import type { User, UserCreate, UserUpdate, UserInviteRequest, UserInviteResponse, Session, AuditLog, PaginatedResponse } from '@/types'

function buildAuditQuery(params?: {
  skip?: number
  limit?: number
  user_id?: number
  action?: string
  from_date?: string
  to_date?: string
  entity_type?: string
  entity_id?: number
}) {
  const p: Record<string, string> = {
    skip: String(params?.skip ?? 0),
    limit: String(params?.limit ?? 50),
  }
  if (params?.user_id) p.user_id = String(params.user_id)
  if (params?.action) p.action = params.action
  if (params?.from_date) p.start_date = params.from_date
  if (params?.to_date) p.end_date = params.to_date
  if (params?.entity_type) p.entity_type = params.entity_type
  if (params?.entity_id) p.entity_id = String(params.entity_id)
  return new URLSearchParams(p).toString()
}

export const adminApi = {
  listUsers: async (params?: { skip?: number; limit?: number }): Promise<PaginatedResponse<User>> => {
    const qs = new URLSearchParams({
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }).toString()
    return api.get<PaginatedResponse<User>>(`/users?${qs}`)
  },

  getUser: async (id: number): Promise<User> => {
    return api.get<User>(`/users/${id}`)
  },

  createUser: async (data: UserCreate): Promise<User> => {
    return api.post<User>('/users', data)
  },

  updateUser: async (id: number, data: UserUpdate): Promise<User> => {
    return api.patch<User>(`/users/${id}`, data)
  },

  deleteUser: async (id: number): Promise<void> => {
    await api.delete(`/users/${id}`)
  },

  unlockUser: async (id: number): Promise<{ status: string; user_id: number }> => {
    return api.post<{ status: string; user_id: number }>(`/users/${id}/unlock`)
  },

  inviteUser: async (data: UserInviteRequest): Promise<UserInviteResponse> => {
    return api.post<UserInviteResponse>('/users/invite', data)
  },

  // Sessions self-service
  getSessions: async (): Promise<{ sessions: Session[]; total: number; active_count: number }> => {
    return api.get<{ sessions: Session[]; total: number; active_count: number }>('/sessions')
  },

  getUserSessions: async (): Promise<Session[]> => {
    const data = await api.get<{ sessions?: Session[]; items?: Session[] }>('/sessions')
    return Array.isArray(data.sessions) ? data.sessions : (Array.isArray(data.items) ? data.items : [])
  },

  terminateSession: async (sessionId: string): Promise<void> => {
    await api.delete(`/sessions/${sessionId}`)
  },

  terminateAllSessions: async (): Promise<void> => {
    await api.delete('/sessions')
  },

  // Sessions admin tenant-level
  getAdminTenantSessions: async (tenantId: number): Promise<{ sessions: Session[]; total: number; active_count: number }> => {
    return api.get<{ sessions: Session[]; total: number; active_count: number }>(`/admin/tenants/${tenantId}/sessions`)
  },

  revokeAdminTenantSession: async (tenantId: number, sessionId: string): Promise<void> => {
    await api.delete(`/admin/tenants/${tenantId}/sessions/${sessionId}`)
  },

  listAuditLogs: async (params?: {
    skip?: number
    limit?: number
    user_id?: number
    action?: string
    from_date?: string
    to_date?: string
    entity_type?: string
    entity_id?: number
  }): Promise<PaginatedResponse<AuditLog>> => {
    const qs = buildAuditQuery(params)
    return api.get<PaginatedResponse<AuditLog>>(`/audit?${qs}`)
  },

  listAuditLogsByUser: async (
    userId: number,
    params?: { skip?: number; limit?: number; action?: string; from_date?: string; to_date?: string }
  ): Promise<PaginatedResponse<AuditLog>> => {
    const qs = buildAuditQuery(params)
    return api.get<PaginatedResponse<AuditLog>>(`/audit/user/${userId}?${qs}`)
  },

  listAuditLogsByEntity: async (
    entityType: string,
    entityId: number,
    params?: { skip?: number; limit?: number; action?: string; from_date?: string; to_date?: string }
  ): Promise<PaginatedResponse<AuditLog>> => {
    const encoded = encodeURIComponent(entityType)
    const qs = buildAuditQuery(params)
    return api.get<PaginatedResponse<AuditLog>>(`/audit/entity/${encoded}/${entityId}?${qs}`)
  },
}
