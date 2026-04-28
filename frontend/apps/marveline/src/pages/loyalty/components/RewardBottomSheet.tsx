import { useState } from 'react'
import { Gift, Star, Check, Loader2 } from 'lucide-react'
import { BottomSheet } from '@shared/components/ui'
import { useRedeemReward } from '@/api/queries/useLoyalty'
import { normalizeError } from '@shared/errors/normalizer'
import type { RewardAvailable } from '@/types/loyalty'

interface RewardBottomSheetProps {
  isOpen: boolean
  onClose: () => void
  memberId: number
  pointsBalance: number
  rewards: RewardAvailable[]
  hasWelcome: boolean
  orderId?: number
  onRedeemed?: (rewardId: number) => void
}

/**
 * Bottom sheet pour utiliser un reward dans le flow panier/livraison.
 * S'ouvre depuis un bouton "Utiliser un reward" dans le panier.
 */
export default function RewardBottomSheet({
  isOpen,
  onClose,
  memberId,
  pointsBalance,
  rewards,
  hasWelcome,
  orderId,
  onRedeemed,
}: RewardBottomSheetProps) {
  const [error, setError] = useState('')
  const [redeemed, setRedeemed] = useState<number | null>(null)
  const redeemMutation = useRedeemReward()

  const handleRedeem = async (reward: RewardAvailable) => {
    setError('')
    try {
      await redeemMutation.mutateAsync({
        member_id: memberId,
        reward_id: reward.reward_id,
        order_id: orderId,
      })
      setRedeemed(reward.reward_id)
      onRedeemed?.(reward.reward_id)
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur')
    }
  }

  const allRewards = rewards.filter((r) => r.points_cost <= pointsBalance)

  return (
    <BottomSheet isOpen={isOpen} onClose={onClose} title="Utiliser un reward">
      <div className="space-y-4 pb-4">
        {/* Solde */}
        <div className="flex items-center justify-between px-4 py-3 bg-dark-800 rounded-xl">
          <span className="text-dark-300 text-sm">Vos points</span>
          <span className="text-primary-400 font-bold text-lg">{pointsBalance}</span>
        </div>

        {/* Erreur */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 mx-4">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Confirmation */}
        {redeemed && (
          <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 mx-4 text-center space-y-2">
            <Check className="w-8 h-8 text-green-400 mx-auto" />
            <p className="text-green-400 font-medium">Reward applique !</p>
          </div>
        )}

        {/* Liste des rewards */}
        {!redeemed && (
          <div className="space-y-2 px-4">
            {/* Welcome reward */}
            {hasWelcome && (
              <button
                onClick={() => handleRedeem({ reward_id: 0, name: 'Bienvenue', tier: 'welcome', points_cost: 0 })}
                disabled={redeemMutation.isPending}
                className="w-full flex items-center gap-3 p-3 bg-gold-400/10 border border-gold-400/30 rounded-xl hover:bg-gold-400/20 transition-colors disabled:opacity-50"
              >
                <Gift className="w-5 h-5 text-gold-400 shrink-0" />
                <div className="flex-1 text-left">
                  <p className="text-white text-sm font-medium">Reward bienvenue</p>
                  <p className="text-dark-400 text-xs">Offert pour votre premiere commande</p>
                </div>
                <span className="text-gold-400 text-xs font-bold">GRATUIT</span>
              </button>
            )}

            {allRewards.map((reward) => (
              <button
                key={reward.reward_id}
                onClick={() => handleRedeem(reward)}
                disabled={redeemMutation.isPending}
                className="card w-full flex items-center gap-3 p-3 rounded-xl hover:bg-dark-700 transition-colors disabled:opacity-50"
              >
                <Star className="w-5 h-5 text-primary-400 shrink-0" />
                <div className="flex-1 text-left">
                  <p className="text-white text-sm font-medium">{reward.name}</p>
                  <p className="text-dark-400 text-xs">{reward.tier.replace('_', ' ')}</p>
                </div>
                <span className="text-primary-400 text-xs font-mono font-bold">{reward.points_cost} pts</span>
              </button>
            ))}

            {allRewards.length === 0 && !hasWelcome && (
              <div className="text-center py-6">
                <p className="text-dark-400 text-sm">Pas de reward disponible avec votre solde actuel.</p>
              </div>
            )}

            {redeemMutation.isPending && (
              <div className="flex justify-center py-4">
                <Loader2 className="w-6 h-6 animate-spin text-primary-400" />
              </div>
            )}
          </div>
        )}
      </div>
    </BottomSheet>
  )
}
