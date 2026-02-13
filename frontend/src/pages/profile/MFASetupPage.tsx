import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { QRCodeSVG } from 'qrcode.react'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'
import {
  Shield,
  ShieldOff,
  Smartphone,
  Copy,
  Check,
  Loader2,
  AlertTriangle,
  Key,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export default function MFASetupPage() {
  const { fetchUser } = useAuthStore()
  const queryClient = useQueryClient()

  const [step, setStep] = useState<'status' | 'setup' | 'verify' | 'backup'>('status')
  const [setupData, setSetupData] = useState<{ secret: string; provisioning_uri: string } | null>(null)
  const [backupCodes, setBackupCodes] = useState<string[]>([])
  const [verifyCode, setVerifyCode] = useState('')
  const [disableCode, setDisableCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const { data: mfaStatus, isLoading } = useQuery({
    queryKey: ['mfa-status'],
    queryFn: () => authApi.mfaStatus(),
  })

  const setupMutation = useMutation({
    mutationFn: authApi.mfaSetup,
    onSuccess: (data) => {
      setSetupData(data)
      setStep('setup')
    },
  })

  const enableMutation = useMutation({
    mutationFn: authApi.mfaEnable,
    onSuccess: (data) => {
      setBackupCodes(data.backup_codes)
      setStep('backup')
      fetchUser()
      queryClient.invalidateQueries({ queryKey: ['mfa-status'] })
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { message?: string } } }
      setError(error.response?.data?.message || 'Code invalide')
    },
  })

  const disableMutation = useMutation({
    mutationFn: authApi.mfaDisable,
    onSuccess: () => {
      setStep('status')
      setDisableCode('')
      fetchUser()
      queryClient.invalidateQueries({ queryKey: ['mfa-status'] })
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { message?: string } } }
      setError(error.response?.data?.message || 'Code invalide')
    },
  })

  const handleCopySecret = () => {
    if (setupData?.secret) {
      navigator.clipboard.writeText(setupData.secret)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleVerify = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    enableMutation.mutate(verifyCode)
  }

  const handleDisable = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    disableMutation.mutate(disableCode)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    )
  }

  // Show backup codes after enabling
  if (step === 'backup') {
    return (
      <div className="max-w-md mx-auto space-y-6">
        <div className="text-center">
          <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-4">
            <Check className="w-8 h-8 text-green-500" />
          </div>
          <h1 className="text-2xl font-bold">2FA activé !</h1>
          <p className="text-dark-400 mt-2">
            Sauvegardez ces codes de récupération en lieu sûr
          </p>
        </div>

        <div className="card">
          <div className="flex items-center gap-2 mb-4 text-yellow-500">
            <AlertTriangle className="w-5 h-5" />
            <span className="font-medium">Important</span>
          </div>
          <p className="text-sm text-dark-400 mb-4">
            Ces codes ne seront plus affichés. Chaque code ne peut être utilisé
            qu'une seule fois.
          </p>

          <div className="grid grid-cols-2 gap-2 p-4 bg-dark-900 rounded-lg font-mono text-sm">
            {backupCodes.map((code, i) => (
              <div key={i} className="text-center py-1">
                {code}
              </div>
            ))}
          </div>

          <button
            onClick={() => {
              navigator.clipboard.writeText(backupCodes.join('\n'))
              setCopied(true)
              setTimeout(() => setCopied(false), 2000)
            }}
            className="btn-secondary w-full mt-4"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 mr-2" />
                Copié !
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 mr-2" />
                Copier les codes
              </>
            )}
          </button>
        </div>

        <button onClick={() => setStep('status')} className="btn-primary w-full">
          Terminé
        </button>
      </div>
    )
  }

  // Setup flow
  if (step === 'setup' && setupData) {
    return (
      <div className="max-w-md mx-auto space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Configurer 2FA</h1>
          <p className="text-dark-400 mt-2">
            Scannez le QR code avec votre application d'authentification
          </p>
        </div>

        <div className="card">
          <div className="flex justify-center p-4 bg-white rounded-lg">
            <QRCodeSVG value={setupData.provisioning_uri} size={200} />
          </div>

          <div className="mt-4">
            <p className="text-sm text-dark-400 mb-2">
              Ou entrez ce code manuellement :
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 p-2 bg-dark-900 rounded text-sm font-mono break-all">
                {setupData.secret}
              </code>
              <button
                onClick={handleCopySecret}
                className="btn-ghost p-2"
                title="Copier"
              >
                {copied ? (
                  <Check className="w-4 h-4 text-green-500" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </div>

        <form onSubmit={handleVerify} className="card space-y-4">
          <div>
            <label className="label">Code de vérification</label>
            <input
              type="text"
              value={verifyCode}
              onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              className="input text-center text-2xl tracking-widest font-mono"
              placeholder="000000"
              maxLength={6}
            />
          </div>

          {error && (
            <p className="text-sm text-red-400 text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={verifyCode.length !== 6 || enableMutation.isPending}
            className="btn-primary w-full"
          >
            {enableMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : null}
            Activer 2FA
          </button>
        </form>

        <button
          onClick={() => setStep('status')}
          className="btn-ghost w-full"
        >
          Annuler
        </button>
      </div>
    )
  }

  // Status view
  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Authentification à deux facteurs</h1>
        <p className="text-dark-400 mt-1">
          Protégez votre compte avec une vérification supplémentaire
        </p>
      </div>

      {/* Current Status */}
      <div
        className={cn(
          'card',
          mfaStatus?.enabled ? 'border-green-500/20' : 'border-dark-600'
        )}
      >
        <div className="flex items-start gap-4">
          <div
            className={cn(
              'w-12 h-12 rounded-lg flex items-center justify-center',
              mfaStatus?.enabled ? 'bg-green-500/10' : 'bg-dark-700'
            )}
          >
            {mfaStatus?.enabled ? (
              <Shield className="w-6 h-6 text-green-500" />
            ) : (
              <ShieldOff className="w-6 h-6 text-dark-400" />
            )}
          </div>
          <div className="flex-1">
            <h3 className="font-semibold">
              {mfaStatus?.enabled ? '2FA activé' : '2FA désactivé'}
            </h3>
            <p className="text-sm text-dark-400 mt-1">
              {mfaStatus?.enabled
                ? 'Votre compte est protégé par l\'authentification à deux facteurs'
                : 'Activez 2FA pour ajouter une couche de sécurité supplémentaire'}
            </p>
            {mfaStatus?.enabled && (
              <p className="text-sm text-dark-400 mt-2">
                Codes de récupération restants :{' '}
                <span
                  className={cn(
                    'font-medium',
                    mfaStatus.backup_codes_remaining <= 2
                      ? 'text-yellow-500'
                      : 'text-white'
                  )}
                >
                  {mfaStatus.backup_codes_remaining}
                </span>
              </p>
            )}
          </div>
        </div>

        {!mfaStatus?.enabled ? (
          <button
            onClick={() => setupMutation.mutate()}
            disabled={setupMutation.isPending}
            className="btn-primary w-full mt-4"
          >
            {setupMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <Smartphone className="w-4 h-4 mr-2" />
            )}
            Configurer 2FA
          </button>
        ) : (
          <form onSubmit={handleDisable} className="mt-4 space-y-3">
            <div>
              <label className="label">
                Entrez votre code 2FA pour désactiver
              </label>
              <input
                type="text"
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                className="input"
                placeholder="000000"
                maxLength={6}
              />
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <button
              type="submit"
              disabled={disableCode.length !== 6 || disableMutation.isPending}
              className="btn-danger w-full"
            >
              {disableMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <ShieldOff className="w-4 h-4 mr-2" />
              )}
              Désactiver 2FA
            </button>
          </form>
        )}
      </div>

      {/* Info */}
      <div className="card bg-dark-800/50">
        <h3 className="font-semibold mb-3">Applications recommandées</h3>
        <ul className="space-y-2 text-sm text-dark-400">
          <li className="flex items-center gap-2">
            <Smartphone className="w-4 h-4" />
            Google Authenticator
          </li>
          <li className="flex items-center gap-2">
            <Smartphone className="w-4 h-4" />
            Microsoft Authenticator
          </li>
          <li className="flex items-center gap-2">
            <Smartphone className="w-4 h-4" />
            Authy
          </li>
          <li className="flex items-center gap-2">
            <Key className="w-4 h-4" />
            1Password
          </li>
        </ul>
      </div>
    </div>
  )
}
