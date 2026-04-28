import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/stock/')({
  beforeLoad: () => {
    throw redirect({ to: '/stock/items' })
  },
})
