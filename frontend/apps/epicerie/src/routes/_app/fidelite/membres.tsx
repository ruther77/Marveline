import { useState } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Users, Search, Plus, Loader2, X } from 'lucide-react'
import { z } from 'zod'
import { massacorpApi } from '@/api'
import { normalizeError } from '@shared/errors/normalizer'

const PAGE_SIZE = 20
const PROGRAM_ID = 1

interface LoyaltyMember {
  id: number
  first_name: string
  last_name: string
  phone: string
  current_tier: string
  points_balance: number
  transaction_count: number
  referral_code: string
}

interface PaginatedMembers {
  items: LoyaltyMember[]
  total: number
}

const searchSchema = z.object({
  q: z.string().optional().default(''),
  tier: z.string().optional().default(''),
  page: z.coerce.number().optional().default(1),
})

export const Route = createFileRoute('/_app/fidelite/membres')({
  validateSearch: searchSchema,
  component: LoyaltyMembresPage,
})

const TIER_BADGES: Record<string, { label: string; cls: string }> = {
  standard: { label: 'Membre', cls: 'bg-slate-100 text-slate-600' },
  vip: { label: 'VIP', cls: 'bg-emerald-100 text-emerald-700' },
}

function LoyaltyMembresPage() {
  const { q, tier, page } = Route.useSearch()
  const navigate = useNavigate({ from: '/fidelite/membres' })
  const queryClient = useQueryClient()

  const [adjustModal, setAdjustModal] = useState<LoyaltyMember | null>(null)
  const [adjustAmount, setAdjustAmount] = useState('')
  const [adjustReason, setAdjustReason] = useState('')
  const [adjustError, setAdjustError] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['loyalty-members', PROGRAM_ID, q, tier, page],
    queryFn: () => {
      const p: Record<string, string> = {
        program_id: String(PROGRAM_ID),
        skip: String((page - 1) * PAGE_SIZE),
        limit: String(PAGE_SIZE),
      }
      if (q) p.search = q
      if (tier) p.tier = tier
      return massacorpApi.get<PaginatedMembers>(`/loyalty/admin/members?${new URLSearchParams(p)}`)
    },
    staleTime: 30_000,
  })

  const adjustMut = useMutation({
    mutationFn: ({ member_id, amount, reason }: { member_id: number; amount: number; reason: string }) =>
      massacorpApi.post<{ new_balance: number }>('/loyalty/admin/adjust', { member_id, amount, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['loyalty-members'] })
      setAdjustModal(null)
      setAdjustAmount('')
      setAdjustReason('')
    },
    onError: (err) => setAdjustError(normalizeError(err).message || 'Erreur'),
  })

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1

  return (
    <div className="p-6 space-y-5 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Membres fidélité</h1>
          {data && <p className="text-sm text-slate-400 mt-0.5">{data.total} membre{data.total > 1 ? 's' : ''}</p>}
        </div>
      </div>

      {/* Filtres */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={q}
            onChange={e => navigate({ search: prev => ({ ...prev, q: e.target.value, page: 1 }) })}
            placeholder="Nom, téléphone..."
            className="w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-600"
          />
        </div>
        <select
          value={tier}
          onChange={e => navigate({ search: prev => ({ ...prev, tier: e.target.value, page: 1 }) })}
          className="px-3 py-2.5 border border-slate-200 rounded-xl text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-600"
        >
          <option value="">Tous les paliers</option>
          <option value="standard">Membre</option>
          <option value="vip">VIP</option>
        </select>
      </div>

      {/* Liste */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-white rounded-2xl border border-slate-200 p-4 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-slate-100 rounded-full" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-slate-100 rounded w-40" />
                  <div className="h-3 bg-slate-100 rounded w-56" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {data?.items.map(member => {
            const badge = TIER_BADGES[member.current_tier] || TIER_BADGES.standard
            return (
              <div key={member.id} className="bg-white rounded-2xl border border-slate-200 p-3 flex items-center gap-3">
                <div className="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center shrink-0">
                  <Users className="w-5 h-5 text-slate-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-medium text-sm text-slate-900">{member.first_name} {member.last_name}</p>
                    <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full ${badge.cls}`}>
                      {badge.label}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{member.phone} · {member.transaction_count} transactions · code {member.referral_code}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-sm font-bold text-emerald-600">{member.points_balance} pts</span>
                  <button
                    onClick={() => { setAdjustModal(member); setAdjustError('') }}
                    className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-slate-100 rounded-xl transition-colors"
                    title="Ajuster les points"
                  >
                    <Plus className="w-4 h-4 text-slate-500" />
                  </button>
                </div>
              </div>
            )
          })}

          {data?.items.length === 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 py-12 text-center">
              <Users className="w-8 h-8 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400 text-sm">Aucun membre trouvé.</p>
            </div>
          )}
        </div>
      )}

      {/* Pagination */}
      {data && data.total > PAGE_SIZE && (
        <div className="flex justify-center items-center gap-2">
          <button
            onClick={() => navigate({ search: prev => ({ ...prev, page: Math.max(1, page - 1) }) })}
            disabled={page <= 1}
            className="px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40"
          >
            Précédent
          </button>
          <span className="text-xs text-slate-400">Page {page} / {totalPages}</span>
          <button
            onClick={() => navigate({ search: prev => ({ ...prev, page: page + 1 }) })}
            disabled={page >= totalPages}
            className="px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40"
          >
            Suivant
          </button>
        </div>
      )}

      {/* Modal ajustement points — spec §"Geste commercial : raison obligatoire, ligne ADJUST" */}
      {adjustModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
            <div className="flex items-center justify-between p-5 border-b border-slate-200">
              <h2 className="font-semibold text-slate-900">
                Ajuster les points — {adjustModal.first_name} {adjustModal.last_name}
              </h2>
              <button onClick={() => setAdjustModal(null)} className="p-1 text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-sm text-slate-500">Solde actuel : <span className="font-semibold text-emerald-600">{adjustModal.points_balance} pts</span></p>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Montant</label>
                <input
                  type="number"
                  value={adjustAmount}
                  onChange={e => setAdjustAmount(e.target.value)}
                  placeholder="Ex: 100 (crédit) ou -50 (débit)"
                  className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Raison *</label>
                <input
                  type="text"
                  value={adjustReason}
                  onChange={e => setAdjustReason(e.target.value)}
                  placeholder="Geste commercial, correction erreur..."
                  className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
                />
              </div>
              {adjustError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2">{adjustError}</p>
              )}
            </div>
            <div className="px-5 pb-5 flex gap-2">
              <button
                onClick={() => setAdjustModal(null)}
                className="flex-1 py-2.5 bg-slate-100 text-slate-700 text-sm font-medium rounded-xl hover:bg-slate-200 min-h-[44px]"
              >
                Annuler
              </button>
              <button
                onClick={() => adjustMut.mutate({
                  member_id: adjustModal.id,
                  amount: Number(adjustAmount),
                  reason: adjustReason,
                })}
                disabled={adjustMut.isPending || !adjustAmount || !adjustReason}
                className="flex-1 py-2.5 bg-emerald-600 text-white text-sm font-semibold rounded-xl hover:opacity-90 disabled:opacity-50 flex items-center justify-center min-h-[44px]"
              >
                {adjustMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Confirmer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
