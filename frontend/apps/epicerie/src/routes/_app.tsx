import { createFileRoute, redirect } from '@tanstack/react-router'
import EpicerieLayout from '../layout/EpicerieLayout'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'

export const Route = createFileRoute('/_app')({
  beforeLoad: async ({ location }) => {
    // Lecture rapide localStorage (persisted SSO)
    const raw = localStorage.getItem('massacorp-auth')
    let localAuth = false
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        localAuth = !!parsed?.state?.isAuthenticated
      } catch {
        // JSON invalide
      }
    }

    // Verification serveur (refresh cookie httpOnly)
    try {
      await useMassaCorpAuthStore.getState().initialize()
      const { isAuthenticated } = useMassaCorpAuthStore.getState()
      if (!isAuthenticated) {
        throw redirect({ to: '/login' })
      }
    } catch (err) {
      // Propager les redirects TanStack
      if (err && typeof err === 'object' && '__isRedirect' in err) throw err

      // Fallback reseau
      const isNetworkOrTimeout =
        err instanceof TypeError ||
        (err instanceof Error && err.message === 'init-timeout')

      if (!localAuth || !isNetworkOrTimeout) {
        throw redirect({ to: '/login' })
      }
    }
  },
  component: EpicerieLayout,
})
