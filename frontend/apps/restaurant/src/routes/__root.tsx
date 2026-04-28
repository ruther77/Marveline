import { createRootRoute, Outlet } from '@tanstack/react-router'
import { ToastProvider } from '@shared/components/ui/Toast'
import { ForbiddenError } from '@shared/errors/types'

function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-950">
      <p className="text-[14px] text-dark-400">Page introuvable</p>
    </div>
  )
}

function RootErrorPage({ error }: { error: unknown }) {
  const isForbidden = error instanceof ForbiddenError
  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-950">
      <div className="text-center max-w-sm px-6">
        <div className={`text-[3rem] font-bold mb-2 ${isForbidden ? 'text-red-500' : 'text-dark-500'}`}>
          {isForbidden ? '403' : '500'}
        </div>
        <h1 className="text-[1.1rem] font-semibold text-dark-50 mb-3">
          {isForbidden ? 'Accès refusé' : 'Erreur inattendue'}
        </h1>
        <p className="text-sm text-dark-400 mb-6">
          {isForbidden
            ? "Vous n'avez pas les permissions nécessaires pour accéder à cette ressource."
            : error instanceof Error ? error.message : 'Une erreur est survenue.'}
        </p>
        <a href="/" className="px-4 py-2 text-sm font-semibold bg-primary-500 text-white rounded-lg hover:opacity-90">
          Retour à l'accueil
        </a>
      </div>
    </div>
  )
}

export const Route = createRootRoute({
  notFoundComponent: NotFoundPage,
  errorComponent: ({ error }) => <RootErrorPage error={error} />,
  component: () => (
    <ToastProvider>
      <Outlet />
    </ToastProvider>
  ),
})
