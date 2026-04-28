import { useState } from 'react'
import { Users, Search, Plus, Loader2 } from 'lucide-react'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { useLoyaltyMembers, useAdjustPoints } from '@/api/queries/useLoyalty'
import { useNavigate } from '@tanstack/react-router'
import { Route } from '@/routes/_app/admin/loyalty-members'
import { normalizeError } from '@shared/errors/normalizer'
import { PageHeader } from '@/components/PageHeader'
import type { LoyaltyMemberList, LoyaltyTier } from '@/types/loyalty'

const PAGE_SIZE = 20
const PROGRAM_ID = 1

const TIER_BADGES: Record<string, { label: string; className: string }> = {
  standard: { label: 'Membre', className: 'bg-dark-100/10 text-dark-400' },
  vip: { label: 'VIP', className: 'bg-gold-400/20 text-gold-400' },
  nouveau: { label: 'Nouveau', className: 'bg-dark-100/10 text-dark-400' },
  habitue: { label: 'Habitué', className: 'bg-primary-500/20 text-primary-400' },
  privilegie: { label: 'Privilégié', className: 'bg-gold-400/20 text-gold-400' },
}

export default function LoyaltyMembersPage() {
  const { q, tier, page } = Route.useSearch()
  const navigate = useNavigate()

  const [adjustModal, setAdjustModal] = useState<LoyaltyMemberList | null>(null)
  const [adjustAmount, setAdjustAmount] = useState('')
  const [adjustReason, setAdjustReason] = useState('')
  const [adjustError, setAdjustError] = useState('')

  const { data, isLoading } = useLoyaltyMembers({
    program_id: PROGRAM_ID,
    skip: (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    search: q || undefined,
    tier: (tier as LoyaltyTier) || undefined,
  })

  const adjustMutation = useAdjustPoints()

  const handleSearch = (newQ: string) => {
    navigate({ search: (prev) => ({ ...prev, q: newQ, page: 1 }) })
  }

  const handleTierFilter = (newTier: string) => {
    navigate({ search: (prev) => ({ ...prev, tier: newTier, page: 1 }) })
  }

  const handleAdjust = async () => {
    if (!adjustModal || !adjustAmount || !adjustReason) return
    setAdjustError('')
    try {
      await adjustMutation.mutateAsync({
        member_id: adjustModal.id,
        amount: Number(adjustAmount),
        reason: adjustReason,
      })
      setAdjustModal(null)
      setAdjustAmount('')
      setAdjustReason('')
    } catch (err) {
      setAdjustError(normalizeError(err).message || 'Erreur')
    }
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      <PageHeader title="Membres fidélité" subtitle={data ? `${data.total} membre${data.total > 1 ? 's' : ''}` : undefined} />

      {/* Filtres */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
          <input
            type="text"
            value={q}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Rechercher par nom, téléphone..."
            className="input w-full pl-10 py-2.5 text-sm"
          />
        </div>
        <select
          value={tier}
          onChange={(e) => handleTierFilter(e.target.value)}
          className="input py-2.5 text-sm"
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
            <div key={i} className="card p-4 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-dark-100/10 rounded-full shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-dark-100/10 rounded w-40" />
                  <div className="h-3 bg-dark-100/10 rounded w-56" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {data?.items.map((member) => {
            const badge = TIER_BADGES[member.current_tier] || TIER_BADGES.standard
            return (
              <div key={member.id} className="card p-3 flex items-center gap-3 hover:shadow-md transition-shadow">
                <div className="w-10 h-10 bg-dark-950 rounded-full flex items-center justify-center shrink-0">
                  <Users className="w-5 h-5 text-dark-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-sm truncate">
                      {member.first_name} {member.last_name}
                    </p>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${badge.className}`}>
                      {badge.label}
                    </span>
                  </div>
                  <p className="text-xs text-dark-400">{member.phone} — {member.transaction_count} transactions</p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => setAdjustModal(member)}
                    className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-dark-100/10 dark:hover:bg-dark-700 rounded-lg transition-colors"
                    title="Ajuster les points"
                  >
                    <Plus className="w-4 h-4 text-dark-400" />
                  </button>
                  <span className="text-xs text-dark-500 font-mono">{member.referral_code}</span>
                </div>
              </div>
            )
          })}

          {data?.items.length === 0 && (
            <div className="card text-center py-12">
              <Users className="w-8 h-8 text-dark-400 mx-auto mb-3" />
              <p className="text-dark-400 text-sm">Aucun membre trouvé.</p>
            </div>
          )}
        </div>
      )}

      {/* Pagination */}
      {data && data.total > PAGE_SIZE && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => navigate({ search: (prev) => ({ ...prev, page: Math.max(1, page - 1) }) })}
            disabled={page <= 1}
            className="px-3 py-1.5 text-xs btn-secondary disabled:opacity-30"
          >
            Précédent
          </button>
          <span className="px-3 py-1.5 text-xs text-dark-400">
            Page {page} / {Math.ceil(data.total / PAGE_SIZE)}
          </span>
          <button
            onClick={() => navigate({ search: (prev) => ({ ...prev, page: page + 1 }) })}
            disabled={page * PAGE_SIZE >= data.total}
            className="px-3 py-1.5 text-xs btn-secondary disabled:opacity-30"
          >
            Suivant
          </button>
        </div>
      )}

      {/* Modal ajustement */}
      <Modal
        isOpen={!!adjustModal}
        onClose={() => { setAdjustModal(null); setAdjustError('') }}
        title={`Ajuster les points — ${adjustModal?.first_name} ${adjustModal?.last_name}`}
        footer={
          <ModalFooter
            onCancel={() => { setAdjustModal(null); setAdjustError('') }}
            onConfirm={handleAdjust}
            confirmText="Confirmer"
            loading={adjustMutation.isPending}
          />
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Montant</label>
            <input
              type="number"
              value={adjustAmount}
              onChange={(e) => setAdjustAmount(e.target.value)}
              placeholder="Ex: 100 (crédit) ou -50 (débit)"
              className="input w-full text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Raison *</label>
            <input
              type="text"
              value={adjustReason}
              onChange={(e) => setAdjustReason(e.target.value)}
              placeholder="Geste commercial, correction..."
              className="input w-full text-sm"
            />
          </div>
          {adjustError && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-2">
              <p className="text-red-400 text-xs">{adjustError}</p>
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}
