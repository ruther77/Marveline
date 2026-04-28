import { createFileRoute, Outlet, useParams } from '@tanstack/react-router'
import { useProductDetail } from '@/api/queries'
import { EntityBreadcrumb } from '@/layout/EntityBreadcrumb'
import { SubNav } from '@/layout/SubNav'

export const Route = createFileRoute('/_app/catalogue/products/$id')({
  component: ProductDetailLayout,
})

function ProductDetailLayout() {
  const { id } = useParams({ from: '/_app/catalogue/products/$id' })
  const productId = id ? parseInt(id, 10) : null
  const { data: product } = useProductDetail(productId)

  const productNav = [
    { label: '← Catalogue', href: '/catalogue/products' },
    { label: 'Fiche',       href: `/catalogue/products/${id}` },
    { label: 'Éditeur',     href: `/catalogue/products/${id}/editor` },
    { label: 'Variantes',   href: `/catalogue/products/${id}/variants` },
    { label: 'Maintenance', href: `/catalogue/products/${id}/maintenance` },
  ]

  return (
    <div>
      <SubNav items={productNav} />
      <div className="px-4 pt-2 md:px-6">
        <EntityBreadcrumb
          items={[
            { label: 'Catalogue', href: '/catalogue/products' },
            { label: product?.name ?? '...' },
          ]}
          backTo="/catalogue/products"
        />
      </div>
      <div className="p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  )
}
