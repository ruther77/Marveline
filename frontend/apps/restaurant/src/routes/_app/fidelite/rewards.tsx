import { useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Gift, Plus, ToggleLeft, ToggleRight, Loader2, X, Search } from 'lucide-react'
import { massacorpApi } from '@/api'
import { normalizeError } from '@shared/errors/normalizer'
import { useDebounce } from '@shared/hooks/useDebounce'

const PROGRAM_ID = 1

interface Reward {
  id: number
  tier: 'welcome' | 'tier_1' | 'tier_2' | 'tier_3'
  name: string
  description: string | null
  points_cost: number
  max_cost_cents: number
  is_active: boolean
}

interface ProductOption {
  id: number
  name: string
}

export const Route = createFileRoute('/_app/fidelite/rewards')({
  component: LoyaltyRewardsPage,
})

const TIER_LABELS: Record<string, string> = {
  welcome: 'Bienvenue (gratuit)',
  tier_1: 'Tier 1 — 500 pts',
  tier_2: 'Tier 2 — 1 500 pts',
  tier_3: 'Tier 3 — 3 000 pts',
}

const TIER_ACCENT: Record<string, string> = {
  welcome: 'border-l-amber-400',
  tier_1: 'border-l-amber-600',
  tier_2: 'border-l-stone-500',
  tier_3: 'border-l-stone-800',
}

function LoyaltyRewardsPage() {
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [createError, setCreateError] = useState('')
  const [form, setForm] = useState({
    tier: 'tier_1' as Reward['tier'],
    name: '',
    description: '',
    points_cost: 500,
    max_cost_cents: 0,
  })
  const [productSearch, setProductSearch] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<ProductOption | null>(null)
  const debouncedProductSearch = useDebounce(productSearch, 300)

  const { data: rewards, isLoading } = useQuery({
    queryKey: ['loyalty-rewards', PROGRAM_ID],
    queryFn: () => massacorpApi.get<Reward[]>(`/loyalty/admin/rewards?program_id=${PROGRAM_ID}`),
    staleTime: 60_000,
  })

  const { data: productsData } = useQuery({
    queryKey: ['products-search', debouncedProductSearch],
    queryFn: () => massacorpApi.get<{ items: ProductOption[]; total: number }>(
      `/products?search=${encodeURIComponent(debouncedProductSearch)}&limit=10`
    ),
    enabled: debouncedProductSearch.length >= 2,
    staleTime: 30_000,
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      massacorpApi.put<Reward>(`/loyalty/admin/rewards/${id}`, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['loyalty-rewards'] }),
  })

  const createMut = useMutation({
    mutationFn: () => massacorpApi.post<Reward>(`/loyalty/admin/rewards?program_id=${PROGRAM_ID}`, {
      tier: form.tier,
      name: form.name.trim(),
      description: form.description.trim() || null,
      points_cost: form.points_cost,
      max_cost_cents: form.max_cost_cents,
      ...(selectedProduct ? { product_id: selectedProduct.id } : {}),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loyalty-rewards'] })
      setShowCreate(false)
      setForm({ tier: 'tier_1', name: '', description: '', points_cost: 500, max_cost_cents: 0 })
      setSelectedProduct(null)
      setProductSearch('')
    },
    onError: (err) => setCreateError(normalizeError(err).message || 'Erreur'),
  })

  const handleSelectProduct = (p: ProductOption) => {
    setSelectedProduct(p)
    setProductSearch('')
    if (!form.name.trim()) setForm(f => ({ ...f, name: p.name }))
  }

  const grouped: Record<string, Reward[]> = { welcome: [], tier_1: [], tier_2: [], tier_3: [] }
  for (const r of rewards ?? []) {
    grouped[r.tier]?.push(r)
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900">Catalogue récompenses</h1>
          <p className="text-sm text-stone-400 mt-0.5">Gérer les rewards par palier — L'Incontournable</p>
        </div>
        <button
          onClick={() => { setShowCreate(true); setCreateError(''); setSelectedProduct(null); setProductSearch('') }}
          className="flex items-center gap-1.5 px-4 py-2 bg-amber-600 text-white text-sm font-semibold rounded-xl hover:opacity-90 min-h-[44px]"
        >
          <Plus className="w-4 h-4" /> Ajouter
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-2xl border border-stone-200 p-4 animate-pulse space-y-2">
              <div className="h-3 bg-stone-100 rounded w-32" />
              <div className="h-14 bg-stone-100 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([tier, items]) => (
            <div key={tier}>
              <h2 className="text-xs font-semibold text-stone-400 uppercase tracking-wider mb-2 px-1">
                {TIER_LABELS[tier]} ({items.length})
              </h2>
              {items.length === 0 ? (
                <p className="text-xs text-stone-300 px-1">Aucune récompense dans ce palier.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {items.map(reward => (
                    <div
                      key={reward.id}
                      className={`bg-white rounded-2xl border border-stone-200 border-l-4 ${TIER_ACCENT[tier] || ''} p-3 flex items-start justify-between transition-opacity ${!reward.is_active ? 'opacity-50' : ''}`}
                    >
                      <div className="flex items-start gap-2.5">
                        <Gift className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="font-medium text-sm text-stone-900">{reward.name}</p>
                          {reward.description && <p className="text-xs text-stone-400 mt-0.5">{reward.description}</p>}
                          <p className="text-xs text-stone-400 mt-1">
                            {reward.points_cost} pts · coût max {(reward.max_cost_cents / 100).toFixed(2)} €
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => toggleMut.mutate({ id: reward.id, is_active: !reward.is_active })}
                        disabled={toggleMut.isPending}
                        className="p-1 shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center"
                        title={reward.is_active ? 'Désactiver' : 'Activer'}
                      >
                        {reward.is_active
                          ? <ToggleRight className="w-6 h-6 text-amber-500" />
                          : <ToggleLeft className="w-6 h-6 text-stone-300" />
                        }
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
            <div className="flex items-center justify-between p-5 border-b border-stone-200">
              <h2 className="font-semibold text-stone-900">Nouvelle récompense</h2>
              <button onClick={() => { setShowCreate(false); setSelectedProduct(null); setProductSearch('') }} className="p-1 text-stone-400 hover:text-stone-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-stone-500 mb-1">Palier *</label>
                <select
                  value={form.tier}
                  onChange={e => setForm(f => ({ ...f, tier: e.target.value as Reward['tier'] }))}
                  className="w-full px-3 py-2.5 border border-stone-300 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-600"
                >
                  <option value="welcome">Bienvenue (gratuit)</option>
                  <option value="tier_1">Tier 1 (500 pts)</option>
                  <option value="tier_2">Tier 2 (1 500 pts)</option>
                  <option value="tier_3">Tier 3 (3 000 pts)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-stone-500 mb-1">
                  Produit du catalogue{' '}
                  <span className="text-stone-300 font-normal">(optionnel — recommandé Tier 1)</span>
                </label>
                {selectedProduct ? (
                  <div className="flex items-center gap-2 px-3 py-2.5 bg-amber-50 border border-amber-200 rounded-xl text-sm">
                    <Gift className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    <span className="flex-1 text-stone-900 truncate">{selectedProduct.name}</span>
                    <button
                      type="button"
                      onClick={() => setSelectedProduct(null)}
                      className="text-stone-400 hover:text-stone-600 shrink-0"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400 pointer-events-none" />
                    <input
                      type="text"
                      value={productSearch}
                      onChange={e => setProductSearch(e.target.value)}
                      placeholder="Rechercher un produit..."
                      className="w-full pl-8 pr-3 py-2.5 border border-stone-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-600"
                    />
                    {debouncedProductSearch.length >= 2 && productsData && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-stone-200 rounded-xl shadow-lg max-h-40 overflow-y-auto">
                        {productsData.items.length === 0 ? (
                          <p className="px-3 py-2 text-xs text-stone-400">Aucun produit trouvé</p>
                        ) : (
                          productsData.items.map(p => (
                            <button
                              key={p.id}
                              type="button"
                              onClick={() => handleSelectProduct(p)}
                              className="w-full text-left px-3 py-2 text-sm hover:bg-amber-50 text-stone-900 first:rounded-t-xl last:rounded-b-xl"
                            >
                              {p.name}
                            </button>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div>
                <label className="block text-xs font-semibold text-stone-500 mb-1">Nom *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Ex: Café offert"
                  className="w-full px-3 py-2.5 border border-stone-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-600"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-stone-500 mb-1">Description</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Optionnel"
                  className="w-full px-3 py-2.5 border border-stone-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-600"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-stone-500 mb-1">Points</label>
                  <input
                    type="number"
                    value={form.points_cost}
                    onChange={e => setForm(f => ({ ...f, points_cost: Number(e.target.value) }))}
                    className="w-full px-3 py-2.5 border border-stone-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-stone-500 mb-1">Coût max (cts)</label>
                  <input
                    type="number"
                    value={form.max_cost_cents}
                    onChange={e => setForm(f => ({ ...f, max_cost_cents: Number(e.target.value) }))}
                    className="w-full px-3 py-2.5 border border-stone-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-600"
                  />
                </div>
              </div>
              {createError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2">{createError}</p>
              )}
            </div>
            <div className="px-5 pb-5 flex gap-2">
              <button onClick={() => setShowCreate(false)}
                className="flex-1 py-2.5 bg-stone-100 text-stone-700 text-sm font-medium rounded-xl hover:bg-stone-200 min-h-[44px]">
                Annuler
              </button>
              <button
                onClick={() => createMut.mutate()}
                disabled={createMut.isPending || !form.name.trim()}
                className="flex-1 py-2.5 bg-amber-600 text-white text-sm font-semibold rounded-xl hover:opacity-90 disabled:opacity-50 flex items-center justify-center min-h-[44px]"
              >
                {createMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Créer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
