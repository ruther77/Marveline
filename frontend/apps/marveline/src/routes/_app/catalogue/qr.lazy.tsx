import { createLazyFileRoute } from '@tanstack/react-router'
import CatalogueQRPage from '@/pages/products/CatalogueQRPage'

export const Route = createLazyFileRoute('/_app/catalogue/qr')({
  component: CatalogueQRPage,
})
