import { createLazyFileRoute } from '@tanstack/react-router'
import FormulasPage from '@/pages/products/FormulasPage'

export const Route = createLazyFileRoute('/_app/catalogue/formulas')({
  component: FormulasPage,
})
