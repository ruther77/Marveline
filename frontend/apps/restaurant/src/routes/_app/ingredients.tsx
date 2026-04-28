import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/ingredients')({
  beforeLoad: () => {
    throw redirect({ to: '/stock' })
  },
  component: () => null,
})
