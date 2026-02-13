import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { formatRelativeTime } from '@/lib/utils'
import {
  Monitor,
  Smartphone,
  Tablet,
  MapPin,
  Clock,
  Trash2,
  AlertTriangle,
  Loader2,
  CheckCircle,
} from 'lucide-react'

// Fonction pour détecter le type d'appareil à partir du user agent
function getDeviceIcon(userAgent: string) {
  const ua = userAgent.toLowerCase()

  // Détection mobile
  if (ua.includes('mobile') || ua.includes('iphone') || ua.includes('android') && !ua.includes('tablet')) {
    return Smartphone
  }

  // Détection tablette
  if (ua.includes('tablet') || ua.includes('ipad')) {
    return Tablet
  }

  // Par défaut : desktop
  return Monitor
}

export default function SessionsPage() {
  const [terminatingId, setTerminatingId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: sessions, isLoading } = useQuery({
    queryKey: ['user-sessions'],
    queryFn: () => adminApi.getUserSessions(),
  })

  const terminateMutation = useMutation({
    mutationFn: adminApi.terminateSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-sessions'] })
      setTerminatingId(null)
    },
  })

  const terminateAllMutation = useMutation({
    mutationFn: adminApi.terminateAllSessions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-sessions'] })
    },
  })

  const activeSessions = sessions?.filter((s) => s.is_active) || []
  const currentSession = sessions?.find((s) => s.is_current)

  const handleTerminate = (sessionId: string) => {
    setTerminatingId(sessionId)
    terminateMutation.mutate(sessionId)
  }

  const handleTerminateAll = () => {
    if (
      confirm(
        'Êtes-vous sûr de vouloir terminer toutes les autres sessions ? Vous resterez connecté sur cette session.'
      )
    ) {
      terminateAllMutation.mutate()
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Mes sessions</h1>
          <p className="text-dark-400 mt-1">
            Gérez vos sessions actives sur tous vos appareils
          </p>
        </div>
        {activeSessions.length > 1 && (
          <button
            onClick={handleTerminateAll}
            disabled={terminateAllMutation.isPending}
            className="btn-danger"
          >
            {terminateAllMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <Trash2 className="w-4 h-4 mr-2" />
            )}
            Terminer toutes les autres
          </button>
        )}
      </div>

      {/* Current Session */}
      {currentSession && (() => {
        const DeviceIcon = getDeviceIcon(currentSession.user_agent)
        return (
          <div className="card border-green-500/20">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-lg bg-green-500/10 flex items-center justify-center">
                  <DeviceIcon className="w-6 h-6 text-green-500" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">Session actuelle</h3>
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  </div>
                  <p className="text-sm text-dark-400 mt-1">
                    {currentSession.user_agent}
                  </p>
                  <div className="flex items-center gap-4 mt-2 text-sm text-dark-400">
                    <span className="flex items-center gap-1">
                      <MapPin className="w-4 h-4" />
                      {currentSession.ip_address}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      Connecté {formatRelativeTime(currentSession.created_at)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )
      })()}

      {/* Other Sessions */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Autres sessions</h2>

        {isLoading ? (
          <div className="card text-center py-8 text-dark-400">
            Chargement...
          </div>
        ) : activeSessions.filter((s) => !s.is_current).length === 0 ? (
          <div className="card text-center py-8 text-dark-400">
            Aucune autre session active
          </div>
        ) : (
          <div className="space-y-3">
            {activeSessions
              .filter((s) => !s.is_current)
              .map((session) => {
                const DeviceIcon = getDeviceIcon(session.user_agent)
                return (
                  <div
                    key={session.id}
                    className="card flex items-start justify-between"
                  >
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-lg bg-dark-700 flex items-center justify-center">
                        <DeviceIcon className="w-6 h-6 text-dark-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">{session.user_agent}</h3>
                        <div className="flex items-center gap-4 mt-2 text-sm text-dark-400">
                          <span className="flex items-center gap-1">
                            <MapPin className="w-4 h-4" />
                            {session.ip_address}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-4 h-4" />
                            {formatRelativeTime(session.last_seen_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleTerminate(session.id)}
                      disabled={terminatingId === session.id}
                      className="btn-ghost text-red-400 hover:text-red-300 hover:bg-red-500/10"
                    >
                      {terminatingId === session.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                )
              })}
          </div>
        )}
      </div>

      {/* Security Tip */}
      <div className="card border-yellow-500/20 bg-yellow-500/5">
        <div className="flex items-start gap-4">
          <AlertTriangle className="w-6 h-6 text-yellow-500 flex-shrink-0" />
          <div>
            <h3 className="font-semibold text-yellow-500">
              Conseil de sécurité
            </h3>
            <p className="text-sm text-dark-400 mt-1">
              Si vous ne reconnaissez pas une session, terminez-la immédiatement
              et changez votre mot de passe. Activez l'authentification à deux
              facteurs pour une sécurité renforcée.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
