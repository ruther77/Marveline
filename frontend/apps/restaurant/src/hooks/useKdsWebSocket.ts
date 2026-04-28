/**
 * Hook WebSocket KDS — connexion temps réel cuisine ↔ salle.
 *
 * Auth via ticket éphémère (UUID, TTL 30s, usage unique).
 * Le hook fetch POST /ws/ticket (auth Bearer) puis connecte
 * le WebSocket avec ?ticket=UUID — le JWT n'apparaît jamais
 * dans l'URL, les logs Nginx ou l'historique navigateur.
 *
 * Reconnexion automatique avec backoff exponentiel.
 * Heartbeat ping/pong toutes les 30s.
 * Callbacks via useRef pour éviter les reconnexions infinies (stale closures).
 */
import { useEffect, useRef, useState, useCallback } from 'react'

interface KdsEvent {
  event: string
  data: Record<string, unknown>
  timestamp: number
}

interface UseKdsWebSocketOptions {
  channel: 'kds' | 'salle'
  getToken: () => string | null
  onNouvelleCommande?: (data: Record<string, unknown>) => void
  onCommandePrete?: (data: Record<string, unknown>) => void
  onLignePrete?: (data: Record<string, unknown>) => void
  onCommandeAnnulee?: (data: Record<string, unknown>) => void
  onCommandeModifiee?: (data: Record<string, unknown>) => void
  onCommandePayee?: (data: Record<string, unknown>) => void
  enabled?: boolean
}

const MAX_RECONNECT_DELAY_MS = 30_000
const INITIAL_RECONNECT_DELAY_MS = 1_000

async function fetchWsTicket(token: string): Promise<string | null> {
  try {
    const res = await fetch('/ws/ticket', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    })
    if (!res.ok) return null
    const data = await res.json() as { ticket: string }
    return data.ticket
  } catch {
    return null
  }
}

export function useKdsWebSocket(options: UseKdsWebSocketOptions) {
  const { channel, getToken, enabled = true } = options

  const [isConnected, setIsConnected] = useState(false)
  const [events, setEvents] = useState<KdsEvent[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY_MS)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const connectingRef = useRef(false)
  const mountedRef = useRef(true)

  // Stocker les callbacks et getToken dans des refs pour éviter les reconnexions
  const callbacksRef = useRef(options)
  useEffect(() => { callbacksRef.current = options }, [options])
  const getTokenRef = useRef(getToken)
  useEffect(() => { getTokenRef.current = getToken }, [getToken])

  const connect = useCallback(async () => {
    if (connectingRef.current) return
    const token = getTokenRef.current()
    if (!token || !enabled) return

    connectingRef.current = true
    const ticket = await fetchWsTicket(token)
    connectingRef.current = false

    // Composant démonté pendant l'await — ne pas créer de WS orphelin
    if (!mountedRef.current) return

    if (!ticket) {
      // Ticket fetch failed — schedule reconnect
      if (enabled && mountedRef.current) {
        const delay = reconnectDelayRef.current
        reconnectTimerRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY_MS)
          connect()
        }, delay)
      }
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/${channel}?ticket=${encodeURIComponent(ticket)}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY_MS
    }

    ws.onclose = () => {
      setIsConnected(false)
      wsRef.current = null

      if (enabled) {
        const delay = reconnectDelayRef.current
        reconnectTimerRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY_MS)
          connect()
        }, delay)
      }
    }

    ws.onerror = () => { ws.close() }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as { event: string; data: Record<string, unknown> }

        if (msg.event === 'ping') {
          ws.send(JSON.stringify({ event: 'pong' }))
          return
        }
        if (msg.event === 'initial_state') return

        const kdsEvent: KdsEvent = { ...msg, timestamp: Date.now() }
        setEvents(prev => [...prev.slice(-99), kdsEvent])

        // Dispatch via refs (pas de stale closure)
        const cb = callbacksRef.current
        switch (msg.event) {
          case 'nouvelle_commande': cb.onNouvelleCommande?.(msg.data); break
          case 'commande_prete': cb.onCommandePrete?.(msg.data); break
          case 'ligne_prete': cb.onLignePrete?.(msg.data); break
          case 'commande_annulee': cb.onCommandeAnnulee?.(msg.data); break
          case 'commande_modifiee': cb.onCommandeModifiee?.(msg.data); break
          case 'commande_payee': cb.onCommandePayee?.(msg.data); break
        }
      } catch {
        // Ignore malformed messages
      }
    }
  }, [channel, enabled])

  const send = useCallback((event: string, data: Record<string, unknown> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event, data }))
    }
  }, [])

  useEffect(() => {
    if (enabled) connect()

    return () => {
      mountedRef.current = false
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect, enabled])

  // Reset mountedRef quand le hook est ré-initialisé (nouveau cycle useEffect)
  useEffect(() => {
    mountedRef.current = true
  }, [connect, enabled])

  return { events, isConnected, send }
}
