import { createLazyFileRoute } from '@tanstack/react-router'
import CataloguePilotagePage from '@/pages/products/CataloguePilotagePage'

export const Route = createLazyFileRoute('/_app/catalogue/pilotage')({
  component: CataloguePilotagePage,
})
