import { useNavigate, useRouterState } from '@tanstack/react-router'
import { useCallback } from 'react'

/**
 * Mapping route → parent logique.
 * Quand l'utilisateur clique "retour", on remonte au parent metier, pas au browser history.
 *
 * Pattern : le chemin le plus specifique matche en premier.
 */
const BACK_MAP: [RegExp, string][] = [
  // Devis detail → liste devis
  [/^\/devis\/\d+/, '/devis'],
  // Devis new → liste devis
  [/^\/devis\/new/, '/devis'],

  // Reservation detail (phases) → liste reservations
  [/^\/reservations\/\d+/, '/reservations'],
  [/^\/reservations\/new/, '/reservations'],

  // Product detail sub-pages → product detail
  [/^\/catalogue\/products\/\d+\/(editor|photos|variants|availability|states|maintenance|audit)/, ''],
  // Product detail → catalogue
  [/^\/catalogue\/products\/\d+/, '/catalogue/products'],
  // Catalogue sub-pages → catalogue products
  [/^\/catalogue\/(bundles|categories|collections|search|comparator|tools|builder|qr)/, '/catalogue/products'],

  // Stock sub-pages → stock items
  [/^\/stock\/items\//, '/stock/items'],
  [/^\/stock\/alerts\//, '/stock/items'],
  [/^\/stock\/(movements|returns|repairs|reorder|adjustments|coverage|inventory|damage-types)/, '/stock/items'],

  // Finance sub-pages → factures
  [/^\/finance\/invoices\/\d+/, '/finance/invoices'],
  [/^\/finance\/(treasury|pricing)/, '/finance/invoices'],

  // Customer detail → clients
  [/^\/customers\/\d+/, '/customers'],

  // Operations → reservations (retour au contexte metier)
  [/^\/operations\/departure\//, '/reservations'],
  [/^\/operations\/return\//, '/reservations'],
  [/^\/operations/, '/reservations'],

  // Evenements detail → evenements
  [/^\/evenements\/\d+/, '/evenements/incidents'],

  // Planning sub-pages → planning today
  [/^\/planning\/(event|resources|affectation)/, '/planning/today'],

  // Admin sub-pages → admin users
  [/^\/admin\/users\//, '/admin/users'],

  // Profile → dashboard
  [/^\/profile/, '/dashboard'],

  // Notifications settings → notifications
  [/^\/notifications\/settings/, '/notifications'],
]

/**
 * Hook qui retourne la route "retour" logique pour la page courante.
 * Utilise un mapping statique (pas browser.history) pour un retour previsible.
 *
 * Usage :
 *   const { goBack, backTo } = useBackNavigation()
 *   <button onClick={goBack}><ArrowLeft /></button>
 */
export function useBackNavigation() {
  const navigate = useNavigate()
  const pathname = useRouterState({ select: (s) => s.location.pathname })

  const backTo = BACK_MAP.find(([re]) => re.test(pathname))?.[1] ?? '/dashboard'

  // Cas special : sous-page product detail → remonter au product detail (pas au catalogue)
  const productDetailSubMatch = pathname.match(/^\/catalogue\/products\/(\d+)\/(editor|photos|variants|availability|states|maintenance|audit)/)
  const resolvedBackTo = productDetailSubMatch
    ? `/catalogue/products/${productDetailSubMatch[1]}`
    : backTo

  const goBack = useCallback(() => {
    navigate({ to: resolvedBackTo as never })
  }, [navigate, resolvedBackTo])

  return { goBack, backTo: resolvedBackTo }
}
