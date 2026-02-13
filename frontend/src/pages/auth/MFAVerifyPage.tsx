import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Smartphone } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'

export default function MFAVerifyPage() {
  const [code, setCode] = useState(['', '', '', '', '', ''])
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [useRecovery, setUseRecovery] = useState(false)
  const [recoveryCode, setRecoveryCode] = useState('')

  const inputRefs = useRef<(HTMLInputElement | null)[]>([])
  const { mfaSessionToken, setTokens, fetchUser, logout } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (!mfaSessionToken) {
      navigate('/login')
    }
  }, [mfaSessionToken, navigate])

  const handleCodeChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return

    const newCode = [...code]
    newCode[index] = value.slice(-1)
    setCode(newCode)

    // Auto-focus next input
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus()
    }

    // Auto-submit when complete
    if (newCode.every((c) => c) && newCode.join('').length === 6) {
      handleSubmit(newCode.join(''))
    }
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    const newCode = [...code]
    pasted.split('').forEach((char, i) => {
      if (i < 6) newCode[i] = char
    })
    setCode(newCode)

    if (newCode.every((c) => c)) {
      handleSubmit(newCode.join(''))
    }
  }

  const handleSubmit = async (codeStr: string) => {
    if (!mfaSessionToken) return

    setError(null)
    setIsSubmitting(true)

    try {
      const response = await authApi.mfaVerify({
        code: codeStr,
        mfa_session_token: mfaSessionToken,
      })

      setTokens(response.access_token, response.refresh_token)
      await fetchUser()
      navigate('/dashboard')
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      setError(error.response?.data?.message || 'Code invalide')
      setCode(['', '', '', '', '', ''])
      inputRefs.current[0]?.focus()
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleRecoverySubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!mfaSessionToken || !recoveryCode) return

    setError(null)
    setIsSubmitting(true)

    try {
      const response = await authApi.mfaVerify({
        code: recoveryCode,
        mfa_session_token: mfaSessionToken,
      })

      setTokens(response.access_token, response.refresh_token)
      await fetchUser()
      navigate('/dashboard')
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } }
      setError(error.response?.data?.message || 'Code de récupération invalide')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCancel = () => {
    logout()
    navigate('/login')
  }

  if (useRecovery) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold">Code de récupération</h2>
          <p className="text-dark-400 mt-2">
            Entrez un de vos codes de récupération
          </p>
        </div>

        <form onSubmit={handleRecoverySubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="label">Code de récupération</label>
            <input
              type="text"
              value={recoveryCode}
              onChange={(e) => setRecoveryCode(e.target.value.toUpperCase())}
              className="input font-mono text-center tracking-widest"
              placeholder="XXXX-XXXX-XXXX"
              autoFocus
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !recoveryCode}
            className="btn-primary w-full"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                Vérification...
              </>
            ) : (
              'Vérifier'
            )}
          </button>
        </form>

        <div className="text-center space-y-2">
          <button
            onClick={() => setUseRecovery(false)}
            className="text-sm link"
          >
            Utiliser l'application TOTP
          </button>
          <br />
          <button onClick={handleCancel} className="text-sm text-dark-400 hover:text-white">
            Annuler et retourner à la connexion
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="w-16 h-16 rounded-full bg-primary-500/10 flex items-center justify-center mx-auto mb-4">
          <Smartphone className="w-8 h-8 text-primary-500" />
        </div>
        <h2 className="text-2xl font-bold">Vérification 2FA</h2>
        <p className="text-dark-400 mt-2">
          Entrez le code de votre application d'authentification
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
          {error}
        </div>
      )}

      <div className="flex justify-center gap-2" onPaste={handlePaste}>
        {code.map((digit, index) => (
          <input
            key={index}
            ref={(el) => (inputRefs.current[index] = el)}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={(e) => handleCodeChange(index, e.target.value)}
            onKeyDown={(e) => handleKeyDown(index, e)}
            className="w-12 h-14 text-center text-2xl font-bold bg-dark-800 border border-dark-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            autoFocus={index === 0}
            disabled={isSubmitting}
          />
        ))}
      </div>

      {isSubmitting && (
        <div className="flex justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-primary-500" />
        </div>
      )}

      <div className="text-center space-y-2">
        <button
          onClick={() => setUseRecovery(true)}
          className="text-sm link"
        >
          Utiliser un code de récupération
        </button>
        <br />
        <button onClick={handleCancel} className="text-sm text-dark-400 hover:text-white">
          Annuler et retourner à la connexion
        </button>
      </div>
    </div>
  )
}
