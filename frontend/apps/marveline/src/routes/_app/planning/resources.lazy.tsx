import { createLazyFileRoute } from '@tanstack/react-router'
import PlanningResourcesPage from '@/pages/planning/PlanningResourcesPage'

export const Route = createLazyFileRoute('/_app/planning/resources')({
  component: PlanningResourcesPage,
})
