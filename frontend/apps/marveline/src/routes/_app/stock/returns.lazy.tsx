import { createLazyFileRoute } from '@tanstack/react-router'
import ReturnsPage from '@/pages/inventory/ReturnsPage'

export const Route = createLazyFileRoute('/_app/stock/returns')({
  component: ReturnsPage,
})
