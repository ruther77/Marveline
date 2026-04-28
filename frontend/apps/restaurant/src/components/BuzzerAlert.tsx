/**
 * BuzzerAlert — Notification sonore + vibration + badge visuel.
 *
 * Déclenché quand une commande est marquée "prête" en cuisine.
 * Son : fichier .ogg "ding" (~1s) joué via Audio API.
 * Vibration : Vibration API (200ms pulse).
 * Haut-parleur Bluetooth : même Audio API (le navigateur route vers le device BT connecté).
 */
import { useEffect, useRef, useState } from 'react'

interface BuzzerAlertProps {
  /** Trigger : incrémenter pour déclencher une alerte */
  trigger: number
  /** Texte affiché dans le badge */
  message?: string
  /** Durée d'affichage du badge (ms) */
  displayDuration?: number
}

// Ding synthétique via Web Audio API — aucun fichier externe requis
function playDing(volume = 0.8) {
  try {
    const ctx = new AudioContext()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.value = 880 // La5 — tonalité aiguë agréable
    gain.gain.setValueAtTime(volume, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.7)
    osc.start(ctx.currentTime)
    osc.stop(ctx.currentTime + 0.7)
    osc.onended = () => ctx.close()
  } catch {
    // Web Audio API non disponible (contexte insécurisé, etc.)
  }
}

export default function BuzzerAlert({
  trigger,
  message = 'Commande prête !',
  displayDuration = 5000,
}: BuzzerAlertProps) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastTriggerRef = useRef(0)

  useEffect(() => {
    if (trigger === 0 || trigger === lastTriggerRef.current) return
    lastTriggerRef.current = trigger

    // 1. Son synthétique
    playDing()

    // 2. Vibration
    if ('vibrate' in navigator) {
      navigator.vibrate([200, 100, 200])
    }

    // 3. Badge visuel
    setVisible(true)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setVisible(false), displayDuration)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [trigger, displayDuration])

  if (!visible) return null

  return (
    <div className="fixed top-4 inset-x-4 z-50 flex justify-center pointer-events-none animate-in slide-in-from-top">
      <div className="bg-green-600 text-white px-6 py-3 rounded-2xl shadow-lg flex items-center gap-3 pointer-events-auto">
        <div className="w-3 h-3 rounded-full bg-white animate-pulse" />
        <span className="text-sm font-semibold">{message}</span>
        <button
          onClick={() => setVisible(false)}
          className="text-white/70 hover:text-white text-xs ml-2"
        >
          ✕
        </button>
      </div>
    </div>
  )
}
