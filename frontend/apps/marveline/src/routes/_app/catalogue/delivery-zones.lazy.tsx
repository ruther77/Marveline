import { createLazyFileRoute } from '@tanstack/react-router'
import DeliveryZonesPage from '@/pages/products/DeliveryZonesPage'

export const Route = createLazyFileRoute('/_app/catalogue/delivery-zones')({
  component: DeliveryZonesPage,
})
