import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Gift, Check, Loader2 } from 'lucide-react'
import { useJoinLoyalty } from '@/api/queries/useLoyalty'
import { normalizeError } from '@shared/errors/normalizer'

const joinSchema = z.object({
  first_name: z.string().min(1, 'Requis').max(100),
  last_name: z.string().min(1, 'Requis').max(100),
  phone: z.string().min(6, 'Minimum 6 chiffres').max(20),
  birth_month: z.coerce.number().min(1).max(12).optional(),
  referral_code_used: z.string().max(50).optional(),
})

type JoinFormData = z.infer<typeof joinSchema>

const MONTH_NAMES = [
  'Janvier', 'Fevrier', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Aout', 'Septembre', 'Octobre', 'Novembre', 'Decembre',
]

export default function JoinLoyaltyPage() {
  const [error, setError] = useState('')
  const [success, setSuccess] = useState<{ referralCode: string; walletUrl?: string } | null>(null)

  const joinMutation = useJoinLoyalty()

  const { register, handleSubmit, formState: { errors } } = useForm<JoinFormData>({
    resolver: zodResolver(joinSchema),
  })

  // Extraire program_id depuis l'URL (QR code)
  const params = new URLSearchParams(window.location.search)
  const programId = Number(params.get('program_id') || '1')

  const onSubmit = async (data: JoinFormData) => {
    setError('')
    try {
      const result = await joinMutation.mutateAsync({
        ...data,
        program_id: programId,
        birth_month: data.birth_month || undefined,
        referral_code_used: data.referral_code_used || undefined,
      })
      setSuccess({
        referralCode: result.referral_code,
        walletUrl: result.wallet_url ?? undefined,
      })
    } catch (err) {
      setError(normalizeError(err).message || 'Une erreur est survenue')
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-dark-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md space-y-6 text-center">
          <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto">
            <Check className="w-8 h-8 text-green-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Bienvenue !</h1>
          <p className="text-dark-300">
            Votre carte de fidelite est prete. Votre code parrain :
          </p>
          <div className="bg-dark-800 rounded-xl p-4 border border-dark-600">
            <span className="text-2xl font-mono font-bold text-primary-400">
              {success.referralCode}
            </span>
          </div>
          <p className="text-dark-400 text-sm">
            Partagez ce code avec vos proches pour gagner 200 points chacun !
          </p>
          {success.walletUrl && (
            <a
              href={success.walletUrl}
              className="inline-flex items-center gap-2 px-6 py-3 bg-primary-500 text-white rounded-xl font-medium hover:bg-primary-600 transition-colors"
            >
              Ajouter au Wallet
            </a>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-dark-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Header */}
        <div className="text-center space-y-3">
          <div className="w-14 h-14 bg-primary-500/20 rounded-full flex items-center justify-center mx-auto">
            <Gift className="w-7 h-7 text-primary-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Carte Fidelite</h1>
          <p className="text-dark-300">
            Gagnez des points a chaque visite et profitez de recompenses exclusives.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-dark-200 mb-1">Prenom *</label>
              <input
                {...register('first_name')}
                placeholder="Jean"
                className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-xl text-white placeholder:text-dark-500 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
              {errors.first_name && <p className="text-red-400 text-xs mt-1">{errors.first_name.message}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-dark-200 mb-1">Nom *</label>
              <input
                {...register('last_name')}
                placeholder="Dupont"
                className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-xl text-white placeholder:text-dark-500 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
              {errors.last_name && <p className="text-red-400 text-xs mt-1">{errors.last_name.message}</p>}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-200 mb-1">Telephone *</label>
            <input
              {...register('phone')}
              type="tel"
              placeholder="+33 6 12 34 56 78"
              className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-xl text-white placeholder:text-dark-500 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
            {errors.phone && <p className="text-red-400 text-xs mt-1">{errors.phone.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-200 mb-1">Mois de naissance</label>
            <select
              {...register('birth_month')}
              className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-xl text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value="">Optionnel</option>
              {MONTH_NAMES.map((name, i) => (
                <option key={i + 1} value={i + 1}>{name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-200 mb-1">Code parrain</label>
            <input
              {...register('referral_code_used')}
              placeholder="JEAN4827"
              className="w-full px-3 py-2.5 bg-dark-800 border border-dark-600 rounded-xl text-white placeholder:text-dark-500 focus:ring-2 focus:ring-primary-500 focus:border-transparent uppercase"
            />
            <p className="text-dark-500 text-xs mt-1">Si un proche vous a donne son code</p>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={joinMutation.isPending}
            className="w-full py-3 bg-primary-500 text-white rounded-xl font-medium hover:bg-primary-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {joinMutation.isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              'Rejoindre le programme'
            )}
          </button>
        </form>

        <p className="text-center text-dark-500 text-xs">
          En vous inscrivant, vous acceptez les conditions du programme de fidelite.
        </p>
      </div>
    </div>
  )
}
