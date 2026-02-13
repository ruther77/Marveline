import apiClient from './client'
import type { User, UserCreate, UserUpdate, Session, AuditLog, PaginatedResponse } from '@/types'

export const adminApi = {
  // Users
  getUsers: async (page = 1, perPage = 20): Promise<{ items: User[]; total: number; page: number; pages: number }> => {
    const response = await apiClient.get('/users', {
      params: { page, per_page: perPage },
    })
    // Transform API response to match expected format
    const data = response.data
    const total = data.total || 0
    const pages = Math.ceil(total / perPage)
    return { items: data.users || [], total, page, pages }
  },

  getUser: async (id: number): Promise<User> => {
    const response = await apiClient.get(`/users/${id}`)
    return response.data
  },

  createUser: async (data: UserCreate): Promise<User> => {
    const response = await apiClient.post('/users', data)
    return response.data
  },

  updateUser: async (id: number, data: UserUpdate): Promise<User> => {
    const response = await apiClient.put(`/users/${id}`, data)
    return response.data
  },

  deleteUser: async (id: number): Promise<void> => {
    await apiClient.delete(`/users/${id}`)
  },

  // Sessions
  getSessions: async (): Promise<{ sessions: Session[]; total: number; active_count: number }> => {
    const response = await apiClient.get('/sessions')
    return response.data
  },

  getUserSessions: async (): Promise<Session[]> => {
    const response = await apiClient.get('/sessions')
    return response.data.sessions
  },

  terminateSession: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/sessions/${sessionId}`)
  },

  terminateAllSessions: async (): Promise<void> => {
    await apiClient.delete('/sessions')
  },

  // Audit Logs - TODO: Implement when backend endpoint is available
  getAuditLogs: async (
    page = 1,
    perPage = 50,
    _filters?: { user_id?: number; action?: string; from_date?: string; to_date?: string }
  ): Promise<PaginatedResponse<AuditLog>> => {
    // Backend audit logs endpoint not yet exposed, return empty
    return { items: [], total: 0, page, per_page: perPage, pages: 0 }
  },
}
