import { createLazyFileRoute } from '@tanstack/react-router'
import DamageTypesPage from '@/pages/inventory/DamageTypesPage'

export const Route = createLazyFileRoute('/_app/stock/damage-types')({
  component: DamageTypesPage,
})
