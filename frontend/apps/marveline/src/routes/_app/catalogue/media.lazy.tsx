import { createLazyFileRoute } from '@tanstack/react-router'
import MediaPage from '@/pages/products/MediaPage'

export const Route = createLazyFileRoute('/_app/catalogue/media')({
  component: MediaPage,
})
