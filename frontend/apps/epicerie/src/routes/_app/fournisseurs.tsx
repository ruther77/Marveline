import { createFileRoute } from '@tanstack/react-router'
import FournisseursPage from '../../pages/FournisseursPage'

export const Route = createFileRoute('/_app/fournisseurs')({
  component: FournisseursPage,
})
