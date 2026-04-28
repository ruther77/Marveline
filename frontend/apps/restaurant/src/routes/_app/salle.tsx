import { createFileRoute } from '@tanstack/react-router'
import SallePage from '../../pages/SallePage'

export const Route = createFileRoute('/_app/salle')({
  component: SallePage,
})
