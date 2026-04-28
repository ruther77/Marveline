import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { Shield } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useBrand } from '@/brand/select'

function AuthLayout() {
  const brand = useBrand()
  return (
    <div className="min-h-screen flex">
      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary-600 to-primary-900 p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-4">
            <Shield className="w-10 h-10 text-white" />
            <span className="text-2xl font-bold text-white">{brand.name}</span>
          </div>
        </div>

        <div className="space-y-6">
          <h1 className="text-4xl font-bold text-white">
            Gérez votre activité simplement
          </h1>
          <p className="text-lg text-primary-100">
            Devis, réservations, stock, événements et facturation — tout en un.
          </p>
        </div>

        <div className="text-primary-200 text-sm">
          &copy; {new Date().getFullYear()} {brand.name}. Tous droits réservés.
        </div>
      </div>

      {/* Right side - Forms */}
      <div className="flex-1 flex items-center justify-center p-8 bg-dark-900">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center justify-center gap-4 mb-8">
            <Shield className="w-8 h-8 text-primary-500" />
            <span className="text-xl font-bold">{brand.shortName}</span>
          </div>

          <Outlet />
        </div>
      </div>
    </div>
  )
}

export const Route = createFileRoute('/_auth')({
  beforeLoad: () => {
    if (useAuthStore.getState().isAuthenticated) {
      throw redirect({ to: '/dashboard' })
    }
  },
  component: AuthLayout,
})
