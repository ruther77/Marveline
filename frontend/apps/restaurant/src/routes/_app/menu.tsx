import { createFileRoute } from '@tanstack/react-router'
import MenuPage from '../../pages/MenuPage'
import { requireManager } from '@/lib/routeGuards'

export const Route = createFileRoute('/_app/menu')({
  beforeLoad: requireManager,
  component: MenuPage,
})
