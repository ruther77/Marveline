import { useState, useEffect, useCallback, useRef } from 'react'

interface NetworkStatus {
  isOnline: boolean
  wasOffline: boolean
}

/**
 * Tracks browser online/offline status via navigator.onLine + events.
 * `wasOffline` stays true after reconnection for a brief period,
 * allowing components to show "back online" feedback.
 */
export function useNetworkStatus(): NetworkStatus {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [wasOffline, setWasOffline] = useState(false)
  const wasOfflineTimer = useRef<ReturnType<typeof setTimeout>>()

  const handleOnline = useCallback(() => {
    setIsOnline(true)
    // Keep wasOffline=true for 5s so UI can show "reconnected" message
    setWasOffline(true)
    wasOfflineTimer.current = setTimeout(() => setWasOffline(false), 5000)
  }, [])

  const handleOffline = useCallback(() => {
    setIsOnline(false)
    setWasOffline(false)
    if (wasOfflineTimer.current) clearTimeout(wasOfflineTimer.current)
  }, [])

  useEffect(() => {
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      if (wasOfflineTimer.current) clearTimeout(wasOfflineTimer.current)
    }
  }, [handleOnline, handleOffline])

  return { isOnline, wasOffline }
}
