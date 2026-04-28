import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useUserSessions, useTerminateSession, useTerminateAllSessions, useLogoutDevice } from '@/api/queries'
import { ActionError, ErrorState } from '@shared/components/ui'
import { formatRelativeTime } from '@/lib/utils'
import { useHasScope } from '@/hooks/useHasScope'
import {
  Monitor,
  Smartphone,
  Tablet,
  Globe,
  Clock,
  Trash2,
  AlertTriangle,
  Loader2,
  ShieldCheck,
  LogOut,
} from 'lucide-react'
import type { Session } from '@/types'
import { normalizeError } from '@shared/errors/normalizer'

// ── UA Parser ────────────────────────────────────────────────────────────────

function parseUserAgent(ua: string) {
  const lower = ua.toLowerCase()

  // Device
  let device = 'Ordinateur'
  let DeviceIcon = Monitor
  if (lower.includes('iphone')) { device = 'iPhone'; DeviceIcon = Smartphone }
  else if (lower.includes('ipad')) { device = 'iPad'; DeviceIcon = Tablet }
  else if (lower.includes('android') && lower.includes('mobile')) { device = 'Android'; DeviceIcon = Smartphone }
  else if (lower.includes('android')) { device = 'Tablette Android'; DeviceIcon = Tablet }
  else if (lower.includes('macintosh') || lower.includes('mac os')) { device = 'Mac' }
  else if (lower.includes('windows')) { device = 'Windows' }
  else if (lower.includes('linux')) { device = 'Linux' }

  // Browser
  let browser = ''
  if (lower.includes('edg/') || lower.includes('edge/')) browser = 'Edge'
  else if (lower.includes('opr/') || lower.includes('opera')) browser = 'Opera'
  else if (lower.includes('firefox/')) browser = 'Firefox'
  else if (lower.includes('crios/') || (lower.includes('chrome/') && !lower.includes('chromium'))) browser = 'Chrome'
  else if (lower.includes('safari/') && !lower.includes('chrome')) browser = 'Safari'

  const label = browser ? `${browser} sur ${device}` : device

  return { label, DeviceIcon }
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function SessionSkeleton() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="flex items-center gap-4">
        <div className="w-11 h-11 skel rounded-xl shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-4 skel rounded w-40" />
          <div className="h-3 skel rounded w-56" />
        </div>
      </div>
    </div>
  )
}

// ── Session card ─────────────────────────────────────────────────────────────

function SessionCard({
  session,
  canRevoke,
  onTerminate,
  onLogoutDevice,
  isTerminating,
  isTerminatingDevice,
}: {
  session: Session
  canRevoke: boolean
  onTerminate: (id: string) => void
  onLogoutDevice: (deviceId: string) => void
  isTerminating: boolean
  isTerminatingDevice: boolean
}) {
  const { label, DeviceIcon } = parseUserAgent(session.user_agent)
  const isCurrent = !!session.is_current

  return (
    <div
      className={`card p-4 hover:shadow-md transition-shadow ${
        isCurrent
          ? 'border-primary-500/40 ring-1 ring-primary-500/20'
          : ''
      }`}
    >
      <div className="flex items-center gap-4">
        {/* Icon */}
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
          isCurrent ? 'bg-primary-500/10' : 'bg-dark-900'
        }`}>
          <DeviceIcon className={`w-5 h-5 ${isCurrent ? 'text-primary-400' : 'text-dark-400'}`} />
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-sm">{label}</p>
            {isCurrent && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-primary-500/10 text-primary-400">
                <ShieldCheck className="w-3 h-3" />
                Cette session
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-dark-400">
            <span className="flex items-center gap-1">
              <Globe className="w-3 h-3" />
              {session.ip_address}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatRelativeTime(session.last_activity)}
            </span>
          </div>
        </div>

        {/* Actions */}
        {canRevoke && !isCurrent && (
          <div className="flex items-center gap-1 shrink-0">
            {session.device_id && (
              <button
                onClick={() => onLogoutDevice(session.device_id!)}
                disabled={isTerminatingDevice}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-amber-400 hover:bg-amber-500/10 rounded-lg transition-colors min-h-[44px]"
                title="Déconnecter cet appareil"
              >
                {isTerminatingDevice
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : <LogOut className="w-3.5 h-3.5" />
                }
                <span className="hidden sm:inline">Appareil</span>
              </button>
            )}
            <button
              onClick={() => onTerminate(session.session_id)}
              disabled={isTerminating}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-red-400 hover:bg-red-500/10 rounded-lg transition-colors min-h-[44px]"
              title="Révoquer cette session"
            >
              {isTerminating
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Trash2 className="w-3.5 h-3.5" />
              }
              <span className="hidden sm:inline">Révoquer</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function SessionsPage() {
  const canRevoke = useHasScope('sessions:revoke')
  const [terminatingId, setTerminatingId] = useState<string | null>(null)
  const [terminatingDeviceId, setTerminatingDeviceId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [showConfirmAll, setShowConfirmAll] = useState(false)

  const { data: sessions, isLoading, error: queryError, refetch } = useUserSessions()
  const terminateMutation = useTerminateSession()
  const terminateAllMutation = useTerminateAllSessions()
  const logoutDeviceMutation = useLogoutDevice()

  const otherCount = sessions?.filter((s) => !s.is_current).length ?? 0

  const handleTerminate = (sessionId: string) => {
    setTerminatingId(sessionId)
    terminateMutation.mutate(sessionId, {
      onSuccess: () => { setActionError(null); setTerminatingId(null) },
      onError: (err) => { setActionError(normalizeError(err).message || 'Erreur'); setTerminatingId(null) },
    })
  }

  const handleTerminateAll = () => {
    terminateAllMutation.mutate(undefined, {
      onSuccess: () => { setActionError(null); setShowConfirmAll(false) },
      onError: (err) => setActionError(normalizeError(err).message || 'Erreur'),
    })
  }

  const handleLogoutDevice = (deviceId: string) => {
    setTerminatingDeviceId(deviceId)
    logoutDeviceMutation.mutate(deviceId, {
      onSuccess: () => { setActionError(null); setTerminatingDeviceId(null) },
      onError: (err) => { setActionError(normalizeError(err).message || 'Erreur'); setTerminatingDeviceId(null) },
    })
  }

  return (
    <div className="max-w-2xl lg:max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <PageHeader
          title="Mes sessions"
          subtitle={`${sessions?.length ?? 0} appareil${(sessions?.length ?? 0) > 1 ? 's' : ''} connecté${(sessions?.length ?? 0) > 1 ? 's' : ''}`}
        />
        {canRevoke && otherCount > 0 && (
          showConfirmAll ? (
            <div className="flex items-center gap-3">
              <span className="text-sm text-dark-400">Déconnecter {otherCount} autre{otherCount > 1 ? 's' : ''} ?</span>
              <button
                onClick={handleTerminateAll}
                disabled={terminateAllMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50"
              >
                {terminateAllMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                Confirmer
              </button>
              <button onClick={() => setShowConfirmAll(false)} className="text-xs text-dark-400 hover:text-dark-200">
                Annuler
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowConfirmAll(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              Tout déconnecter
            </button>
          )
        )}
      </div>

      <ActionError message={actionError} onDismiss={() => setActionError(null)} />

      {/* Sessions list */}
      {queryError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <SessionSkeleton key={i} />)}
        </div>
      ) : !sessions || sessions.length === 0 ? (
        <div className="card p-8 text-center">
          <Monitor className="w-8 h-8 text-dark-400 mx-auto mb-3" />
          <p className="text-dark-400 text-sm">Aucune session active</p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Current session first */}
          {sessions
            .sort((a, b) => (b.is_current ? 1 : 0) - (a.is_current ? 1 : 0))
            .map((session) => (
              <SessionCard
                key={session.session_id}
                session={session}
                canRevoke={canRevoke}
                onTerminate={handleTerminate}
                onLogoutDevice={handleLogoutDevice}
                isTerminating={terminatingId === session.session_id}
                isTerminatingDevice={terminatingDeviceId === session.device_id}
              />
            ))
          }
        </div>
      )}

      {/* Security tip */}
      <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-amber-400">Vous ne reconnaissez pas un appareil ?</p>
          <p className="text-xs text-dark-400 mt-1">
            Révoquez la session immédiatement, changez votre mot de passe et activez la double authentification.
          </p>
        </div>
      </div>
    </div>
  )
}
