import { createFileRoute } from '@tanstack/react-router'
import TransfertNouveauPage from '../../../pages/TransfertNouveauPage'

export const Route = createFileRoute('/_app/transferts/nouveau')({
  component: TransfertNouveauPage,
})
