/**
 * Page publique d'inscription fidélité — Programme L'Incontournable.
 * Accessible sans authentification via QR code au comptoir épicerie.
 * Spec §"Inscription" : Prenom + Nom + Telephone + Mois naissance, code parrain optionnel.
 */
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Gift, Check, Loader2 } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import { massacorpApi } from '@/api'
import { EPICERIE_LOYALTY_PROGRAM_ID } from '@/api/loyalty'

interface JoinResponse {
  member_id: number
  referral_code: string
  wallet_url: string | null
  welcome_reward_available: boolean
}

const MONTHS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

export default function JoinLoyaltyPage() {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [phone, setPhone] = useState('')
  const [birthMonth, setBirthMonth] = useState('')
  const [referralCode, setReferralCode] = useState('')
  const [error, setError] = useState('')
  const [result, setResult] = useState<JoinResponse | null>(null)

  const params = new URLSearchParams(window.location.search)
  const programId = Number(params.get('program_id') || String(EPICERIE_LOYALTY_PROGRAM_ID))

  const joinMut = useMutation({
    mutationFn: () => massacorpApi.post<JoinResponse>('/loyalty/join', {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      phone: phone.trim(),
      birth_month: birthMonth ? Number(birthMonth) : undefined,
      referral_code_used: referralCode.trim() || undefined,
      program_id: programId,
    }),
    onSuccess: (data) => { setResult(data); setError('') },
    onError: (err) => setError(normalizeError(err).message || "Erreur lors de l'inscription"),
  })

  if (result) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-lg p-8 max-w-sm w-full text-center space-y-4">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">Bienvenue !</h1>
          <p className="text-[13px] text-slate-500">Votre carte fidélité est activée.</p>

          <div className="bg-slate-50 rounded-xl p-4 space-y-2">
            <p className="text-[11px] text-slate-400 uppercase font-semibold">Votre code parrainage</p>
            <p className="text-2xl font-bold text-emerald-600 font-mono tracking-wide">{result.referral_code}</p>
            <p className="text-[11px] text-slate-400">Partagez-le pour gagner 200 points !</p>
          </div>

          {result.welcome_reward_available && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex items-center gap-2">
              <Gift className="w-5 h-5 text-emerald-600 shrink-0" />
              <p className="text-[12px] text-emerald-700 font-medium text-left">
                Un cadeau de bienvenue vous attend lors de votre prochaine visite !
              </p>
            </div>
          )}

          {result.wallet_url && (
            <a href={result.wallet_url} target="_blank" rel="noopener noreferrer"
              className="block w-full py-3 bg-slate-900 text-white text-[13px] font-semibold rounded-xl hover:bg-slate-800">
              Ajouter au Wallet
            </a>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-lg p-8 max-w-sm w-full space-y-5">
        <div className="text-center">
          <div className="w-14 h-14 rounded-2xl bg-emerald-600 flex items-center justify-center mx-auto mb-3">
            <Gift className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">L'Incontournable</h1>
          <p className="text-[13px] text-slate-500 mt-1">Programme fidélité restaurant & épicerie</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-3 py-2 text-[12px] text-red-600">{error}</div>
        )}

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-slate-500 mb-1 block">Prénom</label>
              <input type="text" value={firstName} onChange={e => setFirstName(e.target.value)}
                className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-[13px] focus:outline-none focus:ring-2 focus:ring-emerald-600" required />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-slate-500 mb-1 block">Nom</label>
              <input type="text" value={lastName} onChange={e => setLastName(e.target.value)}
                className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-[13px] focus:outline-none focus:ring-2 focus:ring-emerald-600" required />
            </div>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-slate-500 mb-1 block">Téléphone</label>
            <input type="tel" value={phone} onChange={e => setPhone(e.target.value)}
              placeholder="+33 6 12 34 56 78"
              className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-[13px] focus:outline-none focus:ring-2 focus:ring-emerald-600" required />
          </div>

          <div>
            <label className="text-[11px] font-semibold text-slate-500 mb-1 block">Mois de naissance (optionnel)</label>
            <select value={birthMonth} onChange={e => setBirthMonth(e.target.value)}
              className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-[13px] bg-white focus:outline-none focus:ring-2 focus:ring-emerald-600">
              <option value="">—</option>
              {MONTHS.map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
            </select>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-slate-500 mb-1 block">Code parrain (optionnel)</label>
            <input type="text" value={referralCode} onChange={e => setReferralCode(e.target.value)}
              placeholder="Ex: JEAN4827"
              className="w-full px-3 py-2.5 border border-slate-300 rounded-xl text-[13px] font-mono focus:outline-none focus:ring-2 focus:ring-emerald-600" />
          </div>
        </div>

        <button
          onClick={() => joinMut.mutate()}
          disabled={joinMut.isPending || !firstName.trim() || !lastName.trim() || !phone.trim()}
          className="w-full py-3 bg-emerald-600 text-white text-[14px] font-semibold rounded-xl hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2 min-h-[48px]"
        >
          {joinMut.isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Rejoindre le programme'}
        </button>

        <p className="text-[10px] text-slate-400 text-center">
          5 pts/€ à l'épicerie · 10 pts/€ au restaurant · Rewards dès 500 pts
        </p>
      </div>
    </div>
  )
}
