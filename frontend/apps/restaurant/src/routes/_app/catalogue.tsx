import { createFileRoute } from '@tanstack/react-router'
import CataloguePage from '../../pages/CataloguePage'
import { requireManager } from '@/lib/routeGuards'

export const Route = createFileRoute('/_app/catalogue')({
  beforeLoad: requireManager,
  component: CataloguePage,
})
