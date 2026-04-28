import { createFileRoute } from '@tanstack/react-router'
import ReceptionCommandesPage from '../../pages/ReceptionCommandesPage'

export const Route = createFileRoute('/_app/reception')({
  component: ReceptionCommandesPage,
})
