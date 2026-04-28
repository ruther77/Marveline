import { createFileRoute, redirect } from '@tanstack/react-router'
import DashboardLayout from '@/layout/DashboardLayout'
import { useAuthStore } from '@/stores/authStore'

export const Route = createFileRoute('/_app')({
  beforeLoad: async ({ location }) => {
    // Vérification rapide côté client (persisted)
    const raw = localStorage.getItem('marveline-auth')
    let localAuth = false
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        localAuth = !!parsed?.state?.isAuthenticated
      } catch {
        // JSON invalide — continuer vers vérification serveur
      }
    }

    // Vérification serveur systématique (refresh cookie httpOnly)
    try {
      await useAuthStore.getState().initialize()
      const { isAuthenticated, user } = useAuthStore.getState()
      if (!isAuthenticated) {
        throw redirect({
          to: '/login',
          search: { redirect: location.pathname + location.searchStr },
        })
      }

      // Guard password_change_required — redirige vers /profile/security
      // sauf si on y est déjà (évite boucle infinie)
      if (
        user?.password_change_required &&
        !location.pathname.startsWith('/profile/security')
      ) {
        throw redirect({ to: '/profile/security' })
      }
    } catch (err) {
      // Si l'erreur est un redirect TanStack Router, la propager
      if (err && typeof err === 'object' && '__isRedirect' in err) throw err

      // Fallback : uniquement si erreur réseau/timeout (pas de connectivité)
      // Une erreur 500 serveur = le serveur est UP mais en erreur → ne pas laisser passer
      const isNetworkOrTimeout =
        err instanceof TypeError ||
        (err instanceof Error && err.message === 'init-timeout')

      if (!localAuth || !isNetworkOrTimeout) {
        throw redirect({
          to: '/login',
          search: { redirect: location.pathname + location.searchStr },
        })
      }
    }
  },
  component: DashboardLayout,
})
