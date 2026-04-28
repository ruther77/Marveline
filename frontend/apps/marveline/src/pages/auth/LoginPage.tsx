import { useState, useRef, useCallback, useEffect } from 'react'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Loader2, ShieldAlert } from 'lucide-react'
import HCaptcha from '@hcaptcha/react-hcaptcha'
import { useAuthStore } from '@/stores/authStore'
import { useLogin } from '@/api/queries/useAuth'
import { cn } from '@/lib/utils'
import OAuthButtons from '@/components/auth/OAuthButtons'
import { normalizeError } from '@shared/errors/normalizer'
import { useBrand } from '@/brand/select'

// Site key de test hCaptcha (accepte tout en dev).
// En prod : VITE_HCAPTCHA_SITE_KEY dans .env
const HCAPTCHA_SITE_KEY =
  import.meta.env.VITE_HCAPTCHA_SITE_KEY ?? '10000000-ffff-ffff-ffff-000000000001'

const loginSchema = z.object({
  email: z.string().email('Email invalide'),
  password: z.string().min(1, 'Mot de passe requis'),
})

type LoginForm = z.infer<typeof loginSchema>

export default function LoginPage() {
  const brand = useBrand()
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [captchaRequired, setCaptchaRequired] = useState(false)
  const [captchaToken, setCaptchaToken] = useState<string | null>(null)
  const captchaRef = useRef<HCaptcha>(null)
  const [delaySeconds, setDelaySeconds] = useState(0)
  const delayTotalRef = useRef(0)

  // Countdown vivant : décrément chaque seconde
  useEffect(() => {
    if (delaySeconds <= 0) return
    const id = setInterval(() => {
      setDelaySeconds((prev) => (prev <= 1 ? 0 : prev - 1))
    }, 1000)
    return () => clearInterval(id)
  }, [delaySeconds > 0]) // eslint-disable-line react-hooks/exhaustive-deps

  const { setTokens, setMfaSessionToken, fetchUser } = useAuthStore()
  const loginMutation = useLogin()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as { redirect?: string }

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) })

  const handleCaptchaVerify = useCallback((token: string) => {
    setCaptchaToken(token)
    setError(null)
  }, [])

  const handleCaptchaExpire = useCallback(() => {
    setCaptchaToken(null)
    setError('Le CAPTCHA a expiré. Veuillez le compléter à nouveau.')
  }, [])

  const resetCaptcha = useCallback(() => {
    captchaRef.current?.resetCaptcha()
    setCaptchaToken(null)
  }, [])

  const onSubmit = async (data: LoginForm) => {
    setError(null)

    // Bloquer la soumission si CAPTCHA requis mais non résolu
    if (captchaRequired && !captchaToken) {
      setError('Veuillez compléter le CAPTCHA pour continuer.')
      return
    }

    try {
      const response = await loginMutation.mutateAsync({
        credentials: data,
        captchaToken: captchaToken ?? undefined,
      })

      if (response.mfa_required && response.mfa_session_token) {
        setMfaSessionToken(response.mfa_session_token)
        navigate({ to: '/mfa/verify' })
      } else {
        setTokens(response.access_token)
        await fetchUser()
        if (!useAuthStore.getState().isAuthenticated) {
          setError('Erreur lors de la récupération du profil. Réessayez.')
          return
        }
        // INC-07 : mot de passe compromis ou expiré — redirection forcée (spec §04 §4.7)
        if (response.password_change_required) {
          navigate({ to: '/profile/security' })
          return
        }
        const redirectTo =
          search.redirect && search.redirect.startsWith('/')
            ? search.redirect
            : '/dashboard'
        navigate({ to: redirectTo })
      }
    } catch (err: unknown) {
      const appErr = normalizeError(err)
      const msg = appErr.message ?? ''
      const detail = (appErr.original as { detail?: Record<string, unknown> } | undefined)?.detail

      // Cas 1 : captcha requis mais absent/invalide → afficher le widget (première demande)
      if (msg === 'CAPTCHA verification required') {
        setCaptchaRequired(true)
        resetCaptcha()
        setError(null)
        const delay = (detail?.delay_seconds as number | undefined) ?? 0
        if (delay > 0) { delayTotalRef.current = delay; setDelaySeconds(delay) }
      } else {
        // Cas 2 : credentials invalides (captcha validé ou non requis)
        // Si captcha_required dans la réponse → garder/réafficher le widget
        const captchaNeeded = (detail?.captcha_required as boolean | undefined) ?? false
        const delay = (detail?.delay_seconds as number | undefined) ?? 0
        resetCaptcha()
        setError(msg || 'Erreur de connexion')
        if (captchaNeeded) {
          setCaptchaRequired(true)
        }
        if (delay > 0) { delayTotalRef.current = delay; setDelaySeconds(delay) }
      }
    }
  }

  const canSubmit = !captchaRequired || captchaToken !== null

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Connexion</h2>
        <p className="text-dark-400 mt-2">
          Connectez-vous à votre compte {brand.name}
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && (
          <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="email" className="block text-sm text-dark-400 mb-1">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            className={cn('input', errors.email && 'input-error')}
            placeholder="vous@exemple.com"
            {...register('email')}
          />
          {errors.email && (
            <p className="mt-1 text-sm text-red-400">{errors.email.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="password" className="block text-sm text-dark-400 mb-1">
            Mot de passe
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              className={cn('input pr-10', errors.password && 'input-error')}
              placeholder="••••••••"
              {...register('password')}
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-dark-50"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
            >
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
          {errors.password && (
            <p className="mt-1 text-sm text-red-400">{errors.password.message}</p>
          )}
        </div>

        {/* Widget CAPTCHA — affiché uniquement quand le backend le demande */}
        {captchaRequired && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-amber-400 text-sm">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>
                Trop de tentatives détectées. Complétez la vérification pour continuer.
              </span>
            </div>
            <div className="flex justify-center">
              <HCaptcha
                ref={captchaRef}
                sitekey={HCAPTCHA_SITE_KEY}
                theme="dark"
                onVerify={handleCaptchaVerify}
                onExpire={handleCaptchaExpire}
                onError={() => {
                  setCaptchaToken(null)
                  setError('Erreur du CAPTCHA. Réessayez.')
                }}
              />
            </div>
          </div>
        )}

        {/* Countdown délai brute-force — visible même sans CAPTCHA */}
        {delaySeconds > 0 && (
          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-center">
            <p className="text-sm text-amber-400 font-medium">
              Trop de tentatives. Réessayez dans{' '}
              <span className="font-mono text-amber-300 tabular-nums">{delaySeconds}s</span>
            </p>
            <div className="mt-2 h-1 bg-dark-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-amber-500 rounded-full transition-all duration-1000 ease-linear"
                style={{ width: `${(delaySeconds / (delayTotalRef.current || 1)) * 100}%` }}
              />
            </div>
          </div>
        )}

        <div className="flex items-center justify-between gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              className="w-4 h-4 rounded border-dark-600 bg-dark-900 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-dark-300">Se souvenir de moi</span>
          </label>

          <Link to="/forgot-password" className="text-sm link">
            Mot de passe oublié ?
          </Link>
        </div>

        <button
          type="submit"
          disabled={isSubmitting || !canSubmit || delaySeconds > 0}
          className="btn-primary w-full disabled:opacity-50"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              Connexion...
            </>
          ) : (
            'Se connecter'
          )}
        </button>
      </form>

      <OAuthButtons onError={(err) => setError(err)} disabled={isSubmitting} />

      <p className="text-center text-dark-400 text-sm">
        Contactez votre administrateur pour obtenir un compte.
      </p>
    </div>
  )
}
