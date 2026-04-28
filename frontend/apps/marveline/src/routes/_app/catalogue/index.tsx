import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/catalogue/')({
  beforeLoad: () => {
    throw redirect({ to: '/catalogue/products' })
  },
})
