import apiClient from './client'
import type { User, UserCreate, UserUpdate, Session, AuditLog, PaginatedResponse } from '@/types'

export const adminApi = {
  // Users — Backend utilise skip/limit, retourne { items: [...], total, skip, limit }
  getUsers: async (page = 1, perPage = 20): Promise<{ items: User[]; total: number; page: number; pages: number }> => {
    const skip = (page - 1) * perPage
    const response = await apiClient.get('/users', {
      params: { skip, limit: perPage },
    })
    const data = response.data
    const items = Array.isArray(data.items) ? data.items : (Array.isArray(data.users) ? data.users : [])
    const total = data.total || 0
    const pages = Math.ceil(total / perPage)
    return { items, total, page, pages }
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
    const data = response.data
    return Array.isArray(data.sessions) ? data.sessions : (Array.isArray(data.items) ? data.items : [])
  },

  terminateSession: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/sessions/${sessionId}`)
  },

  terminateAllSessions: async (): Promise<void> => {
    await apiClient.delete('/sessions')
  },

  // Audit Logs
  getAuditLogs: async (
    page = 1,
    perPage = 50,
    filters?: { user_id?: number; action?: string; from_date?: string; to_date?: string }
  ): Promise<PaginatedResponse<AuditLog>> => {
    const skip = (page - 1) * perPage
    const params: Record<string, unknown> = { skip, limit: perPage }
    if (filters?.user_id) params.user_id = filters.user_id
    if (filters?.action) params.action = filters.action
    if (filters?.from_date) params.start_date = filters.from_date
    if (filters?.to_date) params.end_date = filters.to_date
    const response = await apiClient.get('/audit', { params })
    const data = response.data
    const total = data.total || 0
    const pages = Math.ceil(total / perPage)
    const items = Array.isArray(data.logs) ? data.logs : (Array.isArray(data.items) ? data.items : [])
    return { items, total, page, per_page: perPage, pages }
  },
}
