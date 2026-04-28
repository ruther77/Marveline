import { createLazyFileRoute } from '@tanstack/react-router'
import DevisDetailsTab from '@/pages/devis/DevisDetailsTab'

export const Route = createLazyFileRoute('/_app/devis/$id/')({
  component: DevisDetailsTab,
})
