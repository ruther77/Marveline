import { useState } from 'react'
import { Gift, Plus, ToggleLeft, ToggleRight, Search, X } from 'lucide-react'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { useLoyaltyRewards, useCreateReward, useUpdateReward } from '@/api/queries/useLoyalty'
import { useProductsList } from '@/api/queries/useProducts'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { normalizeError } from '@shared/errors/normalizer'
import { useDebounce } from '@shared/hooks/useDebounce'
import { PageHeader } from '@/components/PageHeader'
import { cn } from '@/lib/utils'
import type { RewardsCatalogResponse } from '@/types/loyalty'

const PROGRAM_ID = 1

const TIER_LABELS: Record<string, string> = {
  welcome: 'Bienvenue (gratuit)',
  tier_1: 'Tier 1 (500 pts)',
  tier_2: 'Tier 2 (1 500 pts)',
  tier_3: 'Tier 3 (3 000 pts)',
}

const TIER_COLORS: Record<string, string> = {
  welcome: 'border-gold-400/30',
  tier_1: 'border-primary-500/30',
  tier_2: 'border-blue-500/30',
  tier_3: 'border-purple-500/30',
}

const rewardSchema = z.object({
  tier: z.enum(['welcome', 'tier_1', 'tier_2', 'tier_3']),
  name: z.string().min(1, 'Requis').max(200),
  description: z.string().max(500).optional(),
  points_cost: z.coerce.number().min(0),
  max_cost_cents: z.coerce.number().min(0),
})

type RewardFormData = z.infer<typeof rewardSchema>

export default function LoyaltyRewardsPage() {
  const [showCreate, setShowCreate] = useState(false)
  const [error, setError] = useState('')
  const [productSearch, setProductSearch] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<{ id: number; name: string } | null>(null)
  const debouncedProductSearch = useDebounce(productSearch, 300)

  const { data: rewards, isLoading } = useLoyaltyRewards(PROGRAM_ID)
  const createMutation = useCreateReward(PROGRAM_ID)
  const updateMutation = useUpdateReward(PROGRAM_ID)
  const { data: productsData } = useProductsList(
    { search: debouncedProductSearch, limit: 10 },
    debouncedProductSearch.length >= 2,
  )

  const { register, handleSubmit, reset, setValue, formState: { errors: formErrors } } = useForm<RewardFormData>({
    resolver: zodResolver(rewardSchema),
    defaultValues: { tier: 'tier_1', points_cost: 500, max_cost_cents: 0 },
  })

  const handleSelectProduct = (p: { id: number; name: string }) => {
    setSelectedProduct(p)
    setProductSearch('')
    setValue('name', p.name, { shouldValidate: false })
  }

  const closeModal = () => {
    setShowCreate(false)
    setError('')
    setSelectedProduct(null)
    setProductSearch('')
  }

  const onSubmit = async (data: RewardFormData) => {
    setError('')
    try {
      await createMutation.mutateAsync({ ...data, product_id: selectedProduct?.id })
      closeModal()
      reset()
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur')
    }
  }

  const handleToggle = async (reward: RewardsCatalogResponse) => {
    await updateMutation.mutateAsync({ id: reward.id, data: { is_active: !reward.is_active } })
  }

  const grouped: Record<string, RewardsCatalogResponse[]> = {}
  for (const tier of ['welcome', 'tier_1', 'tier_2', 'tier_3']) {
    grouped[tier] = (rewards ?? []).filter((r) => r.tier === tier)
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <PageHeader title="Catalogue récompenses" subtitle="Gérer les récompenses par palier" />
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary flex items-center gap-1.5 text-sm"
        >
          <Plus className="w-4 h-4" /> Ajouter
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-4 animate-pulse space-y-2">
              <div className="h-4 bg-dark-100/10 rounded w-32" />
              <div className="h-12 bg-dark-100/10 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([tier, items]) => (
            <div key={tier}>
              <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wider mb-2 px-1">
                {TIER_LABELS[tier]} ({items.length})
              </h2>
              {items.length === 0 ? (
                <p className="text-xs text-dark-500 px-1">Aucune récompense dans ce palier.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {items.map((reward) => (
                    <div
                      key={reward.id}
                      className={cn(
                        'card p-3 border-l-4 hover:shadow-md transition-shadow',
                        TIER_COLORS[tier] || '',
                        !reward.is_active && 'opacity-40',
                      )}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-2.5">
                          <Gift className="w-4 h-4 text-primary-400 mt-0.5 shrink-0" />
                          <div>
                            <p className="font-medium text-sm">{reward.name}</p>
                            {reward.description && <p className="text-xs text-dark-400 mt-0.5">{reward.description}</p>}
                            <p className="text-xs text-dark-500 mt-1">
                              {reward.points_cost} pts — coût max {(reward.max_cost_cents / 100).toFixed(2)} EUR
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => handleToggle(reward)}
                          disabled={updateMutation.isPending}
                          className="p-1 shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center"
                          title={reward.is_active ? 'Désactiver' : 'Activer'}
                        >
                          {reward.is_active ? (
                            <ToggleRight className="w-6 h-6 text-green-400" />
                          ) : (
                            <ToggleLeft className="w-6 h-6 text-dark-500" />
                          )}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modal creation */}
      <Modal
        isOpen={showCreate}
        onClose={closeModal}
        title="Nouvelle récompense"
        footer={
          <ModalFooter
            onCancel={closeModal}
            onConfirm={handleSubmit(onSubmit)}
            confirmText="Créer"
            loading={createMutation.isPending}
          />
        }
      >
        <form className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Palier *</label>
            <select {...register('tier')} className="input w-full text-sm">
              <option value="welcome">Bienvenue (gratuit)</option>
              <option value="tier_1">Tier 1 (500 pts)</option>
              <option value="tier_2">Tier 2 (1 500 pts)</option>
              <option value="tier_3">Tier 3 (3 000 pts)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Produit du catalogue{' '}
              <span className="text-dark-500 font-normal text-xs">(optionnel — recommandé Tier 1)</span>
            </label>
            {selectedProduct ? (
              <div className="flex items-center gap-2 px-3 py-2.5 bg-primary-500/10 border border-primary-500/30 rounded-lg text-sm">
                <Gift className="w-3.5 h-3.5 text-primary-400 shrink-0" />
                <span className="flex-1 truncate">{selectedProduct.name}</span>
                <button
                  type="button"
                  onClick={() => setSelectedProduct(null)}
                  className="text-dark-400 hover:text-dark-200 shrink-0"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-dark-400 pointer-events-none" />
                <input
                  type="text"
                  value={productSearch}
                  onChange={e => setProductSearch(e.target.value)}
                  placeholder="Rechercher un produit..."
                  className="input w-full text-sm pl-8"
                />
                {debouncedProductSearch.length >= 2 && productsData && (
                  <div className="absolute z-10 w-full mt-1 bg-dark-800 border border-dark-600 rounded-xl shadow-xl max-h-40 overflow-y-auto">
                    {productsData.items.length === 0 ? (
                      <p className="px-3 py-2 text-xs text-dark-400">Aucun produit trouvé</p>
                    ) : (
                      productsData.items.map(p => (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => handleSelectProduct(p)}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-primary-500/10 text-dark-100 first:rounded-t-xl last:rounded-b-xl"
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
            <label className="block text-sm font-medium mb-1">Nom *</label>
            <input {...register('name')} placeholder="Ex: Bière artisanale" className="input w-full text-sm" />
            {formErrors.name && <p className="text-red-400 text-xs mt-1">{formErrors.name.message}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <input {...register('description')} placeholder="Optionnel" className="input w-full text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Points</label>
              <input {...register('points_cost')} type="number" className="input w-full text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Coût max (centimes)</label>
              <input {...register('max_cost_cents')} type="number" className="input w-full text-sm" />
            </div>
          </div>
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-2">
              <p className="text-red-400 text-xs">{error}</p>
            </div>
          )}
        </form>
      </Modal>
    </div>
  )
}
