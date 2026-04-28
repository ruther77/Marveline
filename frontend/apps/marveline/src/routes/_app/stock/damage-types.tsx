import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/stock/damage-types')({
  beforeLoad: () => {
    throw redirect({ to: '/stock/repairs' })
  },
})
