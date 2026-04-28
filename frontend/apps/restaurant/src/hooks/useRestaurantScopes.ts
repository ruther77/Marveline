import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'

const SCOPE_READ = 'restaurant:read'
const SCOPE_WRITE = 'restaurant:write'

const MANAGER_ROLES = new Set(['manager', 'admin', 'superadmin', 'owner'])
const STAFF_ROLES = new Set(['staff', 'employee', 'server', 'barman', 'cuisinier'])

export interface RestaurantScopes {
  canRead: boolean
  canEdit: boolean
  isManager: boolean
  isStaff: boolean
  scopes: string[]
  role: string
}

export function useRestaurantScopes(): RestaurantScopes {
  const user = useMassaCorpAuthStore((s) => s.user)
  const scopes = user?.scopes ?? []
  const role = (user?.role ?? '').toLowerCase()

  const hasScopeRead = scopes.includes(SCOPE_READ)
  const hasScopeWrite = scopes.includes(SCOPE_WRITE)

  const isManager = MANAGER_ROLES.has(role) || hasScopeWrite
  const isStaff = STAFF_ROLES.has(role) || (hasScopeRead && !hasScopeWrite)

  return {
    canRead: hasScopeRead || isManager || isStaff,
    canEdit: hasScopeWrite || MANAGER_ROLES.has(role),
    isManager,
    isStaff,
    scopes,
    role,
  }
}
