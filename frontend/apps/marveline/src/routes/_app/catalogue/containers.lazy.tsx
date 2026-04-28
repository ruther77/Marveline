import { createLazyFileRoute, Navigate } from '@tanstack/react-router'

export const Route = createLazyFileRoute('/_app/catalogue/containers')({
  component: () => <Navigate to="/stock/containers" />,
})
