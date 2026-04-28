import { createLazyFileRoute } from '@tanstack/react-router'
import PlanningConflictPage from '@/pages/planning/PlanningConflictPage'

export const Route = createLazyFileRoute('/_app/planning/conflicts')({
  component: PlanningConflictPage,
})
