import { createFileRoute, redirect } from '@tanstack/react-router'
import RestaurantLayout from '../layout/RestaurantLayout'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'
import { ForbiddenError } from '@shared/errors/types'

function ForbiddenPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-950">
      <div className="text-center max-w-sm px-6">
        <div className="text-[3rem] font-bold text-red-500 mb-2">403</div>
        <h1 className="text-[1.1rem] font-semibold text-dark-50 mb-3">Accès refusé</h1>
        <p className="text-sm text-dark-400 mb-6">
          Vous n'avez pas les permissions nécessaires pour accéder à cette ressource.
          Vérifiez votre connexion ou contactez votre administrateur.
        </p>
        <div className="flex gap-3 justify-center">
          <a href="/" className="px-4 py-2 text-sm font-semibold bg-primary-500 text-white rounded-lg hover:opacity-90">
            Retour à l'accueil
          </a>
          <a href="/login" className="px-4 py-2 text-sm font-medium border border-dark-600 text-dark-200 rounded-lg hover:bg-dark-800">
            Se connecter
          </a>
        </div>
      </div>
    </div>
  )
}

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

      // 403 Forbidden : authentifié mais sans permissions restaurant → page erreur
      if (err instanceof ForbiddenError) throw err

      // Fallback reseau : laisser passer uniquement si localStorage dit auth + erreur reseau
      const isNetworkOrTimeout =
        err instanceof TypeError ||
        (err instanceof Error && err.message === 'init-timeout')

      if (!localAuth || !isNetworkOrTimeout) {
        throw redirect({ to: '/login' })
      }
    }
  },
  errorComponent: ({ error }) => {
    if (error instanceof ForbiddenError) return <ForbiddenPage />
    // Pour les autres erreurs non gérées, rediriger vers login
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-950">
        <p className="text-dark-400 text-sm">Une erreur est survenue. <a href="/login" className="text-primary-400 underline">Se connecter</a></p>
      </div>
    )
  },
  component: RestaurantLayout,
})
