import { createFileRoute } from '@tanstack/react-router'
import MargesPage from '../../pages/MargesPage'

export const Route = createFileRoute('/_app/marges')({
  component: MargesPage,
})
