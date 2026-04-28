import { createLazyFileRoute } from '@tanstack/react-router'
import MaintenancePage from '@/pages/products/MaintenancePage'

export const Route = createLazyFileRoute('/_app/catalogue/products/$id/maintenance')({
  component: MaintenancePage,
})
