import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SubNav } from '@/layout/SubNav'
import { PARC_NAV } from '@/lib/navigation'

export const Route = createFileRoute('/_app/stock')({
  component: () => (
    <div>
      <SubNav items={PARC_NAV} />
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  ),
})
