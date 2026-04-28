import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Plus, ClipboardList, Eye, X } from 'lucide-react'
import { SubNav } from '@/layout/SubNav'
import { useOrderDetail, useOrdersList } from '@/api/queries/useOrders'
import { DomainStatusBadge } from '@shared/components/ui'
import { formatCents } from '@/lib/utils'
import { parseDateLocal } from '@/utils/date'
import type { OrderStatus, OrderType } from '@/types/order'

const COMMANDES_NAV = [
  { label: 'Tout', href: '/commandes' },
  { label: 'Devis', href: '/devis' },
  { label: 'Réservations', href: '/reservations' },
]

const STATUS_OPTIONS: { value: OrderStatus | ''; label: string }[] = [
  { value: '', label: 'Tous statuts' },
  { value: 'draft', label: 'Brouillon' },
  { value: 'sent', label: 'Envoyé' },
  { value: 'accepted', label: 'Accepté' },
  { value: 'confirmed', label: 'Confirmé' },
  { value: 'in_progress', label: 'En cours' },
  { value: 'returning', label: 'Retour' },
  { value: 'closed', label: 'Clôturé' },
  { value: 'cancelled', label: 'Annulé' },
]

const TYPE_LABELS: Record<OrderType, string> = {
  devis: 'Devis',
  reservation: 'Résa',
  vente: 'Vente',
}

const TYPE_COLORS: Record<OrderType, string> = {
  devis: 'text-primary-400',
  reservation: 'text-gold-400',
  vente: 'text-green-400',
}

const PAGE_SIZE = 50

export default function CommandesListPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<OrderStatus | ''>('')
  const [page, setPage] = useState(1)
  const [previewTarget, setPreviewTarget] = useState<{ type: OrderType; id: number } | null>(null)

  const { data, isLoading, isError, refetch } = useOrdersList({
    skip: (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(status ? { status } : {}),
  })

  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const previewOrderType: OrderType = previewTarget?.type ?? 'devis'
  const {
    data: previewDetail,
    isLoading: previewLoading,
    isError: previewError,
    refetch: refetchPreview,
  } = useOrderDetail(previewOrderType, previewTarget?.id ?? null)

  const handleRowClick = (type: OrderType, id: number) => {
    const routes: Record<string, string> = {
      devis: `/devis/${id}`,
      reservation: `/reservations/${id}/phases`,
    }
    navigate({ to: routes[type] as never })
  }

  return (
    <div className="min-h-screen">
      <SubNav items={COMMANDES_NAV} />

      <div className="px-4 pt-4 pb-24">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2 min-w-0">
              <ClipboardList className="w-5 h-5 text-primary-400" />
              Commandes
            </h1>
            {data && (
              <p className="text-sm text-dark-400 mt-0.5">{total} commandes</p>
            )}
          </div>
          <button
            onClick={() => navigate({ to: '/devis/new' })}
            className="flex items-center gap-1.5 bg-gold-500 hover:bg-gold-600 text-dark-900 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Nouveau
          </button>
        </div>

        {/* Filtre statut */}
        <div className="flex gap-2 flex-wrap pb-2 mb-4 lg:flex-nowrap lg:overflow-x-auto lg:scrollbar-hide">
          {STATUS_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => { setStatus(opt.value as OrderStatus | ''); setPage(1) }}
              className={`flex-shrink-0 text-xs px-4 py-1.5 rounded-full border transition-colors ${
                status === opt.value
                  ? 'bg-gold-500 border-gold-500 text-dark-900 font-medium'
                  : 'border-dark-600 text-dark-400 hover:border-dark-500'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Liste */}
        {isLoading && (
          <div className="space-y-2 animate-pulse">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="card p-4 flex items-center gap-4">
                <div className="flex-1 space-y-2">
                  <div className="h-3 skel rounded w-40" />
                  <div className="h-2 skel rounded w-56" />
                </div>
                <div className="h-5 skel rounded w-20 shrink-0" />
                <div className="h-3 skel rounded w-16 shrink-0" />
              </div>
            ))}
          </div>
        )}
        {isError && (
          <div className="card text-center py-12 space-y-4">
            <p className="text-red-400">Impossible de charger les commandes.</p>
            <button onClick={() => refetch()} className="btn-secondary text-sm">
              Réessayer
            </button>
          </div>
        )}
        {data && data.items.length === 0 && (
          <div className="card text-center py-12 space-y-4">
            <p className="text-dark-500">Aucune commande{status ? ' pour ce statut' : ''}.</p>
            {!status && (
              <button
                onClick={() => navigate({ to: '/devis/new' })}
                className="btn-primary text-sm"
              >
                Créer un devis
              </button>
            )}
          </div>
        )}
        {data && data.items.length > 0 && (
          <div className="space-y-2">
            {data.items.map(item => (
              <div
                key={`${item.type}-${item.id}`}
                className="w-full card px-4 py-4 hover:border-dark-500 transition-colors"
              >
                <button
                  onClick={() => handleRowClick(item.type, item.id)}
                  className="w-full text-left"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs font-medium ${TYPE_COLORS[item.type]}`}>
                          {TYPE_LABELS[item.type]}
                        </span>
                        <span className="text-sm font-mono text-dark-300 truncate">
                          {item.reference}
                        </span>
                      </div>
                      {item.customer_name && (
                        <p className="text-sm font-medium truncate">{item.customer_name}</p>
                      )}
                      {item.event_date && (
                        <p className="text-xs text-dark-500 mt-0.5">
                          {parseDateLocal(item.event_date).toLocaleDateString('fr-FR')}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                      <DomainStatusBadge status={item.status} />
                      {item.total_cents != null && (
                        <span className="text-sm font-semibold">
                          {formatCents(item.total_cents)}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
                <div className="mt-4 pt-4 border-t border-dark-600 flex justify-end">
                  <button
                    onClick={() => setPreviewTarget({ type: item.type, id: item.id })}
                    className="inline-flex items-center gap-2 text-xs text-dark-300 hover:text-dark-50 px-4 py-2 rounded-lg border border-dark-600 hover:border-dark-500"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Aperçu
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {previewTarget && (
          <>
            <button
              type="button"
              aria-label="Fermer l'aperçu"
              className="fixed inset-0 bg-black/50 z-40"
              onClick={() => setPreviewTarget(null)}
            />
            <div className="fixed inset-x-0 bottom-0 z-50 border-t border-dark-600 bg-dark-900 rounded-t-2xl max-h-[80vh] overflow-y-auto">
              <div className="px-4 pt-4 pb-4 space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-base font-semibold">Aperçu commande</h2>
                  <button
                    type="button"
                    onClick={() => setPreviewTarget(null)}
                    className="p-2 rounded-lg hover:bg-dark-600 text-dark-300"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {previewLoading && (
                  <div className="card p-4 animate-pulse space-y-2">
                    <div className="h-3 skel rounded w-40" />
                    <div className="h-3 skel rounded w-56" />
                    <div className="h-3 skel rounded w-48" />
                  </div>
                )}

                {previewError && (
                  <div className="card p-4 space-y-4">
                    <p className="text-sm text-red-400">Impossible de charger le détail de la commande.</p>
                    <button onClick={() => refetchPreview()} className="btn-secondary text-sm">
                      Réessayer
                    </button>
                  </div>
                )}

                {previewDetail && (
                  <>
                    <div className="card space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className={`text-xs font-medium ${TYPE_COLORS[previewDetail.type]}`}>
                          {TYPE_LABELS[previewDetail.type]}
                        </span>
                        <DomainStatusBadge status={previewDetail.status} />
                      </div>
                      <p className="text-sm font-mono text-dark-300">{previewDetail.reference}</p>
                      {previewDetail.customer_name && (
                        <p className="text-sm">{previewDetail.customer_name}</p>
                      )}
                      <div className="text-xs text-dark-500 flex gap-4 flex-wrap">
                        {previewDetail.event_date && (
                          <span>
                            Date: {parseDateLocal(previewDetail.event_date).toLocaleDateString('fr-FR')}
                          </span>
                        )}
                        {previewDetail.total_cents != null && (
                          <span>Total: {formatCents(previewDetail.total_cents)}</span>
                        )}
                      </div>
                      {previewDetail.event_location && (
                        <p className="text-xs text-dark-400">Lieu: {previewDetail.event_location}</p>
                      )}
                      {previewDetail.notes && (
                        <p className="text-xs text-dark-400">Notes: {previewDetail.notes}</p>
                      )}
                    </div>

                    <div className="card p-0 overflow-hidden">
                      <div className="px-4 py-4 border-b border-dark-600 text-xs uppercase tracking-wide text-dark-400">
                        Lignes
                      </div>
                      {previewDetail.lines.length === 0 ? (
                        <p className="px-4 py-4 text-sm text-dark-500">Aucune ligne.</p>
                      ) : (
                        <div className="divide-y divide-dark-600">
                          {previewDetail.lines.map((line, idx) => (
                            <div key={`${line.label}-${idx}`} className="px-4 py-4 text-sm">
                              <p className="font-medium">{line.label}</p>
                              <p className="text-xs text-dark-500">
                                {line.quantity} x {formatCents(line.unit_price_cents)} = {formatCents(line.subtotal_cents)}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {previewDetail.actions.length > 0 && (
                      <div className="card">
                        <p className="text-xs uppercase tracking-wide text-dark-400 mb-2">Actions possibles</p>
                        <div className="flex flex-wrap gap-2">
                          {previewDetail.actions.map((action) => (
                            <span
                              key={action}
                              className="text-xs px-2 py-0.5 rounded-full border border-dark-600 text-dark-300"
                            >
                              {action}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <button
                      onClick={() => {
                        setPreviewTarget(null)
                        handleRowClick(previewDetail.type, previewDetail.id)
                      }}
                      className="w-full btn-primary text-sm"
                    >
                      Ouvrir la commande
                    </button>
                  </>
                )}
              </div>
            </div>
          </>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-4 mt-6">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-4 py-1.5 bg-dark-900 rounded-lg text-sm disabled:opacity-40 text-dark-300"
            >
              ‹ Préc.
            </button>
            <span className="text-sm text-dark-400">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-4 py-1.5 bg-dark-900 rounded-lg text-sm disabled:opacity-40 text-dark-300"
            >
              Suiv. ›
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
