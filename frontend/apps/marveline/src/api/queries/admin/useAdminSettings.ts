import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminSettingsApi } from '../../admin_settings'
import type { TenantSettingsUpdate } from '../../admin_settings'

const SETTINGS_KEY = ['admin', 'tenant-settings'] as const

export function useTenantSettings() {
  return useQuery({
    queryKey: SETTINGS_KEY,
    queryFn: () => adminSettingsApi.get(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useUpdateTenantSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: TenantSettingsUpdate) => adminSettingsApi.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: SETTINGS_KEY }) },
  })
}
