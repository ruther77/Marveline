import { createLazyFileRoute } from '@tanstack/react-router'
import DevisIdLayout from '@/pages/devis/DevisIdLayout'

export const Route = createLazyFileRoute('/_app/devis/$id')({
  component: DevisIdLayout,
})
