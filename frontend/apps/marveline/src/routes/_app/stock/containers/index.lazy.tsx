import { createLazyFileRoute } from '@tanstack/react-router'
import ContainersListPage from '@/pages/inventory/ContainersListPage'

export const Route = createLazyFileRoute('/_app/stock/containers/')({
  component: ContainersListPage,
})
