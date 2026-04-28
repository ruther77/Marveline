import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '../keys'
import { adminApi } from '../../admin'

export function useAuditLogs(params?: { skip?: number; limit?: number; action?: string; from_date?: string; to_date?: string }) {
  return useQuery({
    queryKey: queryKeys.admin.auditLogs(params ?? {}),
    queryFn: () => adminApi.listAuditLogs({
      skip: params?.skip,
      limit: params?.limit,
      action: params?.action,
      from_date: params?.from_date,
      to_date: params?.to_date,
    }),
    staleTime: 30 * 1000,
  })
}

export function useUserAuditLogs(
  userId: number | null,
  params?: { skip?: number; limit?: number; action?: string; from_date?: string; to_date?: string }
) {
  return useQuery({
    queryKey: queryKeys.admin.auditUser(userId ?? 0, params ?? {}),
    queryFn: () => adminApi.listAuditLogsByUser(userId!, params),
    enabled: userId !== null,
    staleTime: 30 * 1000,
  })
}

export function useEntityAuditLogs(
  entityType: string,
  entityId: number | null,
  paramsOrLimit?: { skip?: number; limit?: number; action?: string; from_date?: string; to_date?: string } | number
) {
  const params =
    typeof paramsOrLimit === 'number'
      ? ({ limit: paramsOrLimit } as const)
      : (paramsOrLimit ?? {})

  return useQuery({
    queryKey: queryKeys.admin.auditEntity(entityType, entityId ?? 0, params),
    queryFn: () => adminApi.listAuditLogsByEntity(entityType, entityId!, params),
    enabled: entityId !== null,
    staleTime: 30 * 1000,
  })
}
