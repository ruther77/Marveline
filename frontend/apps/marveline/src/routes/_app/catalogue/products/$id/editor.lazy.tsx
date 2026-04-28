import { createLazyFileRoute } from '@tanstack/react-router'
import ProductEditorPage from '@/pages/products/ProductEditorPage'

export const Route = createLazyFileRoute('/_app/catalogue/products/$id/editor')({
  component: ProductEditorPage,
})
