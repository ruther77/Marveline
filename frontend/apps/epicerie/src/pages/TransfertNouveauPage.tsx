import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Search } from 'lucide-react'
import { useToast } from '@shared/components/ui/Toast'
import { epicerieApi } from '@/api/epicerie'
import TransferCart, { type TransferCartLine } from '@/components/transferts/TransferCart'
import TransferConfirmModal from '@/components/transferts/TransferConfirmModal'
import type { EpicerieStockRead, TransferLineCreate } from '@/types/epicerie-v2'
import { normalizeError } from '@shared/errors/normalizer'
import {
  DEFAULT_TRANSFER_TVA_PCT,
  getNextTransferReference,
  getTransferTtcCts,
  RESTAURANT_TENANT_ID,
} from '@/utils/transferts'

type SubmitMode = 'pending' | 'validate'

function CartSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-11 rounded-lg bg-slate-100" />
      <div className="h-64 rounded-2xl bg-slate-100" />
      <div className="h-24 rounded-xl bg-slate-100" />
    </div>
  )
}

export default function TransfertNouveauPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { success: toastOk, error: toastErr } = useToast()
  const [cart, setCart] = useState<TransferCartLine[]>([])
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [notes, setNotes] = useState('')
  const [reference, setReference] = useState('')
  const [referenceEdited, setReferenceEdited] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const trimmedSearch = search.trim()

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedSearch(trimmedSearch)
    }, 180)
    return () => window.clearTimeout(handle)
  }, [trimmedSearch])

  const { data: stockData, isLoading, isFetching } = useQuery({
    queryKey: ['epicerie-stock-list', 'transfer-search', debouncedSearch],
    queryFn: () => epicerieApi.listStock({
      per_page: debouncedSearch ? 20 : 12,
      search: debouncedSearch || undefined,
    }),
    staleTime: 60_000,
  })

  const { data: transfersData } = useQuery({
    queryKey: ['epicerie-transferts', 'reference-seed'],
    queryFn: () => epicerieApi.listTransferts({ per_page: 100 }),
    staleTime: 60_000,
  })

  const stock = stockData?.items ?? []
  const suggestedReference = useMemo(
    () => getNextTransferReference(transfersData?.items ?? []),
    [transfersData?.items],
  )

  useEffect(() => {
    if (!referenceEdited && suggestedReference) {
      setReference(suggestedReference)
    }
  }, [referenceEdited, suggestedReference])

  const cartIds = useMemo(() => new Set(cart.map(line => line.productId)), [cart])
  const filteredProducts = useMemo(() => {
    const candidates = stock.filter(item => !cartIds.has(item.produit_id))
    if (trimmedSearch.length > 0) {
      return [...candidates]
        .sort((left, right) => {
          const availabilityOrder = Number(right.quantite > 0) - Number(left.quantite > 0)
          if (availabilityOrder !== 0) return availabilityOrder
          return left.designation.localeCompare(right.designation, 'fr', { sensitivity: 'base' })
        })
        .slice(0, 12)
    }
    return candidates
      .filter(item => item.quantite > 0)
      .slice(0, 12)
  }, [cartIds, stock, trimmedSearch])
  const searchReady = trimmedSearch.length > 0 && debouncedSearch === trimmedSearch
  const showSearchLoading = trimmedSearch.length > 0 && (!searchReady || isFetching)
  const showSearchResults = searchReady && filteredProducts.length > 0
  const showNoResults = searchReady && !isFetching && filteredProducts.length === 0

  const totalHtCts = useMemo(
    () => cart.reduce((sum, line) => sum + Math.round(line.unitPriceCts * line.quantity), 0),
    [cart],
  )
  const totalTtcCts = useMemo(
    () => getTransferTtcCts(totalHtCts, DEFAULT_TRANSFER_TVA_PCT),
    [totalHtCts],
  )

  const addToCart = useCallback((product: EpicerieStockRead) => {
    if (product.quantite <= 0) {
      return
    }
    setCart(current => [
      ...current,
      {
        productId: product.produit_id,
        designation: product.designation,
        availableQty: product.quantite,
        quantity: 1,
        unitPriceCts: product.prix_achat_cts,
      },
    ])
    setSearch('')
  }, [])

  const updateQuantity = useCallback((productId: number, quantity: number) => {
    setCart(current =>
      current.map(line => (line.productId === productId ? { ...line, quantity: Math.max(0, quantity) } : line)),
    )
  }, [])

  const removeLine = useCallback((productId: number) => {
    setCart(current => current.filter(line => line.productId !== productId))
  }, [])

  const buildPayload = useCallback(() => {
    const lignes: TransferLineCreate[] = cart.map(line => ({
      produit_id: line.productId,
      quantite: line.quantity,
      prix_unitaire: line.unitPriceCts,
      tva_pct: DEFAULT_TRANSFER_TVA_PCT,
    }))

    return {
      dest_tenant_id: RESTAURANT_TENANT_ID,
      reference: reference.trim() || undefined,
      notes: notes.trim() || undefined,
      lignes,
    }
  }, [cart, notes, reference])

  const submitMutation = useMutation({
    mutationFn: async ({ mode }: { mode: SubmitMode }) => {
      const created = await epicerieApi.creerTransfert(buildPayload())
      if (mode === 'validate') {
        const validated = await epicerieApi.validerTransfert(created.id)
        return { mode, transfer: validated }
      }
      return { mode, transfer: created }
    },
    onSuccess: ({ mode, transfer }) => {
      setError(null)
      setShowConfirm(false)
      qc.invalidateQueries({ queryKey: ['epicerie-transferts'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock-list'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock-stats'] })
      toastOk(
        mode === 'validate' ? 'Transfert validé' : 'Transfert créé en attente',
        transfer.reference || `TRF-${transfer.id}`,
      )
      navigate({ to: '/transferts/$id', params: { id: String(transfer.id) } })
    },
    onError: err => {
      const message = normalizeError(err).message || 'Erreur lors du transfert'
      setError(message)
      setShowConfirm(false)
      toastErr('Erreur', message)
    },
  })

  const isPendingCreation = submitMutation.isPending && submitMutation.variables?.mode === 'pending'
  const canSubmit = cart.length > 0 && cart.every(line => line.quantity > 0 && line.quantity <= line.availableQty)

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl p-4 sm:p-6">
        <div className="mb-6">
          <Link to="/transferts" className="text-sm text-slate-500 transition-colors hover:text-slate-700">
            ← Retour
          </Link>
          <h1 className="mt-2 text-xl font-bold text-slate-900">Nouveau transfert</h1>
        </div>
        <CartSkeleton />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <div>
        <Link to="/transferts" className="text-sm text-slate-500 transition-colors hover:text-slate-700">
          ← Retour
        </Link>
        <h1 className="mt-2 text-xl font-bold text-slate-900">Nouveau transfert → Restaurant</h1>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={search}
          onChange={event => setSearch(event.target.value)}
          placeholder="Rechercher par nom ou EAN..."
          className="w-full rounded-lg border border-slate-300 py-2.5 pl-9 pr-3 text-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
        />
      </div>

      {showSearchLoading && (
        <p className="-mt-3 text-sm text-slate-400">Recherche en cours...</p>
      )}

      {showSearchResults && (
        <div className="-mt-3 max-h-56 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
          {filteredProducts.map(product => (
            <button
              key={product.produit_id}
              type="button"
              disabled={product.quantite <= 0}
              onClick={() => addToCart(product)}
              className={`flex min-h-11 w-full items-center justify-between px-4 py-2.5 text-left text-sm transition-colors ${
                product.quantite > 0
                  ? 'hover:bg-emerald-50'
                  : 'cursor-not-allowed bg-slate-50 text-slate-400'
              }`}
            >
              <span className="min-w-0">
                <span className="block truncate font-medium text-slate-800">{product.designation}</span>
                <span className="block truncate text-xs text-slate-400">
                  {product.fournisseur_source || 'sans fournisseur'} · stock: {product.quantite}
                  {product.quantite <= 0 ? ' · rupture' : ''}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}

      {showNoResults && (
        <p className="-mt-3 text-sm text-slate-400">Aucun produit trouvé.</p>
      )}

      <TransferCart lines={cart} onQuantityChange={updateQuantity} onRemove={removeLine} />

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-slate-600">Référence</span>
          <input
            type="text"
            value={reference}
            onChange={event => {
              setReferenceEdited(true)
              setReference(event.target.value)
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
            placeholder={suggestedReference}
          />
          {!referenceEdited && suggestedReference && (
            <span className="text-xs text-slate-400">Référence suggérée: {suggestedReference}</span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-slate-600">Notes</span>
          <input
            type="text"
            value={notes}
            onChange={event => setNotes(event.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
            placeholder="Service midi, préparation..."
          />
        </label>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
          {error}
          <button type="button" onClick={() => setError(null)} className="ml-2 underline">
            fermer
          </button>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => setShowConfirm(true)}
          disabled={!canSubmit || submitMutation.isPending}
          className="inline-flex w-full min-h-12 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ArrowRight className="h-4 w-4" />
          Valider le transfert
        </button>

        <button
          type="button"
          onClick={() => submitMutation.mutate({ mode: 'pending' })}
          disabled={!canSubmit || submitMutation.isPending}
          className="inline-flex w-full min-h-10 items-center justify-center rounded-lg border border-slate-200 px-5 py-2 text-sm text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isPendingCreation ? 'Création…' : 'Créer en attente (valider plus tard)'}
        </button>
      </div>

      {showConfirm && (
        <TransferConfirmModal
          nbArticles={cart.length}
          totalTtcCts={totalTtcCts}
          loading={submitMutation.isPending}
          onConfirm={() => submitMutation.mutate({ mode: 'validate' })}
          onCancel={() => {
            if (!submitMutation.isPending) {
              setShowConfirm(false)
            }
          }}
        />
      )}
    </div>
  )
}
