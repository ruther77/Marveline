import { createLazyFileRoute } from '@tanstack/react-router'
import ContainerDetailPage from '@/pages/inventory/ContainerDetailPage'

export const Route = createLazyFileRoute('/_app/stock/containers/$id')({
  component: ContainerDetailPage,
})
