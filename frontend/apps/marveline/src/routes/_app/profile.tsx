import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/layout/SubNav'

const PROFILE_NAV = [
  { label: 'Informations', href: '/profile' },
  { label: 'Sécurité', href: '/profile/security' },
  { label: 'Authentification 2FA', href: '/profile/mfa' },
  { label: 'Mes sessions', href: '/profile/sessions' },
]

export const Route = createFileRoute('/_app/profile')({
  component: () => (
    <div>
      <SubNav items={PROFILE_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
