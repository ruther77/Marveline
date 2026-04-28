import { createFileRoute } from '@tanstack/react-router'
import PreparationsPage from '../../pages/PreparationsPage'
import { requireManager } from '@/lib/routeGuards'

export const Route = createFileRoute('/_app/preparations')({
  beforeLoad: requireManager,
  component: PreparationsPage,
})
