import { createLazyFileRoute } from '@tanstack/react-router'
import OperationsDashboardPage from '@/pages/operations/OperationsDashboardPage'

export const Route = createLazyFileRoute('/_app/operations/')({
  component: OperationsDashboardPage,
})
