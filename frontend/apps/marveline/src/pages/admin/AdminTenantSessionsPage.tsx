import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { useAdminTenantSessions, useRevokeAdminTenantSession } from '@/api/queries'
import { ActionError } from '@shared/components/ui'
import { formatRelativeTime } from '@/lib/utils'
import { useHasScope } from '@/hooks/useHasScope'
import {
  Monitor,
  Smartphone,
  Tablet,
  Globe,
  Clock,
  Trash2,
  Loader2,
  ShieldCheck,
  Users,
} from 'lucide-react'
import type { Session } from '@/types'
import { normalizeError } from '@shared/errors/normalizer'

// ── UA Parser ────────────────────────────────────────────────────────────────

function parseUserAgent(ua: string) {
  const lower = ua.toLowerCase()

  let device = 'Ordinateur'
  let DeviceIcon = Monitor
  if (lower.includes('iphone')) { device = 'iPhone'; DeviceIcon = Smartphone }
  else if (lower.includes('ipad')) { device = 'iPad'; DeviceIcon = Tablet }
  else if (lower.includes('android') && lower.includes('mobile')) { device = 'Android'; DeviceIcon = Smartphone }
  else if (lower.includes('android')) { device = 'Tablette Android'; DeviceIcon = Tablet }
  else if (lower.includes('macintosh') || lower.includes('mac os')) { device = 'Mac' }
  else if (lower.includes('windows')) { device = 'Windows' }
  else if (lower.includes('linux')) { device = 'Linux' }

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

// ── Main page ────────────────────────────────────────────────────────────────

export default function AdminTenantSessionsPage() {
  const { user } = useAuthStore()
  const tenantId = user?.tenant_id ?? 0
  const canRevoke = useHasScope('sessions:revoke')
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [showConfirmAll, setShowConfirmAll] = useState(false)
  const [revokingAll, setRevokingAll] = useState(false)

  const { data, isLoading } = useAdminTenantSessions(tenantId)
  const revokeMutation = useRevokeAdminTenantSession(tenantId)

  const sessions: Session[] = data?.sessions ?? []
  const activeCount = data?.active_count ?? 0
  const otherSessions = sessions.filter((s) => !s.is_current)

  const handleRevoke = (sessionId: string) => {
    setRevokingId(sessionId)
    revokeMutation.mutate(sessionId, {
      onSuccess: () => { setActionError(null); setRevokingId(null) },
      onError: (err) => { setActionError(normalizeError(err).message || 'Erreur'); setRevokingId(null) },
    })
  }

  const handleRevokeAllOthers = async () => {
    setRevokingAll(true)
    setActionError(null)
    let errorCount = 0
    for (const session of otherSessions) {
      try {
        await revokeMutation.mutateAsync(session.session_id)
      } catch {
        errorCount++
      }
    }
    setRevokingAll(false)
    setShowConfirmAll(false)
    if (errorCount > 0) {
      setActionError(`${errorCount} session(s) n'ont pas pu être révoquées`)
    }
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <PageHeader
          title="Sessions actives"
          subtitle="Tous les appareils connectés à votre espace"
        />
        <div className="flex items-center gap-3">
          {!isLoading && (
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
              <Users className="w-3.5 h-3.5" />
              {activeCount} active{activeCount !== 1 ? 's' : ''}
            </span>
          )}
          {canRevoke && otherSessions.length > 0 && (
            showConfirmAll ? (
              <div className="flex items-center gap-3">
                <span className="text-sm text-dark-400">
                  Déconnecter {otherSessions.length} session{otherSessions.length > 1 ? 's' : ''} ?
                </span>
                <button
                  onClick={handleRevokeAllOthers}
                  disabled={revokingAll}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50"
                >
                  {revokingAll ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
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
                <Trash2 className="w-3.5 h-3.5" />
                Tout déconnecter
              </button>
            )
          )}
        </div>
      </div>

      <ActionError message={actionError} onDismiss={() => setActionError(null)} />

      {/* Sessions list */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <SessionSkeleton key={i} />)}
        </div>
      ) : sessions.length === 0 ? (
        <div className="card p-8 text-center">
          <Monitor className="w-8 h-8 text-dark-400 mx-auto mb-3" />
          <p className="text-dark-400 text-sm">Aucune session active</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions
            .sort((a, b) => (b.is_current ? 1 : 0) - (a.is_current ? 1 : 0))
            .map((session) => {
              const { label, DeviceIcon } = parseUserAgent(session.user_agent)
              const isCurrent = !!session.is_current

              return (
                <div
                  key={session.session_id}
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
                            Vous
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

                    {/* Action */}
                    {canRevoke && !isCurrent && (
                      <button
                        onClick={() => handleRevoke(session.session_id)}
                        disabled={revokingId === session.session_id}
                        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-red-400 hover:bg-red-500/10 rounded-lg transition-colors shrink-0 min-h-[44px]"
                        title="Révoquer cette session"
                      >
                        {revokingId === session.session_id
                          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          : <Trash2 className="w-3.5 h-3.5" />
                        }
                        <span className="hidden sm:inline">Révoquer</span>
                      </button>
                    )}
                  </div>
                </div>
              )
            })
          }
        </div>
      )}
    </div>
  )
}
