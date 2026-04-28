import { createLazyFileRoute } from '@tanstack/react-router'
import ComparateurPage from '@/pages/products/ComparateurPage'

export const Route = createLazyFileRoute('/_app/catalogue/comparator')({
  component: ComparateurPage,
})
