import { createFileRoute } from '@tanstack/react-router'
import NotFoundPage from '@/pages/errors/NotFoundPage'

export const Route = createFileRoute('/$')({ component: NotFoundPage })
