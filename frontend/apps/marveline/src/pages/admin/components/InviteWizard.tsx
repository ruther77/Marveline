import { useState } from 'react'
import { useInviteUser } from '@/api/queries/useAdmin'
import { normalizeError } from '@shared/errors/normalizer'
import { cn } from '@/lib/utils'
import { BottomSheet } from '@shared/components/ui/BottomSheet'
import { CheckCircle2, Shield, Briefcase, UserCheck, ArrowLeft, ArrowRight, Loader2, Mail, UserPlus } from 'lucide-react'
import { useBrand } from '@/brand/select'

interface InviteWizardProps {
  isOpen: boolean
  onClose: () => void
}

const ROLES = [
  {
    value: 'admin',
    label: 'Administrateur',
    icon: Shield,
    color: 'border-purple-500 bg-purple-500/10',
    iconColor: 'text-purple-400',
    description: 'Accès total. Gere les utilisateurs, la configuration, les factures et les paramètres.',
  },
  {
    value: 'manager',
    label: 'Manager',
    icon: Briefcase,
    color: 'border-blue-500 bg-blue-500/10',
    iconColor: 'text-blue-400',
    description: "Gère réservations, stock, clients et devis. Pas d'accès aux paramètres admin.",
  },
  {
    value: 'staff',
    label: 'Staff',
    icon: UserCheck,
    color: 'border-dark-500 bg-dark-800',
    iconColor: 'text-dark-300',
    description: 'Consulte et opere au quotidien. Pas de modification sensible.',
  },
] as const

type Step = 'identity' | 'role' | 'confirm' | 'success'

export function InviteWizard({ isOpen, onClose }: InviteWizardProps) {
  const brand = useBrand()
  const [step, setStep] = useState<Step>('identity')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<string>('staff')
  const [error, setError] = useState<string | null>(null)

  const inviteMutation = useInviteUser()

  const reset = () => {
    setStep('identity')
    setFirstName('')
    setLastName('')
    setEmail('')
    setRole('staff')
    setError(null)
    inviteMutation.reset()
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const canProceedIdentity = firstName.trim().length > 0 && lastName.trim().length > 0 && email.includes('@')

  const handleSubmit = () => {
    setError(null)
    inviteMutation.mutate(
      { email: email.trim(), role, first_name: firstName.trim(), last_name: lastName.trim() },
      {
        onSuccess: () => setStep('success'),
        onError: (err) => setError(normalizeError(err).message || 'Erreur lors de l\'invitation'),
      }
    )
  }

  const stepIndex = { identity: 0, role: 1, confirm: 2, success: 3 }[step]
  const selectedRole = ROLES.find((r) => r.value === role) || ROLES[2]
  const initials = `${firstName[0] ?? ''}${lastName[0] ?? ''}`.toUpperCase()

  return (
    <BottomSheet isOpen={isOpen} onClose={handleClose} title="">
      {/* Stepper */}
      {step !== 'success' && (
        <div className="flex items-center gap-2 px-6 pb-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className={cn(
                'h-1 flex-1 rounded-full transition-colors duration-300',
                i <= stepIndex ? 'bg-primary-500' : 'bg-dark-700'
              )}
            />
          ))}
        </div>
      )}

      {/* Step 1 — Identite */}
      {step === 'identity' && (
        <div className="px-6 pb-6 space-y-5">
          <div>
            <h2 className="text-lg font-semibold">Inviter un collaborateur</h2>
            <p className="text-sm text-dark-400 mt-1">Il recevra un email pour créer son mot de passe.</p>
          </div>

          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-dark-400 mb-1">Prénom</label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="input text-sm"
                  placeholder="Jean"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs text-dark-400 mb-1">Nom</label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="input text-sm"
                  placeholder="Dupont"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-dark-400 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input text-sm"
                placeholder={`jean@${brand.code === 'lesplendid' ? 'le-splendid.events' : 'marveline.com'}`}
              />
            </div>
          </div>

          <button
            onClick={() => setStep('role')}
            disabled={!canProceedIdentity}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            Suivant
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Step 2 — Role */}
      {step === 'role' && (
        <div className="px-6 pb-6 space-y-5">
          <div>
            <h2 className="text-lg font-semibold">Choisir le role</h2>
            <p className="text-sm text-dark-400 mt-1">Definit ce que {firstName} peut faire dans {brand.name}.</p>
          </div>

          <div className="space-y-3">
            {ROLES.map((r) => {
              const active = role === r.value
              return (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => setRole(r.value)}
                  className={cn(
                    'w-full flex items-start gap-3 p-4 rounded-xl border-2 text-left transition-all active:scale-[0.98] min-h-[44px]',
                    active ? r.color : 'border-dark-700 bg-dark-900/40'
                  )}
                >
                  <r.icon className={cn('w-5 h-5 mt-0.5 shrink-0', active ? r.iconColor : 'text-dark-400')} />
                  <div>
                    <p className={cn('text-sm font-semibold', active ? 'text-white' : 'text-dark-300')}>
                      {r.label}
                    </p>
                    <p className="text-xs text-dark-400 mt-0.5 leading-relaxed">{r.description}</p>
                  </div>
                  {active && <CheckCircle2 className={cn('w-5 h-5 shrink-0 mt-0.5', r.iconColor)} />}
                </button>
              )
            })}
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep('identity')} className="btn-secondary flex-1 flex items-center justify-center gap-2">
              <ArrowLeft className="w-4 h-4" />
              Retour
            </button>
            <button onClick={() => setStep('confirm')} className="btn-primary flex-1 flex items-center justify-center gap-2">
              Suivant
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 3 — Confirmation */}
      {step === 'confirm' && (
        <div className="px-6 pb-6 space-y-5">
          <div>
            <h2 className="text-lg font-semibold">Confirmer l'invitation</h2>
          </div>

          <div className="card p-5 flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-lg font-semibold text-white shrink-0">
              {initials || '?'}
            </div>
            <div>
              <p className="font-medium">{firstName} {lastName}</p>
              <p className="text-sm text-dark-400">{email}</p>
              <span className={cn(
                'inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full text-xs font-medium border',
                selectedRole.color
              )}>
                <selectedRole.icon className={cn('w-3 h-3', selectedRole.iconColor)} />
                {selectedRole.label}
              </span>
            </div>
          </div>

          <div className="flex items-start gap-3 bg-dark-900/60 rounded-lg p-3 text-sm text-dark-400">
            <Mail className="w-4 h-4 shrink-0 mt-0.5 text-primary-400" />
            <p>Un email d'invitation sera envoyé à <strong className="text-dark-200">{email}</strong> avec un lien pour créer son mot de passe.</p>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button onClick={() => setStep('role')} disabled={inviteMutation.isPending} className="btn-secondary flex-1 flex items-center justify-center gap-2">
              <ArrowLeft className="w-4 h-4" />
              Retour
            </button>
            <button
              onClick={handleSubmit}
              disabled={inviteMutation.isPending}
              className="btn-primary flex-1 flex items-center justify-center gap-2"
            >
              {inviteMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  Envoyer
                  <CheckCircle2 className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Step 4 — Succes */}
      {step === 'success' && (
        <div className="px-6 pb-6 space-y-6 text-center">
          <div className="flex justify-center">
            <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-green-400" />
            </div>
          </div>
          <div>
            <h2 className="text-lg font-semibold">Invitation envoyée !</h2>
            <p className="text-sm text-dark-400 mt-2">
              <strong className="text-dark-200">{firstName} {lastName}</strong> recevra un email a{' '}
              <strong className="text-dark-200">{email}</strong> pour rejoindre l'equipe.
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => reset()}
              className="btn-secondary flex-1 flex items-center justify-center gap-2"
            >
              <UserPlus className="w-4 h-4" />
              Inviter un autre
            </button>
            <button onClick={handleClose} className="btn-primary flex-1">
              Fermer
            </button>
          </div>
        </div>
      )}
    </BottomSheet>
  )
}
