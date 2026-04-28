import { useQuery } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { featureFlagsApi } from '../featureFlags'
import { useAuthStore } from '@/stores/authStore'
import { useHasScope } from '@/hooks/useHasScope'
import { BRAND } from '@/brand/select'

interface UseFeatureCheckOptions {
  enabled?: boolean
  defaultEnabled?: boolean
  tenantId?: number | null
}

/**
 * Runtime feature gating via GET /features/check/{flag_name}.
 * Fallback `defaultEnabled=true` keeps product usable when the check is unavailable.
 */
export function useFeatureCheck(flagName: string, options?: UseFeatureCheckOptions) {
  const tenantIdFromUser = useAuthStore((s) => s.user?.tenant_id)
  const canReadFeatures = useHasScope('features:read')

  const defaultEnabled = options?.defaultEnabled ?? true
  const explicitEnabled = options?.enabled ?? true
  const tenantId = options?.tenantId ?? tenantIdFromUser ?? Number(import.meta.env.VITE_TENANT_ID || BRAND.defaultTenantId)

  const queryEnabled =
    explicitEnabled &&
    canReadFeatures &&
    Number.isFinite(tenantId) &&
    tenantId > 0 &&
    flagName.trim().length > 0

  const query = useQuery({
    queryKey: queryKeys.features.check(flagName, tenantId),
    queryFn: () => featureFlagsApi.check(flagName, tenantId),
    enabled: queryEnabled,
    staleTime: 60 * 1000,
  })

  const isEnabled = query.data?.enabled ?? defaultEnabled
  const reason = query.data?.reason
    ?? (queryEnabled ? (query.isError ? 'check_failed' : 'pending') : 'fallback')
  const source = query.data ? 'remote' : 'fallback'

  return {
    ...query,
    isEnabled,
    reason,
    source,
    isChecking: queryEnabled && query.isLoading,
  }
}

