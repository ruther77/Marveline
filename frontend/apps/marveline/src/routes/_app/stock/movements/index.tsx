import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/stock/movements/')({
  beforeLoad: () => {
    throw redirect({ to: '/stock/items' })
  },
})
