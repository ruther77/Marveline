import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/stock/returns')({
  beforeLoad: () => {
    throw redirect({ to: '/stock/repairs' })
  },
})
