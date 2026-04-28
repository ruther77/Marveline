import { createFileRoute } from '@tanstack/react-router'
import EpicerieDashboardPage from '../../pages/EpicerieDashboardPage'

export const Route = createFileRoute('/_app/dashboard')({
  component: EpicerieDashboardPage,
})
