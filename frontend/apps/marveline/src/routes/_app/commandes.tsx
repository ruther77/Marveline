import { createFileRoute, redirect } from '@tanstack/react-router'

// Page Commandes supprimée (décision D8) — redirige vers réservations
export const Route = createFileRoute('/_app/commandes')({
  beforeLoad: () => {
    throw redirect({ to: '/reservations' })
  },
})
