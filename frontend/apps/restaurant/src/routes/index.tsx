import { createFileRoute, redirect } from '@tanstack/react-router'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'

const MANAGER_ROLES = new Set(['manager', 'admin', 'superadmin', 'owner'])
const SCOPE_WRITE = 'restaurant:write'

export const Route = createFileRoute('/')({
  beforeLoad: async () => {
    // Landing conditionnelle selon rôle — gérant va au Dashboard,
    // staff (serveur/cuisinier/barman) atterrit en Salle pour le service.
    try {
      await useMassaCorpAuthStore.getState().initialize()
    } catch {
      // Si init fail, _app.beforeLoad gérera la redirection login
    }
    const user = useMassaCorpAuthStore.getState().user
    const role = (user?.role ?? '').toLowerCase()
    const scopes = user?.scopes ?? []
    const isManager = MANAGER_ROLES.has(role) || scopes.includes(SCOPE_WRITE)

    throw redirect({ to: isManager ? '/dashboard' : '/salle', replace: true })
  },
})
