import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/layout/SubNav'

const ADMIN_NAV = [
  { label: 'Utilisateurs', href: '/admin/users' },
  { label: 'Sessions', href: '/admin/sessions' },
  { label: 'Fidélité', href: '/admin/loyalty' },
  { label: 'Clés API', href: '/admin/api-keys' },
  { label: 'Fonctionnalités', href: '/admin/features' },
  { label: 'Audit', href: '/admin/audit-logs' },
  { label: 'VPN', href: '/admin/vpn' },
  { label: 'Paramètres', href: '/admin/settings' },
]

export const Route = createFileRoute('/_app/admin')({
  component: () => (
    <div>
      <SubNav items={ADMIN_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
