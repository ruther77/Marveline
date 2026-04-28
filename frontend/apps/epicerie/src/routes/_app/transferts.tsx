import { createFileRoute, Outlet, useRouterState } from '@tanstack/react-router'
import TransfertsPage from '../../pages/TransfertsPage'
import TransfertNouveauPage from '../../pages/TransfertNouveauPage'

function TransfertsRouteComponent() {
  const pathname = useRouterState({ select: state => state.location.pathname })

  if (pathname === '/transferts' || pathname === '/transferts/') {
    return <TransfertsPage />
  }

   if (pathname === '/transferts/nouveau') {
    return <TransfertNouveauPage />
  }

  return <Outlet />
}

export const Route = createFileRoute('/_app/transferts')({
  component: TransfertsRouteComponent,
})
