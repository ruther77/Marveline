import { createLazyFileRoute } from '@tanstack/react-router'
import CategoriesPage from '@/pages/products/CategoriesPage'

export const Route = createLazyFileRoute('/_app/catalogue/categories')({
  component: CategoriesPage,
})
