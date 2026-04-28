import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { Bell, Plus, Clock, CheckCircle, XCircle, Send } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import { useRelances, useScheduleRelance, useCancelRelance, useMarkRelanceSent } from '@/api/queries/useRelances'
import { useInvoicesList } from '@/api/queries/useInvoices'
import { Modal } from '@shared/components/ui/Modal'
import { SwipeActions } from '@shared/components/ui/SwipeActions'
import type { RelanceChannel } from '@/types/relance'
import { RELANCE_CHANNEL_LABELS } from '@/lib/constants'

// ── Badges statut ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  if (status === 'scheduled')
    return (
      <span className="inline-flex items-center gap-1 text-xs bg-amber-900/30 text-amber-400 border border-amber-700/30 rounded-full px-2 py-0.5">
        <Clock className="w-3 h-3" /> Planifiée
      </span>
    )
  if (status === 'sent')
    return (
      <span className="inline-flex items-center gap-1 text-xs bg-green-900/30 text-green-400 border border-green-700/30 rounded-full px-2 py-0.5">
        <CheckCircle className="w-3 h-3" /> Envoyée
      </span>
    )
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-dark-900 text-dark-400 border border-dark-600 rounded-full px-2 py-0.5">
      <XCircle className="w-3 h-3" /> Annulée
    </span>
  )
}

// ── Modal planification ──────────────────────────────────────────────────────

interface ScheduleModalProps {
  isOpen: boolean
  onClose: () => void
}

function ScheduleModal({ isOpen, onClose }: ScheduleModalProps) {
  const schedule = useScheduleRelance()
  // Ne charger que les factures impayées (overdue + sent), pas toutes
  const { data: invoicesData } = useInvoicesList({ limit: 50, status: 'overdue' })
  const { data: invoicesSentData } = useInvoicesList({ limit: 50, status: 'sent' })
  const invoices = [...(invoicesData?.items ?? []), ...(invoicesSentData?.items ?? [])]

  const [invoiceId, setInvoiceId] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [channel, setChannel] = useState<RelanceChannel>('email')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const handleClose = () => {
    setInvoiceId(''); setScheduledAt(''); setChannel('email'); setMessage(''); setError('')
    onClose()
  }

  const handleSubmit = async () => {
    if (!invoiceId) { setError('Sélectionnez une facture.'); return }
    if (!scheduledAt) { setError('Choisissez une date.'); return }
    setError('')
    try {
      await schedule.mutateAsync({
        invoice_id: Number(invoiceId),
        scheduled_at: new Date(scheduledAt).toISOString(),
        channel,
        message: message.trim() || undefined,
      })
      handleClose()
    } catch (err) {
      setError(
        normalizeError(err).message || 'Erreur lors de la planification.'
      )
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Planifier une relance"
      footer={
        <div className="flex justify-end gap-4">
          <button onClick={handleClose} className="px-4 py-2 text-sm text-dark-300 hover:text-dark-50">
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={schedule.isPending}
            className="px-4 py-2 text-sm bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium rounded-lg disabled:opacity-50"
          >
            {schedule.isPending ? 'Planification…' : 'Planifier'}
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {error && (
          <p className="text-red-400 text-sm bg-red-900/20 border border-red-700/30 rounded-lg px-4 py-2">
            {error}
          </p>
        )}

        <div>
          <label className="block text-sm text-dark-300 mb-1">Facture *</label>
          <select
            value={invoiceId}
            onChange={(e) => setInvoiceId(e.target.value)}
            className="input"
          >
            <option value="">— Sélectionner —</option>
            {invoices.map((inv) => (
              <option key={inv.id} value={inv.id}>
                {inv.invoice_number} — {inv.customer_name ?? `Facture #${inv.id}`}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-1">Date d'envoi *</label>
          <input
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-1">Canal</label>
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value as RelanceChannel)}
            className="input"
          >
            <option value="email">Email</option>
            <option value="sms">SMS</option>
            <option value="push">Push</option>
          </select>
        </div>

        <div>
          <label className="block text-sm text-dark-300 mb-1">
            Message personnalisé <span className="text-dark-500 font-normal">(optionnel)</span>
          </label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            placeholder="Laissez vide pour utiliser le message par défaut…"
            className="input resize-none"
          />
        </div>
      </div>
    </Modal>
  )
}

// ── Page principale ──────────────────────────────────────────────────────────

const STATUS_FILTER = ['all', 'scheduled', 'sent', 'cancelled'] as const
type StatusFilter = (typeof STATUS_FILTER)[number]

export default function RelancesPlanifieesPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [scheduleOpen, setScheduleOpen] = useState(false)

  const { data: relancesData, isLoading } = useRelances()
  const relances = relancesData?.items ?? []
  const cancelRelance = useCancelRelance()
  const markSent = useMarkRelanceSent()

  const filtered = statusFilter === 'all'
    ? relances
    : relances.filter((r) => r.status === statusFilter)

  const scheduled = relances.filter((r) => r.status === 'scheduled').length

  const handleCancel = (id: number) => cancelRelance.mutate(id)
  const handleMarkSent = (id: number) => markSent.mutate(id)

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <Bell className="w-6 h-6 text-gold-400" />
          <PageHeader title="Relances" />
          {scheduled > 0 && (
            <span className="text-xs bg-amber-900/30 text-amber-400 border border-amber-700/30 rounded-full px-2 py-0.5">
              {scheduled} planifiée{scheduled > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <button
          onClick={() => setScheduleOpen(true)}
          className="flex items-center gap-2 bg-gold-500 hover:bg-gold-600 text-dark-900 font-medium text-sm px-4 py-2 rounded-lg"
        >
          <Plus className="w-4 h-4" />
          Planifier une relance
        </button>
      </div>

      {/* Filtres statut */}
      <div className="flex items-center gap-2 flex-wrap">
        {STATUS_FILTER.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`text-xs px-4 py-1.5 rounded-full border transition-colors ${
              statusFilter === s
                ? 'bg-gold-500 text-dark-900 border-gold-500 font-medium'
                : 'bg-dark-900 text-dark-300 border-dark-600 hover:border-dark-500'
            }`}
          >
            {s === 'all' ? 'Toutes' : s === 'scheduled' ? 'Planifiées' : s === 'sent' ? 'Envoyées' : 'Annulées'}
          </button>
        ))}
      </div>

      {/* Liste */}
      {isLoading ? (
        <div className="card divide-y divide-dark-600 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-4">
              <div className="flex-1 space-y-2">
                <div className="h-3 skel rounded w-40" />
                <div className="h-2 skel rounded w-56" />
              </div>
              <div className="h-5 skel rounded w-20 shrink-0" />
              <div className="h-3 skel rounded w-24 shrink-0" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <Bell className="w-10 h-10 text-dark-500 mx-auto mb-4" />
          <p className="font-medium">Aucune relance</p>
          <p className="text-dark-400 text-sm mt-1">
            {statusFilter === 'all'
              ? 'Planifiez des relances sur vos factures en retard.'
              : `Aucune relance au statut "${statusFilter}".`}
          </p>
        </div>
      ) : (
        <div className="card divide-y divide-dark-600">
          {filtered.map((r) => (
            <SwipeActions
              key={r.id}
              actions={r.status === 'scheduled' ? [
                {
                  label: 'Envoyée',
                  icon: <Send className="w-5 h-5" />,
                  color: 'bg-green-600',
                  onClick: () => handleMarkSent(r.id),
                },
                {
                  label: 'Annuler',
                  icon: <XCircle className="w-5 h-5" />,
                  color: 'bg-red-600',
                  onClick: () => handleCancel(r.id),
                },
              ] : []}
            >
              <div className="flex items-start justify-between px-4 py-4 gap-4">
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium">Facture #{r.invoice_id}</span>
                    <StatusBadge status={r.status} />
                    <span className="text-dark-500 text-xs">{RELANCE_CHANNEL_LABELS[r.channel] ?? r.channel}</span>
                  </div>
                  <p className="text-dark-400 text-xs">
                    Planifiée : {new Date(r.scheduled_at).toLocaleString('fr-FR')}
                  </p>
                  {r.sent_at && (
                    <p className="text-green-400 text-xs">
                      Envoyée : {new Date(r.sent_at).toLocaleString('fr-FR')}
                    </p>
                  )}
                  {r.cancelled_at && (
                    <p className="text-dark-400 text-xs">
                      Annulée : {new Date(r.cancelled_at).toLocaleString('fr-FR')}
                    </p>
                  )}
                  {r.message && (
                    <p className="text-dark-400 text-xs italic truncate max-w-xs" title={r.message}>
                      "{r.message}"
                    </p>
                  )}
                </div>

                {/* Actions desktop — uniquement pour relances planifiées */}
                {r.status === 'scheduled' && (
                  <div className="hidden sm:flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleMarkSent(r.id)}
                      disabled={markSent.isPending}
                      className="flex items-center gap-1.5 text-xs text-green-400 hover:text-green-300 disabled:opacity-50"
                      title="Marquer comme envoyée"
                    >
                      <Send className="w-3.5 h-3.5" />
                      Marquer envoyée
                    </button>
                    <button
                      onClick={() => handleCancel(r.id)}
                      disabled={cancelRelance.isPending}
                      className="text-xs text-dark-400 hover:text-red-400 disabled:opacity-50"
                      title="Annuler"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            </SwipeActions>
          ))}
        </div>
      )}

      {scheduleOpen && <ScheduleModal isOpen onClose={() => setScheduleOpen(false)} />}
    </div>
  )
}
