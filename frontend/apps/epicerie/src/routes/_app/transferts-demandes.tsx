import { createFileRoute } from '@tanstack/react-router'
import TransfertDemandesPage from '../../pages/TransfertDemandesPage'

export const Route = createFileRoute('/_app/transferts-demandes')({
  component: TransfertDemandesPage,
})
