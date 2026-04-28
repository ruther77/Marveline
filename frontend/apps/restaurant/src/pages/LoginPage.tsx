/**
 * Restaurant Login — Dual mode :
 *   1. Premier accès : email + password → enregistre device
 *   2. Retour : PIN 4-6 chiffres sur device enregistré
 */
import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Loader2, Lock } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'
import { massacorpApi, RESTAURANT_TENANT_ID } from '@/api'

type Mode = 'pin' | 'password' | 'set-pin'

const DEVICE_ID_KEY = 'massacorp-device-id'

function getOrCreateDeviceId(): string {
  let id = localStorage.getItem(DEVICE_ID_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(DEVICE_ID_KEY, id)
  }
  return id
}

// ── PIN Pad (gros boutons tactiles) ──────────────────────────────────────────

function PinPad({ onSubmit, loading }: { onSubmit: (pin: string) => void; loading: boolean }) {
  const [pin, setPin] = useState('')
  const maxLen = 6

  const addDigit = (d: string) => {
    if (pin.length < maxLen) setPin(pin + d)
  }
  const backspace = () => setPin(pin.slice(0, -1))
  const submit = () => { if (pin.length >= 4) onSubmit(pin) }

  return (
    <div className="flex flex-col items-center gap-6">
      {/* PIN dots */}
      <div className="flex gap-3">
        {Array.from({ length: maxLen }).map((_, i) => (
          <div
            key={i}
            className={`w-4 h-4 rounded-full border-2 transition-colors ${
              i < pin.length ? 'bg-amber-500 border-amber-500' : 'border-stone-300'
            }`}
          />
        ))}
      </div>

      {/* Numpad */}
      <div className="grid grid-cols-3 gap-3">
        {['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', '←'].map((key) => (
          <button
            key={key || 'empty'}
            onClick={() => {
              if (key === '←') backspace()
              else if (key) addDigit(key)
            }}
            disabled={!key || loading}
            className={`w-[72px] h-[72px] rounded-2xl text-2xl font-semibold transition-colors ${
              !key
                ? 'invisible'
                : key === '←'
                  ? 'bg-stone-200 text-stone-600 hover:bg-stone-300'
                  : 'bg-stone-100 text-stone-900 hover:bg-stone-200 active:bg-stone-300'
            }`}
          >
            {key}
          </button>
        ))}
      </div>

      {/* Submit */}
      <button
        onClick={submit}
        disabled={pin.length < 4 || loading}
        className="w-full max-w-[240px] py-3 bg-amber-600 text-white text-base font-semibold rounded-xl hover:bg-amber-700 disabled:opacity-40 flex items-center justify-center gap-2"
      >
        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Lock className="w-5 h-5" />}
        Déverrouiller
      </button>
    </div>
  )
}

// ── Password form (premier enregistrement) ───────────────────────────────────

function PasswordForm({ onSuccess, onSwitchToPin }: { onSuccess: () => void; onSwitchToPin: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const tenantId = RESTAURANT_TENANT_ID
      // 1. Login email/password
      const result = await massacorpApi.fetchFormData<{
        access_token?: string
        mfa_required?: boolean
        password_change_required?: boolean
      }>(
        '/auth/login',
        { username: email, password, tenant_id: tenantId },
      )

      // MFA requis — non supporté sur tablette restaurant
      if (result.mfa_required) {
        setError('Ce compte a la double authentification activée. Désactivez-la pour utiliser la tablette restaurant, ou utilisez un compte sans MFA.')
        return
      }

      if (!result.access_token) {
        setError('Réponse inattendue du serveur.')
        return
      }

      useMassaCorpAuthStore.getState().setTokens(result.access_token)

      // Changement de mot de passe requis — rediriger vers Marveline
      if (result.password_change_required) {
        setError('Vous devez changer votre mot de passe. Connectez-vous sur Marveline pour le modifier.')
        useMassaCorpAuthStore.getState().logout()
        return
      }

      // 2. Enregistrer le device
      const deviceId = getOrCreateDeviceId()
      await massacorpApi.post('/auth/v2/register-device', {
        device_id: deviceId,
        device_name: `Restaurant tablette ${new Date().toLocaleDateString('fr-FR')}`,
      })

      // 3. Passer en mode "creation PIN"
      onSuccess()
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur de connexion')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 w-full max-w-sm">
      <div>
        <label className="block text-xs font-medium text-stone-600 mb-1">Email</label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          autoComplete="email"
          className="w-full px-3 py-2.5 border border-stone-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
          placeholder="email@example.com"
          required
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-stone-600 mb-1">Mot de passe</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          autoComplete="current-password"
          className="w-full px-3 py-2.5 border border-stone-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
          required
        />
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs text-red-700">{error}</div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full py-2.5 bg-amber-600 text-white text-sm font-semibold rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        Enregistrer cette tablette
      </button>

      <button
        type="button"
        onClick={onSwitchToPin}
        className="w-full text-xs text-stone-500 hover:text-stone-700"
      >
        Déjà enregistré ? Saisir le PIN
      </button>
    </form>
  )
}

// ── Set PIN (apres premier enregistrement) ──────────────────────────────────

function SetPinForm({ onDone }: { onDone: () => void }) {
  const [pin, setPin] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState<'enter' | 'confirm'>('enter')

  const handleDigit = (d: string) => {
    if (step === 'enter' && pin.length < 6) setPin(pin + d)
    if (step === 'confirm' && confirm.length < 6) setConfirm(confirm + d)
  }
  const handleBackspace = () => {
    if (step === 'enter') setPin(pin.slice(0, -1))
    else setConfirm(confirm.slice(0, -1))
  }
  const handleSubmit = async () => {
    if (step === 'enter') {
      if (pin.length < 4) return
      setStep('confirm')
      return
    }
    if (confirm !== pin) {
      setError('Les PINs ne correspondent pas')
      setConfirm('')
      setStep('enter')
      setPin('')
      return
    }
    setLoading(true)
    setError(null)
    try {
      await massacorpApi.post('/auth/v2/set-pin', { pin })
      await useMassaCorpAuthStore.getState().initialize()
      onDone()
    } catch (err) {
      setError(normalizeError(err).message || 'Erreur lors de la creation du PIN')
    } finally {
      setLoading(false)
    }
  }

  const current = step === 'enter' ? pin : confirm

  return (
    <div className="flex flex-col items-center gap-4">
      <p className="text-sm text-stone-600 font-medium">
        {step === 'enter' ? 'Choisissez un PIN (4-6 chiffres)' : 'Confirmez votre PIN'}
      </p>
      <div className="flex gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className={`w-4 h-4 rounded-full border-2 transition-colors ${
              i < current.length ? 'bg-amber-500 border-amber-500' : 'border-stone-300'
            }`}
          />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-3">
        {['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', '←'].map((key) => (
          <button
            key={key || 'empty'}
            onClick={() => {
              if (key === '←') handleBackspace()
              else if (key) handleDigit(key)
            }}
            disabled={!key || loading}
            className={`w-[72px] h-[72px] rounded-2xl text-2xl font-semibold transition-colors ${
              !key ? 'invisible'
              : key === '←' ? 'bg-stone-200 text-stone-600 hover:bg-stone-300'
              : 'bg-stone-100 text-stone-900 hover:bg-stone-200 active:bg-stone-300'
            }`}
          >
            {key}
          </button>
        ))}
      </div>
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-xs text-red-700">{error}</div>
      )}
      <button
        onClick={handleSubmit}
        disabled={current.length < 4 || loading}
        className="w-full max-w-[240px] py-3 bg-amber-600 text-white text-base font-semibold rounded-xl hover:bg-amber-700 disabled:opacity-40 flex items-center justify-center gap-2"
      >
        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : null}
        {step === 'enter' ? 'Suivant' : 'Valider le PIN'}
      </button>
    </div>
  )
}

// ── Page principale ──────────────────────────────────────────────────────────

export default function RestaurantLoginPage() {
  // Première visite (pas de device enregistré) → formulaire email/mdp
  // Retour (device connu) → PIN pad
  const hasDevice = Boolean(localStorage.getItem(DEVICE_ID_KEY))
  const [mode, setMode] = useState<Mode>(hasDevice ? 'pin' : 'password')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handlePinSubmit = async (pin: string) => {
    setLoading(true)
    setError(null)
    try {
      const deviceId = getOrCreateDeviceId()
      const tenantId = RESTAURANT_TENANT_ID
      const result = await massacorpApi.post<{ access_token: string }>(
        '/auth/v2/pin-login',
        { pin, device_id: deviceId, tenant_id: Number(tenantId) },
      )
      useMassaCorpAuthStore.getState().setTokens(result.access_token)
      await useMassaCorpAuthStore.getState().initialize()
      navigate({ to: '/salle' })
    } catch (err) {
      const appErr = normalizeError(err)
      if (appErr.status === 401 || appErr.status === 403) {
        // Device révoqué ou PIN invalide après lockout — réinitialiser
        localStorage.removeItem(DEVICE_ID_KEY)
        setError('Appareil non reconnu. Veuillez vous reconnecter avec email et mot de passe.')
        setMode('password')
      } else {
        setError(appErr.message || 'PIN invalide')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-stone-50 px-4">
      {/* Logo */}
      <div className="mb-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-amber-600 flex items-center justify-center mx-auto mb-3">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 11h.01"/><path d="M11 15h.01"/><path d="M16 16h.01"/><path d="m2 16 20 6-6-20A20 20 0 0 0 2 16"/>
          </svg>
        </div>
        <h1 className="text-xl font-bold text-stone-900">Restaurant</h1>
        <p className="text-stone-500 text-sm mt-1">MassaCorp</p>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-700 max-w-sm w-full text-center">
          {error}
        </div>
      )}

      {mode === 'pin' ? (
        <>
          <PinPad onSubmit={handlePinSubmit} loading={loading} />
          <button
            onClick={() => setMode('password')}
            className="mt-6 text-xs text-stone-400 hover:text-stone-600"
          >
            Premiere connexion sur cette tablette ?
          </button>
        </>
      ) : mode === 'password' ? (
        <PasswordForm
          onSuccess={() => setMode('set-pin')}
          onSwitchToPin={() => setMode('pin')}
        />
      ) : (
        <SetPinForm onDone={() => navigate({ to: '/salle' })} />
      )}
    </div>
  )
}
