import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useToast } from '@shared/components/ui/Toast'
import { epicerieApi } from '@/api/epicerie'
import TransferCard from '@/components/transferts/TransferCard'
import TransferConfirmModal from '@/components/transferts/TransferConfirmModal'
import TransferStats from '@/components/transferts/TransferStats'
import { Pagination } from '@/components/Pagination'
import type { InternalTransferRead } from '@/types/epicerie-v2'
import { normalizeError } from '@shared/errors/normalizer'
import { getTransferDisplayTtcCts } from '@/utils/transferts'

const FILTERS = [
  { label: 'Tous', value: null },
  { label: 'En attente', value: 'PENDING' },
  { label: 'Validés', value: 'VALIDATED' },
  { label: 'Annulés', value: 'CANCELLED' },
] as const

const TRANSFERTS_PER_PAGE = 20

function ListSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4].map(index => (
        <div key={index} className="animate-pulse rounded-xl border border-slate-200 p-4">
          <div className="flex items-center gap-4">
            <div className="h-2.5 w-2.5 rounded-full bg-slate-200" />
            <div className="flex-1">
              <div className="mb-2 h-4 w-40 rounded bg-slate-200" />
              <div className="h-3 w-32 rounded bg-slate-100" />
            </div>
            <div className="h-11 w-24 rounded-lg bg-slate-200" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function TransfertsPage() {
  const qc = useQueryClient()
  const { success: toastOk, error: toastErr } = useToast()
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [validatingId, setValidatingId] = useState<number | null>(null)
  const [confirmTarget, setConfirmTarget] = useState<InternalTransferRead | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['epicerie-transferts', statusFilter, page],
    queryFn: () => epicerieApi.listTransferts({
      status: statusFilter || undefined,
      page,
      per_page: TRANSFERTS_PER_PAGE,
    }),
    staleTime: 15_000,
    placeholderData: prev => prev,
  })

  function handleFilterChange(value: string | null) {
    setStatusFilter(value)
    setPage(1)
  }

  const { data: allTransfers } = useQuery({
    queryKey: ['epicerie-transferts', 'all'],
    queryFn: () => epicerieApi.listTransferts({ per_page: 100 }),
    staleTime: 60_000,
  })

  const validateMut = useMutation({
    mutationFn: (id: number) => epicerieApi.validerTransfert(id),
    onMutate: id => setValidatingId(id),
    onSuccess: transfer => {
      toastOk('Transfert validé', transfer.reference || `TRF-${transfer.id}`)
      setError(null)
      setConfirmTarget(null)
      setValidatingId(null)
      qc.invalidateQueries({ queryKey: ['epicerie-transferts'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock-list'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock-stats'] })
    },
    onError: err => {
      const message = normalizeError(err).message || 'Erreur lors de la validation'
      setError(message)
      setValidatingId(null)
      setConfirmTarget(null)
      toastErr('Erreur', message)
    },
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Transferts internes</h1>
          <p className="mt-0.5 text-sm text-slate-500">Épicerie → Restaurant</p>
        </div>

        <Link
          to="/transferts/nouveau"
          className="inline-flex min-h-11 items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-500"
        >
          <Plus className="h-4 w-4" />
          Nouveau transfert
        </Link>
      </div>

      <TransferStats transfers={allTransfers?.items ?? []} />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
          {error}
          <button type="button" onClick={() => setError(null)} className="ml-2 underline">
            fermer
          </button>
        </div>
      )}

      <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
        {FILTERS.map(filter => (
          <button
            key={filter.label}
            type="button"
            onClick={() => handleFilterChange(filter.value)}
            className={`flex-1 rounded px-3 py-2 text-sm font-medium transition-colors ${
              statusFilter === filter.value
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <ListSkeleton />
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center">
          <div className="mb-4 text-5xl">📦</div>
          <h3 className="mb-2 text-lg font-semibold text-slate-700">
            {statusFilter ? 'Aucun transfert trouvé' : 'Aucun transfert pour le moment'}
          </h3>
          <p className="mb-4 text-sm text-slate-500">
            {statusFilter ? 'Essayez un autre filtre.' : 'Préparez le prochain transfert pour le restaurant.'}
          </p>
          {!statusFilter && (
            <Link
              to="/transferts/nouveau"
              className="inline-flex min-h-11 items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-500"
            >
              <Plus className="h-4 w-4" />
              Créer un transfert
            </Link>
          )}
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {items.map(transfer => (
              <TransferCard
                key={transfer.id}
                transfer={transfer}
                onQuickValidate={setConfirmTarget}
                isValidating={validatingId === transfer.id}
              />
            ))}
          </div>
          <Pagination
            page={page}
            total={total}
            perPage={TRANSFERTS_PER_PAGE}
            onPageChange={setPage}
            itemLabel="transfert"
          />
        </>
      )}

      {confirmTarget && (
        <TransferConfirmModal
          nbArticles={confirmTarget.lignes.length}
          totalTtcCts={getTransferDisplayTtcCts(confirmTarget)}
          loading={validateMut.isPending}
          onConfirm={() => validateMut.mutate(confirmTarget.id)}
          onCancel={() => {
            if (!validateMut.isPending) {
              setConfirmTarget(null)
            }
          }}
        />
      )}
    </div>
  )
}
