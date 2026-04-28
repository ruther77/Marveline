import { createFileRoute } from '@tanstack/react-router'
import MesDemandesPage from '../../pages/MesDemandesPage'
import { requireManager } from '@/lib/routeGuards'

export const Route = createFileRoute('/_app/mes-demandes')({
  beforeLoad: requireManager,
  component: MesDemandesPage,
})
