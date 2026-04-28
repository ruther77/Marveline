import { createLazyFileRoute } from '@tanstack/react-router'
import PlanningAffectationPage from '@/pages/planning/PlanningAffectationPage'

export const Route = createLazyFileRoute('/_app/planning/affectation')({
  component: PlanningAffectationPage,
})
