import { Outlet, useNavigate, useParams, useMatches } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'
import { useReservationFull, useReservationDeposits } from '@/api/queries'
import { derivePhase } from '@/pages/reservations/ReservationRouter'

export default function EventIdLayout() {
  const { id } = useParams({ strict: false }) as { id: string }
  const reservationId = Number(id)
  const navigate = useNavigate()
  const lastPhaseRef = useRef<string | null>(null)

  const { data: reservation } = useReservationFull(reservationId)
  const { data: deposits } = useReservationDeposits(reservationId)

  const matches = useMatches()
  const currentPhase = matches.at(-1)?.params?.phase as string | undefined

  useEffect(() => {
    if (!reservation) return
    const expectedPhase = derivePhase(reservation, deposits ?? [])

    // Si on est déjà sur la bonne phase, rien à faire
    if (currentPhase === expectedPhase) {
      lastPhaseRef.current = expectedPhase
      return
    }

    // Eviter boucle infinie
    if (lastPhaseRef.current === expectedPhase) return
    lastPhaseRef.current = expectedPhase

    navigate({
      to: '/reservations/$id/$phase' as never,
      params: { id, phase: expectedPhase } as never,
      replace: true,
    })
  }, [reservation, deposits, id, currentPhase, navigate])

  useEffect(() => {
    lastPhaseRef.current = null
  }, [id])

  return <Outlet />
}
