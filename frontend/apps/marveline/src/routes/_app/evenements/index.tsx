import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/evenements/')({
  beforeLoad: () => {
    throw redirect({ to: '/reservations' })
  },
})
