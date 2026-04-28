import { createFileRoute } from '@tanstack/react-router'
import PointDeVente from '../../pages/PointDeVente'

export const Route = createFileRoute('/_app/pos')({
  component: PointDeVente,
})
