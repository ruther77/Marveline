// Hook célébration — imperative trigger + détection transition PREVIEW → VALIDATED

import { useState, useEffect, useRef, useCallback } from 'react'

const CELEBRATION_DURATION_MS = 4000

/**
 * Déclenche une célébration (confettis) de deux façons :
 * 1. triggerCelebration() — appel impératif depuis handleValidate (principal)
 * 2. Transition PREVIEW → VALIDATED détectée sur le statut (fallback)
 * Ignore les navigations vers un import déjà VALIDATED.
 */
export function useCelebration(statut?: string) {
  const [showCelebration, setShowCelebration] = useState(false)
  const prevStatut = useRef<string | undefined>(undefined)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const triggerCelebration = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setShowCelebration(true)
    timerRef.current = setTimeout(() => setShowCelebration(false), CELEBRATION_DURATION_MS)
  }, [])

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [])

  useEffect(() => {
    if (!statut) return

    // Fallback : détection transition PREVIEW → VALIDATED
    if (statut === 'VALIDATED' && prevStatut.current === 'PREVIEW') {
      triggerCelebration()
    }

    prevStatut.current = statut
  }, [statut, triggerCelebration])

  return {
    showCelebration,
    triggerCelebration,
    dismissCelebration: () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      setShowCelebration(false)
    },
  }
}
