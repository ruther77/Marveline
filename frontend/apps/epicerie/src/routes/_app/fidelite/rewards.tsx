import { useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Gift, Plus, ToggleLeft, ToggleRight, Loader2, X } from 'lucide-react'
import { massacorpApi } from '@/api'
import { normalizeError } from '@shared/errors/normalizer'

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
  tier_1: 'border-l-emerald-500',
  tier_2: 'border-l-blue-500',
  tier_3: 'border-l-purple-500',
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

  const { data: rewards, isLoading } = useQuery({
    queryKey: ['loyalty-rewards', PROGRAM_ID],
    queryFn: () => massacorpApi.get<Reward[]>(`/loyalty/admin/rewards?program_id=${PROGRAM_ID}`),
    staleTime: 60_000,
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
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loyalty-rewards'] })
      setShowCreate(false)
      setForm({ tier: 'tier_1', name: '', description: '', points_cost: 500, max_cost_cents: 0 })
    },
    onError: (err) => setCreateError(normalizeError(err).message || 'Erreur'),
  })

  const grouped: Record<string, Reward[]> = { welcome: [], tier_1: [], tier_2: [], tier_3: [] }
  for (const r of rewards ?? []) {
    grouped[r.tier]?.push(r)
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Catalogue récompenses</h1>
          <p className="text-sm text-slate-400 mt-0.5">Gérer les rewards par palier — L'Incontournable</p>
        </div>
        <button
          onClick={() => { setShowCreate(true); setCreateError('') }}
          className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-sm font-semibold rounded-xl hover:opacity-90 min-h-[44px]"
        >
          <Plus className="w-4 h-4" /> Ajouter
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-2xl border border-slate-200 p-4 animate-pulse space-y-2">
              <div className="h-3 bg-slate-100 rounded w-32" />
              <div className="h-14 bg-slate-100 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([tier, items]) => (
            <div key={tier}>
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 px-1">
                {TIER_LABELS[tier]} ({items.length})
              </h2>
              {items.length === 0 ? (
                <p className="text-xs text-slate-300 px-1">Aucune récompense dans ce palier.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {items.map(reward => (
                    <div
                      key={reward.id}
                      className={`bg-white rounded-2xl border border-slate-200 border-l-4 ${TIER_ACCENT[tier] || ''} p-3 flex items-start justify-between transition-opacity ${!reward.is_active ? 'opacity-50' : ''}`}
                    >
                      <div className="flex items-start gap-2.5">
                        <Gift className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="font-medium text-sm text-slate-900">{reward.name}</p>
                          {reward.description && <p className="text-xs text-slate-400 mt-0.5">{reward.description}</p>}
                          <p className="text-xs text-slate-400 mt-1">
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
                          ? <ToggleRight className="w-6 h-6 text-emerald-500" />
                          : <ToggleLeft className="w-6 h-6 text-slate-300" />
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

      {/* Modal création reward */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
            <div className="flex items-center justify-between p-5 border-b border-slate-200">
              <h2 className="font-semibold text-slate-900">Nouvelle récompense</h2>
              <button onClick={() => setShowCreate(false)} className="p-1 text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Palier *</label>
                <select
                  value={form.tier}
                  onChange={e => setForm(f => ({ ...f, tier: e.target.value as Reward['tier'] }))}
                  className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-600"
                >
                  <option value="welcome">Bienvenue (gratuit)</option>
                  <option value="tier_1">Tier 1 (500 pts)</option>
                  <option value="tier_2">Tier 2 (1 500 pts)</option>
                  <option value="tier_3">Tier 3 (3 000 pts)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Nom *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="Ex: Bière artisanale"
                  className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Description</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Optionnel"
                  className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 mb-1">Points</label>
                  <input
                    type="number"
                    value={form.points_cost}
                    onChange={e => setForm(f => ({ ...f, points_cost: Number(e.target.value) }))}
                    className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 mb-1">Coût max (cts)</label>
                  <input
                    type="number"
                    value={form.max_cost_cents}
                    onChange={e => setForm(f => ({ ...f, max_cost_cents: Number(e.target.value) }))}
                    className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
                  />
                </div>
              </div>
              {createError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2">{createError}</p>
              )}
            </div>
            <div className="px-5 pb-5 flex gap-2">
              <button onClick={() => setShowCreate(false)}
                className="flex-1 py-2.5 bg-slate-100 text-slate-700 text-sm font-medium rounded-xl hover:bg-slate-200 min-h-[44px]">
                Annuler
              </button>
              <button
                onClick={() => createMut.mutate()}
                disabled={createMut.isPending || !form.name.trim()}
                className="flex-1 py-2.5 bg-emerald-600 text-white text-sm font-semibold rounded-xl hover:opacity-90 disabled:opacity-50 flex items-center justify-center min-h-[44px]"
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
