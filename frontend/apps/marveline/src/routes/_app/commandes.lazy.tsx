import { createLazyFileRoute } from '@tanstack/react-router'
import CommandesListPage from '@/pages/commandes/CommandesListPage'

export const Route = createLazyFileRoute('/_app/commandes')({
  component: CommandesListPage,
})
