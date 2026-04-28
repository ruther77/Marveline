import { createFileRoute, Outlet, useRouterState } from '@tanstack/react-router'
import { SubNav } from '@/layout/SubNav'
import { PARC_NAV } from '@/lib/navigation'

function CatalogueLayout() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const isProductDetail = /\/catalogue\/products\/\d+/.test(pathname)
  const isBundleDetail = /\/catalogue\/bundles\/\d+/.test(pathname)
  const isCollectionDetail = /\/catalogue\/collections\/\d+/.test(pathname)
  const hideSubNav = isProductDetail || isBundleDetail || isCollectionDetail

  return (
    <div>
      {!hideSubNav && <SubNav items={PARC_NAV} />}
      <div className={hideSubNav ? '' : 'p-4 md:p-6'}>
        <Outlet />
      </div>
    </div>
  )
}

export const Route = createFileRoute('/_app/catalogue')({
  component: CatalogueLayout,
})
