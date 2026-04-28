import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '../keys'
import { adminApi } from '../../admin'
import type { UserCreate, UserUpdate, UserInviteRequest } from '@/types'

export function useUsers(params?: { skip?: number; limit?: number }, enabled = true) {
  return useQuery({
    queryKey: queryKeys.admin.users(params),
    queryFn: () => adminApi.listUsers(params),
    enabled,
    staleTime: 10 * 60 * 1000,
  })
}

export function useUserDetail(id: number | null) {
  return useQuery({
    queryKey: ['admin', 'users', 'detail', id],
    queryFn: () => adminApi.getUser(id!),
    enabled: id !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: UserCreate) => adminApi.createUser(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.admin.users() }) },
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UserUpdate }) => adminApi.updateUser(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.admin.users() }) },
  })
}

export function useDeleteUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => adminApi.deleteUser(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.admin.users() }) },
  })
}

export function useInviteUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: UserInviteRequest) => adminApi.inviteUser(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.admin.users() }) },
  })
}

export function useUnlockUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => adminApi.unlockUser(id),
    onSuccess: (_data, userId) => {
      qc.invalidateQueries({ queryKey: queryKeys.admin.users() })
      qc.invalidateQueries({ queryKey: ['admin', 'user', userId] })
      qc.invalidateQueries({ queryKey: ['admin', 'audit-logs'] })
    },
  })
}
