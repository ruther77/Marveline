import { WifiOff, Wifi } from 'lucide-react'
import { useNetworkStatus } from '@/hooks/useNetworkStatus'
import { cn } from '@/lib/utils'

/**
 * Persistent banner shown when the browser goes offline.
 * Shows a "back online" confirmation briefly after reconnection.
 * Placed at the top of the main content area.
 */
export default function OfflineBanner() {
  const { isOnline, wasOffline } = useNetworkStatus()

  // Nothing to show
  if (isOnline && !wasOffline) return null

  return (
    <div
      role="alert"
      className={cn(
        'flex items-center gap-4 px-4 py-2.5 text-sm font-medium transition-all duration-300',
        isOnline
          ? 'bg-green-900/80 text-green-200 border-b border-green-700/50'
          : 'bg-yellow-900/80 text-yellow-200 border-b border-yellow-700/50',
      )}
    >
      {isOnline ? (
        <>
          <Wifi className="w-4 h-4 flex-shrink-0" />
          <span>Connexion retablie</span>
        </>
      ) : (
        <>
          <WifiOff className="w-4 h-4 flex-shrink-0" />
          <span>Connexion perdue — les donnees affichees peuvent etre obsoletes</span>
        </>
      )}
    </div>
  )
}
