import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/planning/')({
  beforeLoad: () => {
    throw redirect({ to: '/planning/calendar' })
  },
})

