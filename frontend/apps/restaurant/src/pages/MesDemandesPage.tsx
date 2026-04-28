// Route : /_app/mes-demandes
// Suivi des demandes de transfert envoyées à l'épicerie

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Package, Clock, CheckCircle, XCircle, Ban } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import type { TransferRequestRead, TransferRequestStatus } from '@/types/restaurant-v2'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

const STATUS_CONFIG: Record<TransferRequestStatus, { label: string; badge: string; icon: React.ReactNode }> = {
  PENDING:   { label: 'En attente',  badge: 'bg-amber-100 text-amber-700',   icon: <Clock className="h-3.5 w-3.5" /> },
  APPROVED:  { label: 'Approuvée',   badge: 'bg-emerald-100 text-emerald-700', icon: <CheckCircle className="h-3.5 w-3.5" /> },
  FULFILLED: { label: 'Traitée',     badge: 'bg-sky-100 text-sky-700',        icon: <CheckCircle className="h-3.5 w-3.5" /> },
  REJECTED:  { label: 'Refusée',     badge: 'bg-red-100 text-red-700',        icon: <XCircle className="h-3.5 w-3.5" /> },
  CANCELLED: { label: 'Annulée',     badge: 'bg-stone-100 text-stone-500',    icon: <Ban className="h-3.5 w-3.5" /> },
}

const FILTERS = [
  { label: 'Toutes',     value: 'all' },
  { label: 'En attente', value: 'PENDING' },
  { label: 'Approuvées', value: 'APPROVED' },
  { label: 'Refusées',   value: 'REJECTED' },
  { label: 'Annulées',   value: 'CANCELLED' },
]

// ─── DemandeCard ──────────────────────────────────────────────────────────────

function DemandeCard({ demande, onCancel, cancelling }: {
  demande: TransferRequestRead
  onCancel: (id: number) => void
  cancelling: boolean
}) {
  const cfg = STATUS_CONFIG[demande.status]
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-semibold ${cfg.badge}`}>
            {cfg.icon}
            {cfg.label}
          </span>
          <span className="text-[12px] text-stone-400">#{demande.id}</span>
        </div>
        <span className="text-[11px] text-stone-400 shrink-0">{fmtDate(demande.created_at)}</span>
      </div>

      <ul className="mt-3 space-y-1.5">
        {demande.lignes.map(l => (
          <li key={l.id} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-[13px]">
            <span className="font-medium text-stone-800">{l.designation}</span>
            <span className="text-stone-400 text-[12px]">{l.quantity} {l.unit}</span>
            {l.notes && <span className="text-stone-400 text-[11px] italic">{l.notes}</span>}
          </li>
        ))}
      </ul>

      {demande.notes && (
        <p className="mt-2 text-[12px] text-stone-500 italic border-t border-stone-100 pt-2">
          Note : {demande.notes}
        </p>
      )}

      {demande.status === 'REJECTED' && demande.rejection_reason && (
        <div className="mt-2 px-3 py-2 bg-red-50 border border-red-100 rounded-lg">
          <p className="text-[12px] text-red-600">
            <span className="font-semibold">Motif du refus :</span> {demande.rejection_reason}
          </p>
        </div>
      )}

      {demande.status === 'PENDING' && (
        <div className="mt-3 pt-3 border-t border-stone-100">
          <button
            onClick={() => onCancel(demande.id)}
            disabled={cancelling}
            className="text-[12px] text-stone-400 hover:text-red-600 disabled:opacity-50 transition-colors"
          >
            Annuler cette demande
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function DemandeSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[1, 2, 3].map(i => (
        <div key={i} className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="flex justify-between">
            <div className="h-6 w-28 bg-stone-100 rounded-full" />
            <div className="h-4 w-20 bg-stone-100 rounded" />
          </div>
          <div className="mt-3 space-y-2">
            <div className="h-4 w-3/4 bg-stone-100 rounded" />
            <div className="h-4 w-1/2 bg-stone-100 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MesDemandesPage() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState('all')
  const [cancelError, setCancelError] = useState<string | null>(null)
  const [cancellingId, setCancellingId] = useState<number | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['restaurant-transfer-requests', filter],
    queryFn: () => restaurantApi.listTransferRequests({
      status: filter === 'all' ? undefined : filter,
      per_page: 50,
    }),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const cancelMut = useMutation({
    mutationFn: (id: number) => restaurantApi.annulerDemandeTransfert(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-transfer-requests'] })
      setCancellingId(null)
    },
    onError: (err) => {
      setCancelError(normalizeError(err).message || "Erreur lors de l'annulation")
      setCancellingId(null)
    },
  })

  function handleCancel(id: number) {
    setCancellingId(id)
    setCancelError(null)
    cancelMut.mutate(id)
  }

  const items = data?.items ?? []

  return (
    <div className="flex flex-col min-h-0">
      <div className="px-5 sm:px-7 pt-6 pb-4 border-b border-stone-200 bg-white">
        <h1 className="text-[20px] font-bold text-stone-900 tracking-tight">Mes demandes</h1>
        <p className="text-[13px] text-stone-500 mt-0.5">
          Suivi de vos demandes de réassort envoyées à l'épicerie
        </p>
      </div>

      <div className="px-5 sm:px-7 py-3 border-b border-stone-100 bg-white flex gap-2 overflow-x-auto">
        {FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`shrink-0 px-3 py-1 rounded-full text-[12px] font-medium transition-colors ${
              filter === f.value
                ? 'bg-stone-900 text-white'
                : 'bg-stone-100 text-stone-500 hover:bg-stone-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-5 sm:px-7 py-4">
        {cancelError && (
          <div className="mb-3 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-[12px] text-red-600 flex items-center justify-between gap-2">
            {cancelError}
            <button onClick={() => setCancelError(null)} className="text-red-400 hover:text-red-700 shrink-0">✕</button>
          </div>
        )}

        {isLoading ? (
          <DemandeSkeleton />
        ) : isError ? (
          <div className="py-12 text-center text-stone-400 text-[13px]">Erreur de chargement</div>
        ) : items.length === 0 ? (
          <div className="py-16 flex flex-col items-center gap-3 text-center">
            <Package className="h-10 w-10 text-stone-200" />
            <p className="text-[14px] font-medium text-stone-600">Aucune demande</p>
            <p className="text-[12px] text-stone-400 max-w-xs">
              {filter === 'all'
                ? "Utilisez le bouton « Demander à l'épicerie » depuis la page Stock pour créer une demande."
                : 'Aucune demande dans cette catégorie.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map(d => (
              <DemandeCard
                key={d.id}
                demande={d}
                onCancel={handleCancel}
                cancelling={cancellingId === d.id && cancelMut.isPending}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
