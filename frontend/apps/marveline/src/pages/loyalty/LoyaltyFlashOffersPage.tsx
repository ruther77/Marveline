import { useState } from 'react'
import { Zap, Plus, Clock, Check } from 'lucide-react'
import { Modal, ModalFooter } from '@shared/components/ui/Modal'
import { useLoyaltyFlashOffers, useCreateFlashOffer } from '@/api/queries/useLoyalty'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { normalizeError } from '@shared/errors/normalizer'
import { PageHeader } from '@/components/PageHeader'
import { cn } from '@/lib/utils'
import type { FlashOfferResponse } from '@/types/loyalty'

const PROGRAM_ID = 1

const STATUS_BADGES: Record<string, { label: string; icon: typeof Clock; className: string }> = {
  scheduled: { label: 'Programmée', icon: Clock, className: 'text-blue-400 bg-blue-400/10' },
  active: { label: 'Active', icon: Zap, className: 'text-green-400 bg-green-400/10' },
  ended: { label: 'Terminée', icon: Check, className: 'text-dark-400 bg-dark-100/10' },
}

const offerSchema = z.object({
  name: z.string().min(1, 'Requis').max(200),
  multiplier: z.coerce.number().min(1.1, 'Min 1.1').max(10),
  target: z.enum(['all', 'vip']),
  starts_at: z.string().min(1, 'Requis'),
  ends_at: z.string().min(1, 'Requis'),
})

type OfferFormData = z.infer<typeof offerSchema>

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export default function LoyaltyFlashOffersPage() {
  const [showCreate, setShowCreate] = useState(false)
  const [error, setError] = useState('')

  const { data: offers, isLoading } = useLoyaltyFlashOffers()
  const createMutation = useCreateFlashOffer()

  const { register, handleSubmit, reset, formState: { errors: formErrors } } = useForm<OfferFormData>({
    resolver: zodResolver(offerSchema),
    defaultValues: { multiplier: 2, target: 'all' },
  })

  const onSubmit = async (data: OfferFormData) => {
    setError('')
    try {
      await createMutation.mutateAsync({
        ...data,
        program_id: PROGRAM_ID,
        starts_at: new Date(data.starts_at).toISOString(),
        ends_at: new Date(data.ends_at).toISOString(),
      })
      setShowCreate(false)
      reset()
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur')
    }
  }

  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <PageHeader title="Offres flash" subtitle="Points x2, promotions temporaires" />
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary flex items-center gap-1.5 text-sm"
        >
          <Plus className="w-4 h-4" /> Nouvelle offre
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card p-4 animate-pulse space-y-2">
              <div className="h-4 bg-dark-100/10 rounded w-40" />
              <div className="h-3 bg-dark-100/10 rounded w-56" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {(offers ?? []).length === 0 && (
            <div className="card text-center py-12">
              <Zap className="w-8 h-8 mx-auto mb-3 text-dark-400" />
              <p className="text-dark-400 text-sm">Aucune offre flash programmée.</p>
            </div>
          )}

          {(offers ?? []).map((offer) => {
            const badge = STATUS_BADGES[offer.status] || STATUS_BADGES.scheduled
            const BadgeIcon = badge.icon
            return (
              <div key={offer.id} className="card p-4 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4 text-primary-400" />
                      <p className="font-medium text-sm">{offer.name}</p>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-dark-400">
                      <span>x{offer.multiplier}</span>
                      <span>Cible : {offer.target === 'all' ? 'Tous' : 'VIP'}</span>
                    </div>
                    <div className="text-xs text-dark-500">
                      {formatDate(offer.starts_at)} — {formatDate(offer.ends_at)}
                    </div>
                  </div>
                  <span className={cn('flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase', badge.className)}>
                    <BadgeIcon className="w-3 h-3" />
                    {badge.label}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Modal creation */}
      <Modal
        isOpen={showCreate}
        onClose={() => { setShowCreate(false); setError('') }}
        title="Nouvelle offre flash"
        footer={
          <ModalFooter
            onCancel={() => { setShowCreate(false); setError('') }}
            onConfirm={handleSubmit(onSubmit)}
            confirmText="Créer"
            loading={createMutation.isPending}
          />
        }
      >
        <form className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Nom *</label>
            <input {...register('name')} placeholder="Ex: Points x2 ce weekend !" className="input w-full text-sm" />
            {formErrors.name && <p className="text-red-400 text-xs mt-1">{formErrors.name.message}</p>}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Multiplicateur *</label>
              <input {...register('multiplier')} type="number" step="0.1" className="input w-full text-sm" />
              {formErrors.multiplier && <p className="text-red-400 text-xs mt-1">{formErrors.multiplier.message}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Cible *</label>
              <select {...register('target')} className="input w-full text-sm">
                <option value="all">Tous les membres</option>
                <option value="vip">VIP uniquement</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Début *</label>
              <input {...register('starts_at')} type="datetime-local" className="input w-full text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Fin *</label>
              <input {...register('ends_at')} type="datetime-local" className="input w-full text-sm" />
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
