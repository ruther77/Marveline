import { useState } from 'react'
import { useParams, useNavigate } from '@tanstack/react-router'
import { useCustomerHistory, useRelancesByCustomer, useCancelRelance, useMarkRelanceSent } from '@/api/queries'
import { useCustomerRFMProfile } from '@/api/queries/useCustomers'
import { useLoyaltyByCustomer } from '@/api/queries/useLoyalty'
import { CustomerFormModal } from './components/CustomerFormModal'
import { ScheduleRelanceModal } from './components/ScheduleRelanceModal'
import { ActionError } from '@shared/components/ui/ActionError'
import { normalizeError } from '@shared/errors/normalizer'
import { CUSTOMER_TYPE_LABELS as TYPE_LABELS } from '@/lib/constants'
import {
  User,
  Mail,
  Phone,
  MapPin,
  Calendar,
  Euro,
  FileText,
  ArrowLeft,
  Pencil,
  Bell,
  StickyNote,
  CalendarPlus,
  Heart,
  Award,
  Star,
  TrendingUp,
} from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { StatCard } from '@shared/components/ui/Card'
import { PageHeader } from '@shared/components/ui/Breadcrumb'
import { formatCents, formatDate } from '@/lib/utils'
import { DomainStatusBadge } from '@shared/components/ui'

export default function CustomerDetailPage() {
  const { id } = useParams({ strict: false })
  const navigate = useNavigate()
  const customerId = Number(id)

  const { data, isLoading, isError, refetch } = useCustomerHistory(customerId || null)
  const { data: relancesData } = useRelancesByCustomer(customerId)
  const { data: loyalty } = useLoyaltyByCustomer(customerId || null)
  const { data: rfm } = useCustomerRFMProfile(customerId, customerId > 0)
  const relances = relancesData?.items ?? []
  const cancelRelance = useCancelRelance()
  const markSentRelance = useMarkRelanceSent()
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [scheduleRelanceOpen, setScheduleRelanceOpen] = useState(false)
  const [relanceError, setRelanceError] = useState<string | null>(null)

  const errHandler = (err: unknown) => setRelanceError(
    normalizeError(err).message || 'Une erreur est survenue'
  )

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="card p-6 space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 skel rounded-full" />
            <div className="space-y-2">
              <div className="h-4 skel rounded w-40" />
              <div className="h-3 skel rounded w-28" />
            </div>
          </div>
        </div>
        <div className="card divide-y divide-dark-600">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex justify-between px-4 py-4">
              <div className="h-3 skel rounded w-24" />
              <div className="h-3 skel rounded w-36" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate({ to: '/customers' })}
          className="flex items-center gap-2 text-sm text-dark-400 hover:text-dark-200"
        >
          <ArrowLeft className="w-4 h-4" /> Retour aux clients
        </button>
        <div className="card p-6 text-center space-y-4">
          <p className="text-red-400">Erreur lors du chargement du client.</p>
          <button onClick={() => refetch()} className="btn-secondary">
            Réessayer
          </button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => navigate({ to: '/customers' })}
          className="flex items-center gap-2 text-sm text-dark-400 hover:text-dark-200"
        >
          <ArrowLeft className="w-4 h-4" /> Retour aux clients
        </button>
        <p className="text-red-400">Client introuvable.</p>
      </div>
    )
  }

  const { customer, reservations, invoices, stats } = data

  return (
    <div className="space-y-6">
      <ActionError message={relanceError} onDismiss={() => setRelanceError(null)} />

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="mb-2">
            <BackButton label="Retour" />
          </div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary-500/20 text-primary-400 flex items-center justify-center font-semibold text-sm shrink-0">
              {customer.display_name?.split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()}
            </div>
            <PageHeader
              title={customer.display_name}
              subtitle={TYPE_LABELS[customer.customer_type] ?? customer.customer_type}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={`mailto:${customer.email}`}
            className="btn-ghost text-sm flex items-center gap-1.5"
          >
            <Mail className="h-4 w-4" /> Message
          </a>
          <button
            onClick={() => navigate({ to: '/devis/new', search: { customer_id: customer.id } })}
            className="btn-primary text-sm flex items-center gap-1.5 whitespace-nowrap"
          >
            <CalendarPlus className="h-4 w-4" /> Nouveau devis
          </button>
          <button
            onClick={() => setScheduleRelanceOpen(true)}
            className="btn-secondary text-sm flex items-center gap-1.5"
          >
            <Bell className="w-4 h-4" /> Planifier une relance
          </button>
          <button
            onClick={() => setEditModalOpen(true)}
            className="btn-secondary flex items-center gap-2"
          >
            <Pencil className="w-4 h-4" /> Modifier
          </button>
        </div>
      </div>

      {/* Infos client */}
      <div className="card p-6">
        <h2 className="mb-4 text-sm font-semibold text-dark-400 uppercase tracking-wide">Informations</h2>
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex items-center gap-4">
            <Mail className="w-4 h-4 text-dark-500 shrink-0" />
            <div>
              <dt className="text-xs text-dark-400">Email</dt>
              <dd className="text-sm">{customer.email}</dd>
            </div>
          </div>
          {customer.phone && (
            <div className="flex items-center gap-4">
              <Phone className="w-4 h-4 text-dark-500 shrink-0" />
              <div>
                <dt className="text-xs text-dark-400">Téléphone</dt>
                <dd className="text-sm">{customer.phone}</dd>
              </div>
            </div>
          )}
          {customer.city && (
            <div className="flex items-center gap-4">
              <MapPin className="w-4 h-4 text-dark-500 shrink-0" />
              <div>
                <dt className="text-xs text-dark-400">Ville</dt>
                <dd className="text-sm">{customer.city}{customer.postal_code ? ` (${customer.postal_code})` : ''}</dd>
              </div>
            </div>
          )}
          <div className="flex items-center gap-4">
            <User className="w-4 h-4 text-dark-500 shrink-0" />
            <div>
              <dt className="text-xs text-dark-400">Membre depuis</dt>
              <dd className="text-sm">{new Date(customer.created_at).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })}</dd>
            </div>
          </div>
        </dl>
      </div>

      {/* Quick-links */}
      <div className="flex gap-2 flex-wrap">
        {[
          { label: 'Réservations', href: '#reservations' },
          { label: 'Factures', href: '#factures' },
          { label: 'Devis', href: `/devis?customer_id=${customer.id}` },
        ].map((link) => (
          <a
            key={link.label}
            href={link.href}
            className="text-xs px-4 py-1.5 rounded-full border border-dark-600 text-dark-300 hover:border-primary-400 hover:text-primary-400 transition-colors"
          >
            {link.label}
          </a>
        ))}
      </div>

      {/* Note interne */}
      {customer.notes && (
        <div className="card p-4">
          <h3 className="text-sm font-medium text-dark-400 mb-1 flex items-center gap-1.5">
            <StickyNote className="h-4 w-4" /> Note interne
            <span className="text-xs text-dark-500">(non visible par le client)</span>
          </h3>
          <p className="text-sm text-dark-200 whitespace-pre-wrap">{customer.notes}</p>
        </div>
      )}

      {/* Stats KPI */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          title="Total réservations"
          value={stats.total_reservations}
          icon={<Calendar className="w-5 h-5" />}
        />
        <StatCard
          title="CA total"
          value={formatCents(stats.total_revenue_cents)}
          icon={<Euro className="w-5 h-5" />}
          trend="up"
        />
        <StatCard
          title="Dernière prestation"
          value={formatDate(stats.last_event_date)}
          icon={<Calendar className="w-5 h-5" />}
        />
      </div>

      {/* Profil RFM */}
      {rfm && (
        <div className="card p-6 space-y-4">
          <h2 className="text-sm font-semibold text-dark-400 uppercase tracking-wide flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-primary-400" /> Analyse RFM
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="card px-4 py-3">
              <div className="text-[11px] text-dark-500">Segment</div>
              <div className={`text-sm font-bold mt-1 ${
                rfm.segment === 'Champions' ? 'text-gold-400'
                : rfm.segment === 'Loyal' ? 'text-primary-400'
                : rfm.segment === 'Potential' ? 'text-blue-400'
                : rfm.segment === 'At Risk' ? 'text-yellow-400'
                : rfm.segment === 'Lost' ? 'text-red-400'
                : 'text-dark-300'
              }`}>{rfm.segment}</div>
            </div>
            <div className="card px-4 py-3">
              <div className="text-[11px] text-dark-500">Récence</div>
              <div className="text-sm font-bold mt-1">
                {rfm.recency_days === 9999 ? 'Jamais' : `${rfm.recency_days} j`}
              </div>
            </div>
            <div className="card px-4 py-3">
              <div className="text-[11px] text-dark-500">Fréquence</div>
              <div className="text-sm font-bold mt-1">
                {rfm.frequency} résa{rfm.frequency > 1 ? 's' : ''}
              </div>
            </div>
            <div className="card px-4 py-3">
              <div className="text-[11px] text-dark-500">Total payé</div>
              <div className="text-sm font-bold mt-1 text-gold-400">
                {formatCents(rfm.monetary_cents)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Fidélité */}
      {loyalty && (
        <div className="card p-6 space-y-4">
          <h2 className="text-sm font-semibold text-dark-400 uppercase tracking-wide flex items-center gap-2">
            <Heart className="w-4 h-4 text-pink-400" /> Programme fidélité
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="card px-4 py-3">
              <div className="text-[11px] text-dark-500 flex items-center gap-1"><Award className="w-3 h-3" /> Palier</div>
              <div className="text-sm font-bold mt-1 capitalize">{loyalty.current_tier}</div>
            </div>
            <div className="card px-4 py-3">
              <div className="text-[11px] text-dark-500 flex items-center gap-1"><Star className="w-3 h-3" /> Points</div>
              <div className="text-sm font-bold mt-1 text-primary-400">{loyalty.points_balance.toLocaleString()}</div>
            </div>
            <div className="card px-4 py-3">
              <div className="text-[11px] text-dark-500 flex items-center gap-1"><TrendingUp className="w-3 h-3" /> CA cumulé</div>
              <div className="text-sm font-bold mt-1">{(loyalty.cumulative_ca_cents / 100).toFixed(0)} EUR</div>
            </div>
            <div className="card px-4 py-3">
              <div className="text-[11px] text-dark-500 flex items-center gap-1"><Euro className="w-3 h-3" /> Remise</div>
              <div className="text-sm font-bold mt-1 text-green-400">{loyalty.discount_percent}%</div>
            </div>
          </div>
          {loyalty.available_rewards.length > 0 && (
            <div>
              <p className="text-xs text-dark-400 mb-2">Récompenses disponibles</p>
              <div className="flex flex-wrap gap-2">
                {loyalty.available_rewards.map((r) => (
                  <span key={r.reward_id} className="text-xs px-3 py-1 rounded-full bg-primary-500/10 text-primary-400 border border-primary-500/20">
                    {r.name} ({r.points_cost} pts)
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Réservations */}
      <div className="card p-0 overflow-hidden">
        <div className="px-6 py-4 border-b border-dark-600">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Calendar className="w-4 h-4" /> Réservations ({reservations.length})
          </h2>
        </div>
        {reservations.length === 0 ? (
          <p className="px-6 py-4 text-sm text-dark-500">Aucune réservation.</p>
        ) : (
          <table className="min-w-full divide-y divide-dark-600 text-sm">
            <thead className="bg-dark-900">
              <tr>
                <th className="px-4 py-4 text-left font-medium text-dark-400">Référence</th>
                <th className="px-4 py-4 text-left font-medium text-dark-400">Date</th>
                <th className="px-4 py-4 text-left font-medium text-dark-400">Statut</th>
                <th className="px-4 py-4 text-right font-medium text-dark-400">Montant</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-600">
              {reservations.map((r) => (
                <tr key={r.id} className="hover:bg-dark-600">
                  <td className="px-4 py-4 font-mono text-xs text-dark-200">{r.reference}</td>
                  <td className="px-4 py-4 text-dark-200">{formatDate(r.event_date)}</td>
                  <td className="px-4 py-4">
                    <DomainStatusBadge status={r.status} />
                  </td>
                  <td className="px-4 py-4 text-right text-dark-200">{formatCents(r.total_amount_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Factures */}
      <div className="card p-0 overflow-hidden">
        <div className="px-6 py-4 border-b border-dark-600">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <FileText className="w-4 h-4" /> Factures ({invoices.length})
          </h2>
        </div>
        {invoices.length === 0 ? (
          <p className="px-6 py-4 text-sm text-dark-500">Aucune facture.</p>
        ) : (
          <table className="min-w-full divide-y divide-dark-600 text-sm">
            <thead className="bg-dark-900">
              <tr>
                <th className="px-4 py-4 text-left font-medium text-dark-400">Numéro</th>
                <th className="px-4 py-4 text-left font-medium text-dark-400">Statut</th>
                <th className="px-4 py-4 text-right font-medium text-dark-400">Total</th>
                <th className="px-4 py-4 text-right font-medium text-dark-400">Payé</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-600">
              {invoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-dark-600">
                  <td className="px-4 py-4 font-mono text-xs text-dark-200">{inv.invoice_number}</td>
                  <td className="px-4 py-4">
                    <DomainStatusBadge status={inv.status} />
                  </td>
                  <td className="px-4 py-4 text-right text-dark-200">{formatCents(inv.total_amount_cents)}</td>
                  <td className="px-4 py-4 text-right text-dark-200">{formatCents(inv.paid_amount_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {/* Relances */}
      <div className="card p-0 overflow-hidden">
        <div className="px-6 py-4 border-b border-dark-600">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Bell className="w-4 h-4" /> Relances planifiées ({relances.length})
          </h2>
        </div>
        {relances.length === 0 ? (
          <p className="px-6 py-4 text-sm text-dark-500">Aucune relance.</p>
        ) : (
          <table className="min-w-full divide-y divide-dark-600 text-sm">
            <thead className="bg-dark-900">
              <tr>
                <th className="px-4 py-4 text-left font-medium text-dark-400">Date planifiée</th>
                <th className="px-4 py-4 text-left font-medium text-dark-400">Canal</th>
                <th className="px-4 py-4 text-left font-medium text-dark-400">Statut</th>
                <th className="px-4 py-4 text-right font-medium text-dark-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-600">
              {relances.map((rel) => (
                <tr key={rel.id} className="hover:bg-dark-600">
                  <td className="px-4 py-4 text-dark-200">{formatDate(rel.scheduled_at)}</td>
                  <td className="px-4 py-4 text-dark-200 capitalize">{rel.channel}</td>
                  <td className="px-4 py-4">
                    <DomainStatusBadge status={rel.status} />
                  </td>
                  <td className="px-4 py-4 text-right space-x-2">
                    {rel.status === 'scheduled' && (
                      <>
                        <button
                          onClick={() => markSentRelance.mutate(rel.id, { onError: errHandler })}
                          className="text-xs text-green-400 hover:underline"
                        >
                          Marquer envoyée
                        </button>
                        <button
                          onClick={() => cancelRelance.mutate(rel.id, { onError: errHandler })}
                          className="text-xs text-red-400 hover:underline"
                        >
                          Annuler
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <CustomerFormModal
        isOpen={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        customer={customer}
        mode="edit"
      />
      <ScheduleRelanceModal
        isOpen={scheduleRelanceOpen}
        onClose={() => setScheduleRelanceOpen(false)}
        invoices={invoices}
      />
    </div>
  )
}
