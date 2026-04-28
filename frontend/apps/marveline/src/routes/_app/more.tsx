import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/more')({
  beforeLoad: () => {
    throw redirect({ to: '/plus' })
  },
  component: () => null,
})
