import { createLazyFileRoute } from '@tanstack/react-router'
import RepairPlanningPage from '@/pages/inventory/RepairPlanningPage'

export const Route = createLazyFileRoute('/_app/stock/repairs')({
  component: RepairPlanningPage,
})
