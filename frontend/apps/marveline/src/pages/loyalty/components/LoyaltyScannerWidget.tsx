import { useCallback, useEffect, useRef, useState } from 'react'
import { ScanLine, User, Gift, Star, Loader2, X } from 'lucide-react'
import { useLoyaltyScan, useRedeemReward } from '@/api/queries/useLoyalty'
import { normalizeError } from '@shared/errors/normalizer'
import type { LoyaltyMemberProfile, RewardAvailable } from '@/types/loyalty'

interface LoyaltyScannerWidgetProps {
  onMemberScanned?: (profile: LoyaltyMemberProfile) => void
  onRewardRedeemed?: (rewardId: number, memberId: number) => void
  className?: string
}

/**
 * Widget de scan fidelite pour la caisse.
 * Fonctionne en deux modes :
 * 1. Saisie manuelle du code barcode (lecteur USB = saisie clavier)
 * 2. Resultat = profil membre + rewards disponibles
 */
export default function LoyaltyScannerWidget({
  onMemberScanned,
  onRewardRedeemed,
  className = '',
}: LoyaltyScannerWidgetProps) {
  const [barcode, setBarcode] = useState('')
  const [profile, setProfile] = useState<LoyaltyMemberProfile | null>(null)
  const [error, setError] = useState('')
  const [selectedReward, setSelectedReward] = useState<RewardAvailable | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scanMutation = useLoyaltyScan()
  const redeemMutation = useRedeemReward()

  // Auto-focus pour le lecteur USB
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleScan = useCallback(async (code: string) => {
    if (!code.trim()) return
    setError('')
    setProfile(null)
    setSelectedReward(null)

    try {
      const result = await scanMutation.mutateAsync(code.trim())
      setProfile(result)
      onMemberScanned?.(result)
    } catch (err) {
      setError(normalizeError(err).message || 'Code invalide')
    }
  }, [scanMutation, onMemberScanned])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleScan(barcode)
    }
  }, [barcode, handleScan])

  const handleRedeem = useCallback(async (reward: RewardAvailable) => {
    if (!profile) return
    setError('')

    try {
      await redeemMutation.mutateAsync({
        member_id: profile.member_id,
        reward_id: reward.reward_id,
      })
      setSelectedReward(reward)
      onRewardRedeemed?.(reward.reward_id, profile.member_id)
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors de la redemption')
    }
  }, [profile, redeemMutation, onRewardRedeemed])

  const handleReset = useCallback(() => {
    setBarcode('')
    setProfile(null)
    setError('')
    setSelectedReward(null)
    inputRef.current?.focus()
  }, [])

  const tierColors: Record<string, string> = {
    standard: 'text-dark-300',
    vip: 'text-gold-400',
    nouveau: 'text-dark-300',
    habitue: 'text-primary-400',
    privilegie: 'text-gold-400',
  }

  return (
    <div className={`bg-dark-800 rounded-xl border border-dark-600 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-dark-600 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ScanLine className="w-5 h-5 text-primary-400" />
          <span className="font-medium text-sm">Fidelite</span>
        </div>
        {profile && (
          <button onClick={handleReset} className="p-1 hover:bg-dark-700 rounded">
            <X className="w-4 h-4 text-dark-400" />
          </button>
        )}
      </div>

      <div className="p-4 space-y-3">
        {/* Input barcode */}
        {!profile && (
          <div className="relative">
            <input
              ref={inputRef}
              type="text"
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Scanner ou saisir le code..."
              className="w-full px-3 py-2.5 bg-dark-900 border border-dark-600 rounded-lg text-white placeholder:text-dark-500 focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm font-mono"
              autoComplete="off"
            />
            {scanMutation.isPending && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <Loader2 className="w-4 h-4 animate-spin text-primary-400" />
              </div>
            )}
          </div>
        )}

        {/* Erreur */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-2">
            <p className="text-red-400 text-xs">{error}</p>
          </div>
        )}

        {/* Profil membre */}
        {profile && (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-dark-700 rounded-full flex items-center justify-center">
                <User className="w-5 h-5 text-dark-300" />
              </div>
              <div>
                <p className="font-medium text-white text-sm">
                  {profile.first_name} {profile.last_name}
                </p>
                <p className={`text-xs font-semibold uppercase ${tierColors[profile.current_tier] || 'text-dark-300'}`}>
                  {profile.current_tier === 'vip' ? 'VIP' : profile.current_tier}
                </p>
              </div>
              <div className="ml-auto text-right">
                <p className="text-lg font-bold text-primary-400">{profile.points_balance}</p>
                <p className="text-xs text-dark-400">points</p>
              </div>
            </div>

            {/* Remise (programme location) */}
            {profile.discount_percent > 0 && (
              <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-2 text-center">
                <span className="text-green-400 font-bold text-sm">-{profile.discount_percent}% sur le panier</span>
              </div>
            )}

            {/* Welcome reward */}
            {profile.has_welcome_reward && (
              <div className="bg-gold-400/10 border border-gold-400/30 rounded-lg p-2 flex items-center gap-2">
                <Gift className="w-4 h-4 text-gold-400" />
                <span className="text-gold-400 text-xs font-medium">Reward bienvenue disponible !</span>
              </div>
            )}

            {/* Rewards disponibles */}
            {profile.available_rewards.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs text-dark-400 font-medium uppercase">Rewards disponibles</p>
                {profile.available_rewards.map((reward) => (
                  <button
                    key={reward.reward_id}
                    onClick={() => handleRedeem(reward)}
                    disabled={redeemMutation.isPending}
                    className="w-full flex items-center justify-between px-3 py-2 bg-dark-700 hover:bg-dark-600 rounded-lg transition-colors text-sm disabled:opacity-50"
                  >
                    <div className="flex items-center gap-2">
                      <Star className="w-4 h-4 text-primary-400" />
                      <span className="text-white">{reward.name}</span>
                    </div>
                    <span className="text-primary-400 font-mono text-xs">{reward.points_cost} pts</span>
                  </button>
                ))}
              </div>
            )}

            {/* Confirmation redemption */}
            {selectedReward && (
              <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 text-center space-y-1">
                <p className="text-green-400 font-medium text-sm">Reward utilise !</p>
                <p className="text-dark-300 text-xs">{selectedReward.name} (-{selectedReward.points_cost} pts)</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
