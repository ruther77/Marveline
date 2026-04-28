/**
 * Widget scan fidélité épicerie — design emerald.
 * Flow : saisir/scanner barcode → profil membre → créditer points → optionnel redeem.
 * Spec §"Affichage caissier post-scan" : Nom, palier, points actuels, rewards disponibles.
 * Spec §"Points" : Epicerie = 5 pts/EUR TTC, source='epicerie'.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ScanLine, User, Gift, Star, Loader2, X, Check } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import { loyaltyApi, EPICERIE_LOYALTY_PROGRAM_ID } from '@/api/loyalty'
import type { LoyaltyMemberProfile, RewardAvailable, CreditResponse } from '@/api/loyalty'

function fmtEur(cts: number): string {
  return (cts / 100).toFixed(2) + ' €'
}

interface LoyaltyScannerProps {
  venteId: number
  totalCts: number
  onClose: () => void
}

export default function LoyaltyScanner({ venteId, totalCts, onClose }: LoyaltyScannerProps) {
  const [barcode, setBarcode] = useState('')
  const [profile, setProfile] = useState<LoyaltyMemberProfile | null>(null)
  const [creditResult, setCreditResult] = useState<CreditResponse | null>(null)
  const [error, setError] = useState('')
  const [redeemedReward, setRedeemedReward] = useState<RewardAvailable | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const scanMut = useMutation({
    mutationFn: (code: string) => loyaltyApi.scan(code),
    onSuccess: (data) => { setProfile(data); setError('') },
    onError: (err) => setError(normalizeError(err).message || 'Code invalide'),
  })

  const creditMut = useMutation({
    mutationFn: () => loyaltyApi.credit({
      member_id: profile!.member_id,
      order_id: venteId,
      amount_cts: totalCts,
      source: 'epicerie',
      program_id: EPICERIE_LOYALTY_PROGRAM_ID,
    }),
    onSuccess: (data) => { setCreditResult(data); setError('') },
    onError: (err) => setError(normalizeError(err).message || 'Erreur crédit points'),
  })

  const redeemMut = useMutation({
    mutationFn: (reward: RewardAvailable) => loyaltyApi.redeem({
      member_id: profile!.member_id,
      reward_id: reward.reward_id,
      order_id: venteId,
    }),
    onSuccess: (_, reward) => setRedeemedReward(reward),
    onError: (err) => setError(normalizeError(err).message || 'Erreur redemption'),
  })

  const handleScan = useCallback(() => {
    if (barcode.trim()) scanMut.mutate(barcode.trim())
  }, [barcode, scanMut])

  const tierLabel: Record<string, { text: string; cls: string }> = {
    standard: { text: 'Membre',  cls: 'bg-slate-100 text-slate-600' },
    vip:      { text: 'VIP',     cls: 'bg-emerald-100 text-emerald-700' },
  }

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-xl overflow-hidden max-w-sm w-full">
      {/* Header */}
      <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between bg-slate-50">
        <div className="flex items-center gap-2">
          <ScanLine className="w-5 h-5 text-emerald-600" />
          <span className="font-semibold text-[14px] text-slate-900">Fidélité</span>
        </div>
        <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600" aria-label="Fermer">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-5 space-y-3">
        {/* Étape 1 : Scanner */}
        {!profile && (
          <div>
            <p className="text-[12px] text-slate-500 mb-2">Scanner ou saisir le code fidélité du client</p>
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={barcode}
                onChange={e => setBarcode(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleScan()}
                placeholder="Code barcode..."
                className="flex-1 px-3 py-2.5 border border-slate-300 rounded-xl text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:border-transparent"
                autoComplete="off"
              />
              <button
                onClick={handleScan}
                disabled={scanMut.isPending || !barcode.trim()}
                className="px-4 py-2.5 bg-emerald-600 text-white text-[13px] font-semibold rounded-xl hover:opacity-90 disabled:opacity-50 min-w-[80px]"
              >
                {scanMut.isPending ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'Scanner'}
              </button>
            </div>
          </div>
        )}

        {/* Erreur */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-3 py-2">
            <p className="text-[12px] text-red-600">{error}</p>
          </div>
        )}

        {/* Étape 2 : Profil client + rewards */}
        {profile && !creditResult && (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center">
                <User className="w-5 h-5 text-slate-400" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-[14px] text-slate-900">{profile.first_name} {profile.last_name}</p>
                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                  tierLabel[profile.current_tier]?.cls || 'bg-slate-100 text-slate-600'
                }`}>
                  {tierLabel[profile.current_tier]?.text || profile.current_tier}
                </span>
              </div>
              <div className="text-right">
                <p className="text-[18px] font-bold text-emerald-600">{profile.points_balance}</p>
                <p className="text-[10px] text-slate-400">points</p>
              </div>
            </div>

            {profile.has_welcome_reward && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2 flex items-center gap-2">
                <Gift className="w-4 h-4 text-emerald-600" />
                <span className="text-[12px] text-emerald-700 font-medium">Cadeau de bienvenue disponible !</span>
              </div>
            )}

            {profile.available_rewards.length > 0 && (
              <div>
                <p className="text-[11px] text-slate-400 font-semibold uppercase mb-1.5">Rewards utilisables</p>
                {profile.available_rewards.map(r => (
                  <button
                    key={r.reward_id}
                    onClick={() => redeemMut.mutate(r)}
                    disabled={redeemMut.isPending}
                    className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl mb-1 hover:border-emerald-600 transition-colors text-left disabled:opacity-50"
                  >
                    <div className="flex items-center gap-2">
                      <Star className="w-4 h-4 text-emerald-600" />
                      <span className="text-[12px] font-medium text-slate-900">{r.name}</span>
                    </div>
                    <span className="text-[11px] font-mono text-emerald-600">{r.points_cost} pts</span>
                  </button>
                ))}
              </div>
            )}

            {redeemedReward && (
              <div className="bg-green-50 border border-green-200 rounded-xl px-3 py-2 text-center">
                <p className="text-[12px] text-green-700 font-medium">Reward utilisé : {redeemedReward.name}</p>
              </div>
            )}

            {/* Spec LOYAL-POINTS-MISMATCH-01 : pas d'estimation, montant réel affiché en étape 3 */}
            <button
              onClick={() => creditMut.mutate()}
              disabled={creditMut.isPending}
              className="w-full py-3 bg-emerald-600 text-white text-[13px] font-semibold rounded-xl hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2 min-h-[48px]"
            >
              {creditMut.isPending
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <><Check className="w-4 h-4" /> Créditer {fmtEur(totalCts)}</>
              }
            </button>
          </div>
        )}

        {/* Étape 3 : Confirmation */}
        {creditResult && (
          <div className="text-center space-y-2 py-2">
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <Check className="w-6 h-6 text-green-600" />
            </div>
            <p className="text-[14px] font-semibold text-slate-900">Points crédités !</p>
            <p className="text-[12px] text-slate-500">
              +{creditResult.points_earned} pts
              {creditResult.multiplier > 1 && <span className="text-emerald-600"> (×{creditResult.multiplier})</span>}
            </p>
            <p className="text-[12px] text-slate-400">Nouveau solde : {creditResult.new_balance} pts</p>
            {creditResult.flash_offer_active && (
              <p className="text-[11px] text-emerald-600 font-medium">Offre flash active !</p>
            )}
            <button
              onClick={onClose}
              className="mt-3 w-full py-2.5 bg-slate-100 text-slate-700 text-[13px] font-medium rounded-xl hover:bg-slate-200 min-h-[44px]"
            >
              Fermer
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
