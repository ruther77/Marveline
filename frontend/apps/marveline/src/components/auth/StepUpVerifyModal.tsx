import { useState } from 'react'
import { Loader2, ShieldCheck } from 'lucide-react'
import { Modal } from '@shared/components/ui/Modal'
import { useStepUpVerify } from '@/api/queries'
import { normalizeError } from '@shared/errors/normalizer'

interface StepUpVerifyModalProps {
  isOpen: boolean
  onClose: () => void
  onVerified: () => void
  title?: string
  description?: string
}

export default function StepUpVerifyModal({
  isOpen,
  onClose,
  onVerified,
  title = 'Vérification de sécurité',
  description = 'Entrez votre code MFA pour confirmer cette action sensible.',
}: StepUpVerifyModalProps) {
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const stepUpMutation = useStepUpVerify()

  const handleClose = () => {
    if (stepUpMutation.isPending) return
    setCode('')
    setError(null)
    onClose()
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    stepUpMutation.mutate(code, {
      onSuccess: () => {
        setCode('')
        onVerified()
      },
      onError: (err) => {
        setError(normalizeError(err).message || 'Code invalide')
      },
    })
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={title}
      description={description}
      size="sm"
      closeOnOverlayClick={!stepUpMutation.isPending}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex items-center gap-2 text-sm text-dark-300">
          <ShieldCheck className="w-4 h-4 text-primary-400" />
          Validité step-up: 15 minutes
        </div>

        <div>
          <label className="block text-sm text-dark-400 mb-1">
            Code MFA
          </label>
          <input
            type="text"
            autoFocus
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
            className="input text-center text-xl tracking-widest font-mono"
            placeholder="000000"
            maxLength={8}
          />
        </div>

        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            className="btn-secondary"
            onClick={handleClose}
            disabled={stepUpMutation.isPending}
          >
            Annuler
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={code.length < 6 || stepUpMutation.isPending}
          >
            {stepUpMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Vérification...
              </>
            ) : (
              'Valider'
            )}
          </button>
        </div>
      </form>
    </Modal>
  )
}
